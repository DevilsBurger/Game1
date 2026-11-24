# -*- coding: utf-8 -*-
"""
전투 분석 리포트 (08 §8.1). 결과 화면(S08) '분석' 탭의 기준 구현.

rules["report"]=True일 때만 수집한다. 수집은 읽기 전용이다 — RNG·이벤트 스트림·체크섬·전투 결과에 영향을 주지 않으므로
리포트를 켜도 테스트 벡터는 그대로 재현된다. 클라이언트(C#)는 같은 규칙으로 `BattleReport`를 만든다.
"""

BUCKET_SEC = 5.0          # 시간대별 피해 막대 간격
KILL_WINDOW_SEC = 4.0     # '누구에게 쓰러졌는가' 집계 구간(사망 직전)
KINDS = ("physical", "magic", "true")
ENV = -1                  # 환경 피해(성벽 화살비 등) 출처 uid

# 패배 원인 힌트 임계값. 문자열 키는 ui.report.hint.{code}
EARLY_DEATH_SEC = 8.0     # 이 시간 안에 전열이 쓰러지면 frontline_collapsed
DIVE_DEATH_SEC = 12.0     # 이 시간 안에 후열이 근접 적에게 쓰러지면 backline_dived
TYPE_HEAVY_SHARE = 0.65   # 받은 피해 중 한 속성이 이 비율 이상이면 physical_heavy / magic_heavy
THREAT_SHARE = 0.40       # 적 1명이 아군이 받은 피해의 이 비율 이상이면 single_threat
CC_SHARE = 0.20           # 아군 총 생존 시간 중 기절 비율이 이 이상이면 cc_locked
SUSTAIN_SHARE = 0.35      # 적 치유+방어막 흡수가 아군이 준 피해의 이 비율 이상이면 enemy_sustain
DAMAGE_SHORT_HP = 0.50    # 종료 시 적 잔여 체력 비율이 이 이상이면 damage_short


class ReportCollector:
    def __init__(self):
        self.matrix = {}        # (src_uid, dst_uid) -> 피해
        self.by_kind = {}       # uid -> {"dealt": {kind: v}, "taken": {kind: v}, "skill": v, "attack": v}
        self.absorbed = {}      # uid -> 방어막이 흡수한 피해
        self.heal = {}          # uid -> {"done": v, "vamp": v, "received": v}
        self.stunned = {}       # uid -> 기절당한 시간(초)
        self.stun_dealt = {}    # uid -> 기절시킨 시간(초, 스킬 시전자 기준)
        self.recent = {}        # dst_uid -> [(t, src_uid, amount, kind)]
        self.deaths = []        # 사망 순서대로
        self.timeline = []      # [[아군 피해, 적 피해], ...] BUCKET_SEC 간격

    def _unit(self, uid):
        d = self.by_kind.get(uid)
        if d is None:
            d = self.by_kind[uid] = {"dealt": dict.fromkeys(KINDS, 0.0), "taken": dict.fromkeys(KINDS, 0.0), "skill": 0.0, "attack": 0.0}
        return d

    def on_damage(self, t, src, dst, dealt, absorbed, kind, is_skill, is_attack):
        s = src.uid if src is not None else ENV
        self.matrix[(s, dst.uid)] = self.matrix.get((s, dst.uid), 0.0) + dealt
        self._unit(dst.uid)["taken"][kind] += dealt
        if absorbed > 0: self.absorbed[dst.uid] = self.absorbed.get(dst.uid, 0.0) + absorbed
        if src is not None:
            d = self._unit(s); d["dealt"][kind] += dealt
            if is_attack: d["attack"] += dealt
            elif is_skill: d["skill"] += dealt
            i = int(t / BUCKET_SEC)
            while len(self.timeline) <= i: self.timeline.append([0.0, 0.0])
            self.timeline[i][src.team] += dealt
        self.recent.setdefault(dst.uid, []).append((t, s, dealt, kind))

    def on_heal(self, src, dst, healed, from_vamp):
        if healed <= 0: return
        if src is not None:
            h = self.heal.setdefault(src.uid, {"done": 0.0, "vamp": 0.0, "received": 0.0})
            h["vamp" if from_vamp else "done"] += healed
        self.heal.setdefault(dst.uid, {"done": 0.0, "vamp": 0.0, "received": 0.0})["received"] += healed

    def on_stun(self, src, dst, dur):
        self.stunned[dst.uid] = self.stunned.get(dst.uid, 0.0) + dur
        if src is not None: self.stun_dealt[src.uid] = self.stun_dealt.get(src.uid, 0.0) + dur

    def on_death(self, t, u, killer):
        win = [r for r in self.recent.get(u.uid, []) if r[0] >= t - KILL_WINDOW_SEC]
        total = sum(r[2] for r in win)
        by_src = {}; by_kind = dict.fromkeys(KINDS, 0.0)
        for _, s, amt, kind in win:
            by_src[s] = by_src.get(s, 0.0) + amt; by_kind[kind] += amt
        top = sorted(by_src.items(), key=lambda kv: (-kv[1], kv[0]))[:3]
        self.deaths.append({"uid": u.uid, "team": u.team, "t": round(t, 2), "killer": (killer.uid if killer is not None else ENV),
                            "sources": [{"uid": s, "amount": round(a), "share": round(a / total, 3) if total > 0 else 0.0} for s, a in top],
                            "kinds": {k: round(v) for k, v in by_kind.items()}})

    # ── 집계
    def build(self, battle):
        units = {u.uid: u for u in battle.units}
        end = battle.t
        rows = []
        for u in battle.units:
            k = self.by_kind.get(u.uid) or {"dealt": dict.fromkeys(KINDS, 0.0), "taken": dict.fromkeys(KINDS, 0.0), "skill": 0.0, "attack": 0.0}
            h = self.heal.get(u.uid, {"done": 0.0, "vamp": 0.0, "received": 0.0})
            rows.append({"uid": u.uid, "team": u.team, "id": u.hid, "name": u.name, "is_summon": u.is_summon or u.is_turret, "owner": (u.spawned_by if u.spawned_by is not None else ENV),
                         "dealt": {x: round(v) for x, v in k["dealt"].items()}, "dealt_attack": round(k["attack"]), "dealt_skill": round(k["skill"]),
                         "taken": {x: round(v) for x, v in k["taken"].items()}, "shield_absorbed": round(self.absorbed.get(u.uid, 0.0)), "mitigated": round(u.stats["mitigated"]),
                         "heal_done": round(h["done"]), "heal_vamp": round(h["vamp"]), "heal_received": round(h["received"]),
                         "stunned_sec": round(self.stunned.get(u.uid, 0.0), 2), "stun_dealt_sec": round(self.stun_dealt.get(u.uid, 0.0), 2),
                         "kills": u.stats["kills"], "casts": u.stats["casts"], "alive_sec": round(u.dead_time if u.dead_time is not None else end, 2)})
        matrix = [{"src": s, "dst": d, "amount": round(a)} for (s, d), a in sorted(self.matrix.items()) if round(a) > 0]
        out = {"units": rows, "matrix": matrix, "deaths": self.deaths, "bucket_sec": BUCKET_SEC,
               "timeline": [[round(a), round(b)] for a, b in self.timeline], "mvp": self._mvp(battle, 0), "enemy_mvp": self._mvp(battle, 1)}
        out["threats"] = self._threats(units)
        out["hints"] = self._hints(battle, units, out) if battle.winner != 0 else []
        return out

    def _score(self, u):
        """MVP 점수: 준 피해 + 치유 + 흡수·경감으로 버틴 피해의 절반 (소환수 기여는 주인에게 합산)."""
        h = self.heal.get(u.uid, {"done": 0.0})
        return u.stats["dmg"] + h["done"] + 0.5 * (self.absorbed.get(u.uid, 0.0) + u.stats["mitigated"])

    def _mvp(self, battle, team):
        score = {}
        for u in battle.units:
            if u.team != team or u.is_structure: continue
            owner = u.spawned_by if u.spawned_by is not None else u.uid
            score[owner] = score.get(owner, 0.0) + self._score(u)
        if not score: return ENV
        return sorted(score.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]

    def _threats(self, units):
        """아군이 받은 피해를 적 유닛별로 합산(소환수는 주인에게). 상위 3."""
        by = {}; total = 0.0
        for (s, d), a in self.matrix.items():
            if units[d].team != 0: continue
            total += a
            if s != ENV:
                su = units[s]; s = su.spawned_by if su.spawned_by is not None else s
            by[s] = by.get(s, 0.0) + a
        top = sorted(by.items(), key=lambda kv: (-kv[1], kv[0]))[:3]
        return [{"uid": s, "amount": round(a), "share": round(a / total, 3) if total > 0 else 0.0} for s, a in top]

    def _hints(self, battle, units, out):
        """패배(또는 무승부) 원인 힌트. 규칙 기반·결정론. 반환: [{code, uid?, value?}] 최대 3개(우선순위 순)."""
        hints = []
        allies = [u for u in battle.units if u.team == 0 and not u.is_summon and not u.is_turret and not u.is_structure]
        ally_deaths = [d for d in self.deaths if d["team"] == 0 and units[d["uid"]] in allies]
        # 1) 전열 조기 붕괴 / 후열 침투
        for d in ally_deaths:
            u = units[d["uid"]]
            if u.front and u.range_base <= 1 and d["t"] <= EARLY_DEATH_SEC:
                hints.append({"code": "frontline_collapsed", "uid": u.uid, "value": d["t"]}); break
        for d in ally_deaths:
            u = units[d["uid"]]; k = units.get(d["killer"])
            if u.range_base > 1 and d["t"] <= DIVE_DEATH_SEC and k is not None and k.range_base <= 1:
                hints.append({"code": "backline_dived", "uid": u.uid, "value": d["t"]}); break
        # 2) 단일 위협
        if out["threats"] and out["threats"][0]["uid"] != ENV and out["threats"][0]["share"] >= THREAT_SHARE:
            hints.append({"code": "single_threat", "uid": out["threats"][0]["uid"], "value": out["threats"][0]["share"]})
        # 3) 피해 속성 편중
        taken = dict.fromkeys(KINDS, 0.0)
        for u in allies:
            for k, v in (self.by_kind.get(u.uid) or {"taken": {}})["taken"].items(): taken[k] += v
        tot = sum(taken.values())
        if tot > 0:
            for kind in ("physical", "magic"):
                if taken[kind] / tot >= TYPE_HEAVY_SHARE:
                    hints.append({"code": kind + "_heavy", "value": round(taken[kind] / tot, 3)})
        # 4) 군중 제어
        alive = sum((u.dead_time if u.dead_time is not None else battle.t) for u in allies)
        stunned = sum(self.stunned.get(u.uid, 0.0) for u in allies)
        if alive > 0 and stunned / alive >= CC_SHARE:
            hints.append({"code": "cc_locked", "value": round(stunned / alive, 3)})
        # 5) 적 유지력 / 화력 부족
        dealt = sum(a for (s, d), a in self.matrix.items() if units[d].team == 1)
        enemy_sustain = sum(self.heal.get(u.uid, {"received": 0.0})["received"] + self.absorbed.get(u.uid, 0.0) for u in battle.units if u.team == 1)
        if dealt > 0 and enemy_sustain / dealt >= SUSTAIN_SHARE:
            hints.append({"code": "enemy_sustain", "value": round(enemy_sustain / dealt, 3)})
        enemies = [u for u in battle.units if u.team == 1 and not u.is_summon and not u.is_turret]
        cap = sum(u.max_hp for u in enemies)
        left = sum(max(0.0, u.hp) for u in enemies if u.alive)
        if cap > 0 and left / cap >= DAMAGE_SHORT_HP:
            hints.append({"code": "damage_short", "value": round(left / cap, 3)})
        return hints[:3]
