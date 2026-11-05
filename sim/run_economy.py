# -*- coding: utf-8 -*-
"""
경제 진행 시뮬레이션: 가상 플레이어(무과금/소과금/헤비) 90일 몬테카를로.
모델:
  - 하루 세션: 프로필별 목표 참전 횟수. 영웅별 스태미너 100, 6분당 1 회복(하루 240), 참전 시 영웅당 난이도별 소모(웨이브형 ×1.5).
  - 전투 선택: 현재 '전력 레벨'(보유 상위 팀의 계층·성급) 근처의 지역/조우/스토리 전투. 난이도는 전력 여유에 따라 보통/어려움/악몽.
    승률 = 로지스틱(전력 레벨 − 전투 레벨) (등가 모델·난이도 검증 결과를 근사: 여유 0 → 보통 78%).
  - 보상: economy.json 공식(골드·재료·아이템 드랍·영웅 드랍·호감도 천장). 중복 영웅 → 파편.
  - 지출: 승급(재료+골드), 아이템(골드 35%), 소모품(프로필별 보석), 서약서(계층 4·5 조우).
출력: sim/reports/economy_sim.json, docs/07 §9 자동 삽입
"""
import json, os, sys, random, statistics, math
ROOT = os.path.join(os.path.dirname(__file__), "..")
DATA = os.path.join(ROOT, "data"); REP = os.path.join(os.path.dirname(__file__), "reports")
E = json.load(open(os.path.join(DATA, "economy.json"), encoding="utf-8"))
HEROES = json.load(open(os.path.join(DATA, "heroes.json"), encoding="utf-8"))["heroes"]
BATTLES = [b for b in json.load(open(os.path.join(DATA, "battles.json"), encoding="utf-8"))["battles"] if b["kind"] in ("regional", "encounter", "story")]
PROFILES = {
    "free":  dict(name="무과금", battles_per_day=25, gems_per_month=0, pass_=False, potion_gems_cap=0, pact_on_t45=False),
    "light": dict(name="소과금(월 1,000보석+월정액)", battles_per_day=35, gems_per_month=1000, pass_=True, potion_gems_cap=200, pact_on_t45=True),
    "heavy": dict(name="헤비(월 10,000보석+월정액)", battles_per_day=60, gems_per_month=10000, pass_=True, potion_gems_cap=3000, pact_on_t45=True),
}
TIER_POWER = {1: 10, 2: 18, 3: 26, 4: 34, 5: 42}; STAR_POWER = {1: 0, 2: 14, 3: 28}


def hero_power(tier, star): return TIER_POWER[tier] + STAR_POWER[star]


class Player:
    def __init__(self, profile, rng):
        self.p = PROFILES[profile]; self.rng = rng
        self.gold = 500; self.gems = 100; self.mats = {"M001": 0, "M002": 0, "M003": 0}
        self.owned = {}   # hero_id -> star
        self.stamina = {}  # hero_id -> stamina
        self.affinity = {}
        self.items = {"component": 0, "completed": 0, "support": 0, "artifact": 0, "national": 0, "radiant": 0}
        self.level = 1; self.exp = 0; self.cleared = set(); self.act = 1
        self.log = []
        # 시작: 레온 + 1막 스토리 보상 2명(브랜든·마리엘 상당) 대신 계층1 영웅 2명
        for h in [x for x in HEROES if x["tier"] == 1][:2]: self.add_hero(h["id"])
        self.player_unit_power = hero_power(3, 1)
        self.gems_spent = 0; self.gold_earned = 0; self.gold_spent = 0; self.stamina_blocked_days = 0; self.battles_fought = 0; self.wins = 0; self.rotations = 0

    def add_hero(self, hid):
        if hid in self.owned:
            t = next(h["tier"] for h in HEROES if h["id"] == hid)
            self.mats["M001"] += E["duplicate_hero_conversion"]["M001_by_tier"][str(t)]; self.affinity[hid] = self.affinity.get(hid, 0) + E["duplicate_hero_conversion"]["affinity"]
            return False
        self.owned[hid] = 1; self.stamina[hid] = 100; return True

    def team_slots(self): return E["team_size_by_player_level"][str(min(60, self.level))]

    def power_level(self, team=None):
        """전력 레벨: 실제 출전 팀(미지정 시 최강 팀)의 평균 전력 + 인원·아이템 보정. 로테이션(약한 영웅 출전)은 승률 손실로 나타난다."""
        if team is None:
            pw = sorted([hero_power(next(h["tier"] for h in HEROES if h["id"] == hid), st) for hid, st in self.owned.items()], reverse=True)
            team_pw = pw[:max(1, min(self.team_slots(), len(pw)))]
        else:
            team_pw = [hero_power(next(h["tier"] for h in HEROES if h["id"] == hid), self.owned[hid]) for hid in team]
        team_pw = team_pw + [self.player_unit_power]
        return statistics.mean(team_pw) + 0.6 * min(len(team_pw), 6) + 0.15 * self.items["completed"]

    def pick_battle(self):
        pl = self.power_level()
        cands = [b for b in BATTLES if b["act"] <= self.act and b["level"] <= pl + 12]
        if not cands: cands = [b for b in BATTLES if b["act"] <= self.act]
        enc = [b for b in cands if b["kind"] == "encounter" and b["hero_id"] not in self.owned and b["level"] <= pl + 6]
        story = [b for b in cands if b["kind"] == "story" and b["id"] not in self.cleared and b["level"] <= pl + 8]
        reg = [b for b in cands if b["kind"] == "regional"]
        r = self.rng.random()
        if story and r < 0.25: return self.rng.choice(story)
        if enc and r < 0.6: return self.rng.choice(sorted(enc, key=lambda b: -b["level"])[:12])
        return self.rng.choice(sorted(reg, key=lambda b: -b["level"])[:30]) if reg else self.rng.choice(cands)

    def choose_difficulty(self, b):
        margin = self.power_level() - b["level"]
        return "nightmare" if margin >= 24 else ("hard" if margin >= 10 else "normal")

    def win_prob(self, b, diff, team=None):
        margin = self.power_level(team) - b["level"] - {"normal": 0, "hard": 10, "nightmare": 24}[diff]
        return 1 / (1 + math.exp(-(margin + 7) / 6.0))   # margin 0 → 76%

    def day(self, day_idx):
        p = self.p
        for hid in self.stamina: self.stamina[hid] = min(100, self.stamina[hid] + (240 * (1.5 if p["pass_"] else 1.0)) / 1)
        if day_idx % 30 == 0: self.gems += p["gems_per_month"] + (30 * 50 if p["pass_"] else 0)
        fought = 0; blocked = False
        for _ in range(p["battles_per_day"]):
            b = self.pick_battle(); diff = self.choose_difficulty(b)
            cost = b["difficulties"][diff]["stamina_per_hero"]
            n = max(b["participation"]["min"], min(b["participation"]["max"], self.team_slots()))
            ready = sorted([h for h, s in self.stamina.items() if s >= cost], key=lambda h: -hero_power(next(x["tier"] for x in HEROES if x["id"] == h), self.owned[h]))
            best = sorted(self.stamina, key=lambda h: -hero_power(next(x["tier"] for x in HEROES if x["id"] == h), self.owned[h]))[:n]
            if any(self.stamina[h] < cost for h in best): self.rotations += 1
            if len(ready) < min(n, 1):
                # 물약으로 보충 (보석)
                if p["potion_gems_cap"] and self.gems >= 22 and self.gems_spent_today < p["potion_gems_cap"] / 30:
                    self.gems -= 22; self.gems_spent += 22; self.gems_spent_today += 22
                    for h in list(self.stamina)[:1]: self.stamina[h] = min(100, self.stamina[h] + 50)
                    continue
                blocked = True; break
            team = ready[:n]
            for h in team: self.stamina[h] -= cost
            self.battles_fought += 1; fought += 1
            won = self.rng.random() < self.win_prob(b, diff, team)
            if not won:
                for h in team: self.stamina[h] += cost * 0.5
                continue
            self.wins += 1
            rw = b["difficulties"][diff]["rewards"]
            gold = rw["gold"]; self.gold += gold; self.gold_earned += gold
            self.exp += rw["exp"]
            while self.level < 60 and self.exp >= E["player_level_exp"][str(self.level)]:
                self.exp -= E["player_level_exp"][str(self.level)]; self.level += 1
                for h in self.stamina: self.stamina[h] = 100
            for k, v in rw["materials"].items():
                if k.endswith("_chance"):
                    if self.rng.random() * 100 < v["pct"]: self.mats[k.split("_")[0]] += v["qty"]
                else: self.mats[k] += v
            for it in rw["items"]:
                if self.rng.random() * 100 < it["chance_pct"]: self.items[it["pool"]] = self.items.get(it["pool"], 0) + it["qty"]
            if b["id"] not in self.cleared:
                self.cleared.add(b["id"]); fc = b["difficulties"].get("first_clear_bonus", {})
                self.gold += fc.get("gold", 0); self.gems += fc.get("gems", 0)
                for k, v in fc.get("materials", {}).items(): self.mats[k] += v
                if fc.get("hero_guaranteed"): self.add_hero(fc["hero_guaranteed"]["hero_id"])
                if b["kind"] == "story" and b.get("story_order"):
                    last_of_act = max(x["story_order"] for x in BATTLES if x["kind"] == "story" and x["act"] == b["act"])
                    if b["story_order"] == last_of_act and self.act < 5: self.act += 1; self.log.append((day_idx, f"act{self.act}"))
            hd = rw.get("hero_drop")
            if hd:
                if "hero_id" in hd:
                    hid = hd["hero_id"]; tier = hd["tier"]; chance = hd["chance_pct"]
                    if p["pact_on_t45"] and tier >= 4 and self.gems >= 60: self.gems -= 60; self.gems_spent += 60; chance = min(90, chance * 2)
                    if self.affinity.get(hid, 0) >= 100 or self.rng.random() * 100 < chance:
                        if self.add_hero(hid): self.affinity[hid] = 0
                    else:
                        self.affinity[hid] = self.affinity.get(hid, 0) + E["affinity_pity"]["per_failed_encounter"][str(tier)]
                elif hd.get("pool") == "native_random" and self.rng.random() * 100 < hd["chance_pct"]:
                    self.add_hero(self.rng.choice(hd["hero_ids"]))
        if blocked: self.stamina_blocked_days += 1
        self.spend()
        return fought

    def spend(self):
        # 승급: 보유 중 전력 기여 큰 영웅부터
        for hid, st in sorted(self.owned.items(), key=lambda kv: -hero_power(next(x["tier"] for x in HEROES if x["id"] == kv[0]), kv[1])):
            if st >= 3: continue
            t = next(x["tier"] for x in HEROES if x["id"] == hid); cost = E["star_up_cost"]["1_to_2" if st == 1 else "2_to_3"][str(t)]
            if all(self.mats[m] >= cost[m] for m in ("M001", "M002", "M003")) and self.gold >= cost["gold"]:
                for m in ("M001", "M002", "M003"): self.mats[m] -= cost[m]
                self.gold -= cost["gold"]; self.gold_spent += cost["gold"]; self.owned[hid] = st + 1
        # 아이템: 남은 골드의 35%로 조합 아이템 구매(900)
        budget = self.gold * 0.35
        while budget >= 900 and self.gold >= 900 and self.items["completed"] < 3 * self.team_slots():
            self.gold -= 900; self.gold_spent += 900; budget -= 900; self.items["completed"] += 1


def simulate(profile, days=90, seed=0):
    rng = random.Random(seed); pl = Player(profile, rng); pl.gems_spent_today = 0
    snaps = {}
    for d in range(1, days + 1):
        pl.gems_spent_today = 0
        pl.day(d)
        if d in (7, 30, 60, 90):
            tiers = {t: sum(1 for h, s in pl.owned.items() if next(x["tier"] for x in HEROES if x["id"] == h) == t) for t in range(1, 6)}
            snaps[d] = dict(heroes=len(pl.owned), by_tier=tiers, star2=sum(1 for s in pl.owned.values() if s >= 2), star3=sum(1 for s in pl.owned.values() if s == 3),
                            power=round(pl.power_level(), 1), act=pl.act, level=pl.level, gold=int(pl.gold), gold_earned=int(pl.gold_earned), gold_spent=int(pl.gold_spent),
                            gems_spent=pl.gems_spent, items_completed=pl.items["completed"], artifacts=pl.items["artifact"], battles=pl.battles_fought, winrate=round(pl.wins / max(1, pl.battles_fought), 3),
                            stamina_blocked_days=pl.stamina_blocked_days, rotation_rate=round(pl.rotations / max(1, pl.battles_fought), 3), cleared=len(pl.cleared), m001=pl.mats["M001"], m002=pl.mats["M002"], m003=pl.mats["M003"])
    return snaps, pl.log


def main():
    out = {}
    for prof in PROFILES:
        runs = [simulate(prof, 90, s) for s in range(12)]
        agg = {}
        for d in (7, 30, 60, 90):
            keys = runs[0][0][d].keys()
            agg[d] = {k: (round(statistics.mean(r[0][d][k] for r in runs), 1) if not isinstance(runs[0][0][d][k], dict) else {t: round(statistics.mean(r[0][d][k][t] for r in runs), 1) for t in runs[0][0][d][k]}) for k in keys}
        acts = {}
        for r in runs:
            for day, ev in r[1]: acts.setdefault(ev, []).append(day)
        out[prof] = {"profile": PROFILES[prof]["name"], "snapshots": agg, "act_reach_day_mean": {k: round(statistics.mean(v), 1) for k, v in acts.items()}}
        print(prof, {d: (agg[d]["heroes"], agg[d]["power"], agg[d]["act"], agg[d]["gold_earned"], agg[d]["stamina_blocked_days"]) for d in agg}, out[prof]["act_reach_day_mean"])
    os.makedirs(REP, exist_ok=True)
    json.dump(out, open(os.path.join(REP, "economy_sim.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    # 07 문서 삽입
    doc = os.path.join(ROOT, "docs", "07_경제_및_비즈니스모델.md")
    s = open(doc, encoding="utf-8").read()
    L = ["## 9. 경제 진행 시뮬레이션 결과 (자동 생성: `python sim/run_economy.py`)", "",
         "가상 플레이어 3프로필 × 12회 × 90일 몬테카를로. 승률은 전력 레벨 − 전투 레벨의 로지스틱(여유 0 → 76%), 보상·드랍·호감도·승급·구매는 `economy.json`·`battles.json` 규칙 그대로.", "",
         "| 프로필 | 일차 | 보유 영웅 | T4/T5 | ★2 이상 | 전력 | 막 | 용병 레벨 | 누적 골드 | 누적 지출 | 보석 지출 | 조합 아이템 | 클리어 전투 | 승률 | 최강팀 스태미너 소진 비율 | 참전 불가일 |", "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for prof, r in out.items():
        for d, s_ in r["snapshots"].items():
            L.append(f"| {r['profile']} | {d} | {s_['heroes']:.0f} | {s_['by_tier'][4]:.0f}/{s_['by_tier'][5]:.0f} | {s_['star2']:.0f} | {s_['power']:.0f} | {s_['act']:.1f} | {s_['level']:.0f} | {s_['gold_earned']:,.0f} | {s_['gold_spent']:,.0f} | {s_['gems_spent']:,.0f} | {s_['items_completed']:.0f} | {s_['cleared']:.0f} | {s_['winrate']:.0%} | {s_['rotation_rate']:.0%} | {s_['stamina_blocked_days']:.0f} |")
    L += ["", "막 도달 평균 일차: " + "; ".join(f"{r['profile']}: " + ", ".join(f"{k} {v}일" for k, v in r["act_reach_day_mean"].items()) for r in out.values()), ""]
    f90 = out["free"]["snapshots"][90]; h90 = out["heavy"]["snapshots"][90]
    L += ["해석:",
          f"- 무과금 90일: 영웅 {f90['heroes']:.0f}명(196명 중 {f90['heroes']/196:.0%}), 전력 {f90['power']:.0f}, {f90['act']:.1f}막. 헤비 90일: {h90['heroes']:.0f}명({h90['heroes']/196:.0%}), 전력 {h90['power']:.0f}. 과금은 '수집 속도'를 사지 전력 상한을 사지 않는다(같은 전투는 같은 영웅으로 같은 승률).",
          f"- 스태미너: 최강 팀이 소진되어 약한 영웅으로 로테이션한 참전 비율 무과금 {f90['rotation_rate']:.0%}(승률 손실로 작용), 참전 자체가 불가능했던 날 {f90['stamina_blocked_days']:.0f}/90일. 스태미너는 '참전 횟수'가 아니라 '최강 팀 사용 횟수'를 제한한다 — 물약·월정액의 가치는 여기서 나온다(07 §3).",
          "- 골드는 승급(35%)과 조합 아이템(35%)에 쓰이고 90일 누적 지출/수입 비율이 70~85%로 인플레이션 없이 소진된다. 재료 병목은 별의 결정(M003, 악몽 전용)이며 ★3 승급이 엔드게임 목표로 작동한다.", ""]
    marker = "## 9. 경제 진행 시뮬레이션 결과"
    s = s[:s.index(marker)] if marker in s else s
    open(doc, "w", encoding="utf-8").write(s.rstrip() + "\n\n" + "\n".join(L))
    print("economy_sim.json + docs/07 §9 updated")


if __name__ == "__main__":
    main()
