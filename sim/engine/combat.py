# -*- coding: utf-8 -*-
"""
결정론적 자동전투 엔진 (TFT 규칙). 헥스 8×7, 틱 0.05초, 30초 + 연장 15초.
"""
import math, random
from .hexgrid import COLS, ROWS, hdist, hneighbors, cells_within, ALL_CELLS

DT = 0.05
TIME_LIMIT = 30.0
OVERTIME = 15.0
MOVE_INTERVAL = 0.5
CAST_TIME = 0.3
MANA_PER_ATTACK = 10
MANA_HIT_CAP = 42.5


class Unit:
    __slots__ = ("uid", "team", "name", "hid", "cls", "origin", "tier", "star", "is_summon", "is_turret", "is_structure", "no_attack",
                 "max_hp", "hp", "ad_base", "as_base", "armor_base", "mr_base", "range_base", "mana", "mana_max", "mana_start",
                 "crit_base", "crit_dmg_base", "ap_base", "skill", "skill_mult", "items",
                 "mod", "buffs", "dirty", "e_ad", "e_as", "e_armor", "e_mr", "e_range", "e_ap", "e_crit", "e_crit_dmg", "e_omnivamp", "e_dur", "e_dmg_amp", "e_heal_recv", "e_magic_dr",
                 "shields", "stun_until", "root_until", "cc_immune_until", "taunt_by", "taunt_until", "next_attack", "cast_until", "next_move",
                 "pos", "target", "alive", "lifetime_until", "hooks", "state", "stats", "empowered", "attack_count", "dots", "stasis_until", "front", "summons", "spawned_by", "dead_time", "death_cancel_used", "regen_pct", "mana_regen", "mana_on_attack", "move_cd")

    def __init__(self, uid, team, spec, rng):
        self.uid = uid; self.team = team
        self.name = spec["name"]; self.hid = spec["id"]; self.cls = spec["class"]; self.origin = spec["origin"]
        self.tier = spec["tier"]; self.star = spec["star"]
        self.is_summon = spec.get("is_summon", False); self.is_turret = spec.get("is_turret", False)
        self.is_structure = spec.get("is_structure", False); self.no_attack = spec.get("no_attack", False)
        self.max_hp = float(spec["hp"]); self.hp = self.max_hp
        self.ad_base = float(spec["ad"]); self.as_base = float(spec["attack_speed"])
        self.armor_base = float(spec["armor"]); self.mr_base = float(spec["mr"]); self.range_base = int(spec["range"])
        self.mana_start = float(spec["mana_start"]); self.mana_max = float(spec["mana_max"]); self.mana = self.mana_start
        self.crit_base = float(spec["crit_chance"]); self.crit_dmg_base = float(spec["crit_damage"]); self.ap_base = float(spec["ap"])
        self.skill = spec.get("skill"); self.skill_mult = spec.get("skill_mult", 1.0)
        self.items = spec.get("items", [])
        # 정적 수정치 (아이템/특성)
        self.mod = dict(ad_pct=0.0, ad_flat=0.0, ap=0.0, hp=0.0, hp_pct=0.0, armor=0.0, mr=0.0, as_pct=0.0, mana=0.0, crit=0.0, crit_dmg=0.0,
                        omnivamp=0.0, durability=0.0, range=0, dmg_amp=0.0, heal_recv=0.0, magic_dr=0.0, armor_shred=0.0, mr_shred=0.0, skill_dmg=0.0)
        self.buffs = []  # [stat, value, until]
        self.dirty = True
        self.shields = []  # [amount, until]
        self.stun_until = 0.0; self.root_until = 0.0; self.cc_immune_until = 0.0; self.taunt_by = None; self.taunt_until = 0.0
        self.next_attack = 0.0; self.cast_until = 0.0; self.next_move = 0.0; self.move_cd = MOVE_INTERVAL
        self.pos = None; self.target = None; self.alive = True; self.lifetime_until = spec.get("lifetime_until", 1e9)
        self.hooks = {}; self.state = {}
        self.stats = dict(dmg=0.0, taken=0.0, heal=0.0, kills=0, casts=0, mitigated=0.0)
        self.empowered = 0; self.attack_count = 0; self.dots = []  # [dps, until, src, kind]
        self.stasis_until = 0.0; self.front = False; self.summons = []; self.spawned_by = spec.get("spawned_by"); self.dead_time = None
        self.death_cancel_used = False; self.regen_pct = 0.0; self.mana_regen = 0.0; self.mana_on_attack = 0.0

    # ── 훅 등록
    def on(self, event, fn, params=None):
        self.hooks.setdefault(event, []).append((fn, params or {}))

    def fire(self, battle, event, *args):
        hs = self.hooks.get(event)
        if not hs: return None
        res = None
        for fn, params in hs:
            r = fn(battle, self, params, *args)
            if r is not None: res = r
        return res

    # ── 능력치
    def add_buff(self, stat, value, until):
        self.buffs.append([stat, value, until]); self.dirty = True

    def expire(self, t):
        if self.buffs:
            n = len(self.buffs)
            self.buffs = [b for b in self.buffs if b[2] > t]
            if len(self.buffs) != n: self.dirty = True
        if self.shields:
            self.shields = [s for s in self.shields if s[1] > t and s[0] > 0]
        if self.dirty: self.recalc()

    def recalc(self):
        m = self.mod
        b = {}
        for stat, v, _ in self.buffs:
            b[stat] = b.get(stat, 0.0) + v
        ad_pct = m["ad_pct"] + b.get("ad_pct", 0.0)
        self.e_ad = (self.ad_base + m["ad_flat"]) * (1 + ad_pct / 100.0)
        self.e_as = min(5.0, self.as_base * (1 + (m["as_pct"] + b.get("as_pct", 0.0)) / 100.0))
        self.e_armor = max(0.0, (self.armor_base + m["armor"] + b.get("armor", 0.0)) * (1 - min(0.9, (m["armor_shred"] + b.get("armor_shred", 0.0)) / 100.0)))
        self.e_mr = max(0.0, (self.mr_base + m["mr"] + b.get("mr", 0.0)) * (1 - min(0.9, (m["mr_shred"] + b.get("mr_shred", 0.0)) / 100.0)))
        self.e_range = self.range_base + m["range"] + int(b.get("range", 0))
        self.e_ap = self.ap_base + m["ap"] + b.get("ap", 0.0)
        self.e_crit = min(100.0, self.crit_base + m["crit"] + b.get("crit", 0.0))
        self.e_crit_dmg = self.crit_dmg_base + m["crit_dmg"] + b.get("crit_dmg", 0.0)
        self.e_omnivamp = m["omnivamp"] + b.get("omnivamp", 0.0)
        self.e_dur = min(80.0, m["durability"] + b.get("durability", 0.0))
        self.e_dmg_amp = m["dmg_amp"] + b.get("dmg_amp", 0.0)
        self.e_heal_recv = m["heal_recv"] + b.get("heal_recv", 0.0)
        self.e_magic_dr = m["magic_dr"] + b.get("magic_dr", 0.0)
        self.dirty = False

    def shield_total(self):
        return sum(s[0] for s in self.shields)

    def add_shield(self, amount, until):
        if amount > 0: self.shields.append([amount, until])

    def hp_pct(self):
        return self.hp / self.max_hp if self.max_hp > 0 else 0.0

    def can_act(self, t):
        return self.alive and t >= self.stun_until and t >= self.stasis_until


class Battle:
    def __init__(self, data, allies, enemies, seed=0, rules=None, trait_counts=None):
        """allies/enemies: 유닛 스펙 리스트(각각 pos 옵션). rules: dict(overtime, waves 등)."""
        self.data = data
        self.rng = random.Random(seed)
        self.rules = rules or {}
        self.t = 0.0
        self.units = []
        self.occ = {}
        self.log = []
        self.winner = None
        self.uid_seq = 0
        self.team_traits = {0: {}, 1: {}}
        self.dmg_mult_global = 1.0
        self.pending_summons = []
        self.trait_counts_override = trait_counts
        self._place_team(allies, 0)
        self._place_team(enemies, 1)
        self._setup()

    # ── 배치
    def _place_team(self, specs, team):
        cols_front = [3, 2, 1, 0] if team == 0 else [4, 5, 6, 7]
        cols_back = [0, 1, 2, 3] if team == 0 else [7, 6, 5, 4]
        rows = list(range(ROWS)); self.rng.shuffle(rows)
        order = sorted(range(len(specs)), key=lambda i: (specs[i]["range"] > 1, i))  # 근접 먼저
        for i in order:
            spec = specs[i]
            u = Unit(self.uid_seq, team, spec, self.rng); self.uid_seq += 1
            pos = spec.get("pos")
            if pos is None or pos in self.occ:
                pref = cols_front if spec["range"] <= 1 else ([1, 0, 2, 3] if team == 0 else [6, 7, 5, 4])
                pos = None
                for c in pref:
                    for r in sorted(rows, key=lambda r: abs(r - 3)):
                        if (c, r) not in self.occ:
                            pos = (c, r); break
                    if pos: break
            if pos is None:
                for cell in ALL_CELLS:
                    if cell not in self.occ and ((cell[0] < 4) == (team == 0)):
                        pos = cell; break
            u.pos = pos; self.occ[pos] = u
            self.units.append(u)
        for u in self.units:
            if u.team == team:
                u.front = (u.pos[0] in (2, 3)) if team == 0 else (u.pos[0] in (4, 5))

    def _setup(self):
        from .traits import apply_traits
        from .items import apply_items
        for u in self.units:
            u.mod["mana"] = 0.0
        apply_items(self)
        apply_traits(self)
        for u in self.units:
            u.max_hp = u.max_hp * (1 + u.mod["hp_pct"] / 100.0) + u.mod["hp"]
            u.hp = u.max_hp
            u.mana_max = max(10.0, u.mana_max)
            u.mana = min(u.mana_max - 1, u.mana_start + u.mod["mana"])
            u.recalc()
            u.next_attack = self.rng.random() * 0.3
            u.next_move = 0.0
        for u in list(self.units):
            u.fire(self, "start")

    # ── 유틸
    def alive_units(self, team=None):
        return [u for u in self.units if u.alive and (team is None or u.team == team)]

    def enemies_of(self, u):
        return [e for e in self.units if e.alive and e.team != u.team]

    def allies_of(self, u, include_self=False):
        return [a for a in self.units if a.alive and a.team == u.team and (include_self or a is not u)]

    def free_cell_near(self, cell, max_r=3):
        for r in range(1, max_r + 1):
            cands = [c for c in cells_within(cell, r) if c not in self.occ and hdist(c, cell) == r]
            if cands:
                return cands[self.rng.randrange(len(cands))]
        return None

    def move_to(self, u, cell):
        if cell in self.occ: return False
        del self.occ[u.pos]; u.pos = cell; self.occ[cell] = u
        return True

    def spawn(self, owner, spec, near=None):
        cell = self.free_cell_near(near or owner.pos, 4)
        if cell is None: return None
        spec = dict(spec); spec["spawned_by"] = owner.uid
        s = Unit(self.uid_seq, owner.team, spec, self.rng); self.uid_seq += 1
        s.pos = cell; self.occ[cell] = s; s.alive = True
        s.next_attack = self.t + 0.3
        s.recalc()
        self.units.append(s); owner.summons.append(s)
        # 소환수 특성/아이템 보정
        bonus = owner.state.get("summon_bonus_pct", 0.0) if not s.is_turret else owner.state.get("turret_bonus_pct", 0.0)
        if bonus:
            s.max_hp *= 1 + bonus / 100.0; s.hp = s.max_hp; s.ad_base *= 1 + bonus / 100.0; s.dirty = True; s.recalc()
        return s

    # ── 피해/치유
    def damage(self, src, dst, amount, kind="physical", is_skill=False, can_crit=False, crit_forced=False, is_attack=False):
        if not dst.alive or amount <= 0: return 0.0
        if dst.stasis_until > self.t: return 0.0
        raw = amount
        if src is not None:
            raw *= 1 + src.e_dmg_amp / 100.0
            if is_skill: raw *= 1 + src.mod["skill_dmg"] / 100.0
            r = src.fire(self, "pre_damage", dst, raw, kind, is_skill)
            if r is not None: raw *= r
        crit = False
        if src is not None and (can_crit or (is_skill and src.state.get("spell_crit"))):
            if crit_forced or self.rng.random() * 100 < src.e_crit:
                crit = True; raw *= src.e_crit_dmg / 100.0
        pre = raw
        if kind == "physical":
            mit = raw * 100.0 / (100.0 + dst.e_armor)
        elif kind == "magic":
            mit = raw * 100.0 / (100.0 + dst.e_mr) * (1 - min(0.8, dst.e_magic_dr / 100.0))
        else:
            mit = raw
        mit *= (1 - dst.e_dur / 100.0) * self.dmg_mult_global
        dr = dst.fire(self, "pre_taken", src, mit, kind)
        if dr is not None: mit *= dr
        # 방어막
        remaining = mit
        for s in dst.shields:
            if remaining <= 0: break
            take = min(s[0], remaining); s[0] -= take; remaining -= take
        dst.hp -= remaining
        dealt = mit
        if src is not None:
            src.stats["dmg"] += dealt
            if src.e_omnivamp > 0: self.heal(src, src, dealt * src.e_omnivamp / 100.0, from_vamp=True)
            if crit: src.fire(self, "crit", dst)
            src.fire(self, "damage_dealt", dst, dealt, kind, is_skill, is_attack)
        dst.stats["taken"] += dealt; dst.stats["mitigated"] += pre - mit
        # 피격 마나
        if dst.cast_until <= self.t and dst.stun_until <= self.t:
            dst.mana = min(dst.mana_max, dst.mana + min(MANA_HIT_CAP, pre * 0.01 + mit * 0.07))
        dst.fire(self, "damaged", src, dealt, kind, is_attack)
        if dst.hp <= 0: self.kill(dst, src)
        return dealt

    def heal(self, src, dst, amount, from_vamp=False):
        if not dst.alive or amount <= 0: return 0.0
        amount *= 1 + dst.e_heal_recv / 100.0
        if dst.state.get("grievous_until", 0) > self.t: amount *= 1 - dst.state.get("grievous_pct", 33) / 100.0
        if src is not None and src is not dst and src.state.get("heal_power"):
            amount *= 1 + src.state["heal_power"] / 100.0
        missing = dst.max_hp - dst.hp
        healed = min(missing, amount)
        dst.hp += healed
        over = amount - healed
        if over > 0 and dst.state.get("overheal_shield_pct"):
            cap = dst.max_hp * dst.state["overheal_shield_pct"] / 100.0
            cur = dst.shield_total()
            if cur < cap: dst.add_shield(min(over, cap - cur), self.t + 5)
        if src is not None: src.stats["heal"] += healed
        return healed

    def kill(self, u, killer):
        if not u.alive: return
        if not u.death_cancel_used:
            r = u.fire(self, "death", killer)
            if r == "cancel":
                u.death_cancel_used = True
                return
        u.alive = False; u.dead_time = self.t
        if u.pos in self.occ and self.occ[u.pos] is u: del self.occ[u.pos]
        if killer is not None and killer.alive:
            killer.stats["kills"] += 1
            killer.fire(self, "kill", u)
            if killer.spawned_by is not None:
                owner = self.unit_by_uid(killer.spawned_by)
                if owner is not None and owner.alive: owner.fire(self, "kill", u)
        u.fire(self, "died", killer)
        for e in self.units:
            if e.target is u: e.target = None

    def unit_by_uid(self, uid):
        for u in self.units:
            if u.uid == uid: return u
        return None

    # ── CC
    def stun(self, u, dur):
        if u.cc_immune_until > self.t or u.is_structure: return
        u.stun_until = max(u.stun_until, self.t + dur)

    def slow(self, u, pct, dur):
        if u.cc_immune_until > self.t: return
        u.add_buff("as_pct", -pct, self.t + dur)

    def shred(self, u, pct, dur, mr=True):
        u.add_buff("armor_shred", pct, self.t + dur)
        if mr: u.add_buff("mr_shred", pct, self.t + dur)

    # ── 타겟팅
    def acquire(self, u):
        if u.taunt_by is not None and u.taunt_until > self.t and u.taunt_by.alive:
            u.target = u.taunt_by; return
        enemies = self.enemies_of(u)
        if not enemies: u.target = None; return
        best = None; bd = 1e9
        for e in enemies:
            d = hdist(u.pos, e.pos)
            if e.is_structure and not e.state.get("priority"): d += 0.5
            if e.state.get("escort_priority"): d -= 0.75
            if d < bd or (d == bd and e.hp < best.hp): best = e; bd = d
        u.target = best

    def step_unit(self, u):
        t = self.t
        if not u.alive: return
        if u.lifetime_until <= t:
            u.alive = False; u.dead_time = t
            if self.occ.get(u.pos) is u: del self.occ[u.pos]
            for e in self.units:
                if e.target is u: e.target = None
            return
        u.expire(t)
        if u.is_structure or u.no_attack: return
        if not u.can_act(t): return
        if u.cast_until > t: return
        if u.target is None or not u.target.alive or (u.taunt_by is not None and u.taunt_until > t and u.taunt_by.alive and u.target is not u.taunt_by):
            self.acquire(u)
        if u.target is None: return
        tgt = u.target
        d = hdist(u.pos, tgt.pos)
        if d > u.e_range:
            if u.mana >= u.mana_max and u.skill is not None and u.skill.get("archetype") and u.skill["params"].get("kind") not in ("damage", "dot", "empower"):
                self.cast(u)
                return
            if u.is_turret or u.root_until > t: return
            if t >= u.next_move:
                # 타겟 재검토: 더 가까운 적이 있으면 교체
                best = None; bd = d
                for e in self.enemies_of(u):
                    dd = hdist(u.pos, e.pos)
                    if dd < bd: best = e; bd = dd
                if best is not None and (u.taunt_by is None or u.taunt_until <= t): u.target = tgt = best; d = bd
                if d > u.e_range:
                    cands = [c for c in hneighbors(u.pos) if c not in self.occ]
                    if cands:
                        cands.sort(key=lambda c: (hdist(c, tgt.pos), self.rng.random()))
                        if hdist(cands[0], tgt.pos) < d: self.move_to(u, cands[0])
                    u.next_move = t + u.move_cd
            return
        # 사거리 내: 스킬 우선
        if u.mana >= u.mana_max and u.skill is not None and u.skill.get("archetype"):
            self.cast(u)
            return
        if t >= u.next_attack:
            self.attack(u, tgt)
            u.next_attack = t + 1.0 / max(0.1, u.e_as)

    def attack(self, u, tgt):
        u.attack_count += 1
        dmg = u.e_ad
        bonus_phys = 0.0
        if u.empowered > 0:
            u.empowered -= 1
            p = u.state.get("empower")
            if p: bonus_phys = p[0] * u.e_ad + p[1]
        self.damage(u, tgt, dmg + bonus_phys, "physical", can_crit=True, is_attack=True)
        if not u.alive: return
        gain = MANA_PER_ATTACK + u.mana_on_attack
        if u.cast_until <= self.t: u.mana = min(u.mana_max, u.mana + gain)
        u.fire(self, "attack", tgt)

    # ── 스킬
    def cast(self, u):
        from .abilities import cast_ability
        u.mana = 0.0
        u.cast_until = self.t + CAST_TIME
        u.stats["casts"] += 1
        cast_ability(self, u)
        u.fire(self, "cast")
        u.mana = min(u.mana_max, u.mana + u.state.pop("mana_refund", 0.0))

    # ── 메인 루프
    def run(self, max_time=None):
        limit = TIME_LIMIT if max_time is None else max_time
        last_sec = -1
        while True:
            self.t += DT
            t = self.t
            if t > limit:
                self.dmg_mult_global = 1.0 + 0.5 * (t - limit)
            sec = int(t)
            tick1s = sec != last_sec
            last_sec = sec
            for u in self.units:
                if not u.alive: continue
                self.step_unit(u)
            if tick1s:
                for u in self.units:
                    if not u.alive: continue
                    if u.regen_pct: self.heal(u, u, u.max_hp * u.regen_pct / 100.0)
                    if u.mana_regen and u.cast_until <= t: u.mana = min(u.mana_max, u.mana + u.mana_regen)
                    if u.dots:
                        for d in list(u.dots):
                            if d[1] <= t: u.dots.remove(d); continue
                            src = d[2]
                            self.damage(src if (src is not None and src.alive) else None, u, d[0], d[3], is_skill=True)
                        if not u.alive: continue
                    u.fire(self, "tick1s")
            a = any(u.alive and not u.is_structure and not u.no_attack for u in self.units if u.team == 0)
            b = any(u.alive and not u.is_structure and not u.no_attack for u in self.units if u.team == 1)
            must = [u for u in self.units if u.state.get("must_survive")]
            lost = any(not u.alive for u in must)
            if lost: self.winner = 1 if any(u.team == 0 for u in must if not u.alive) else 0; break
            if self.rules.get("assassination") and not any(u.alive for u in self.units if u.state.get("commander")):
                self.winner = 0; break
            if self.rules.get("escape") and t >= 30.0 and a:
                self.winner = 0; break
            if not a and not b: self.winner = -1; break
            if not a: self.winner = 1; break
            if not b: self.winner = 0; break
            if t >= limit + OVERTIME:
                ha = sum(u.hp_pct() for u in self.units if u.alive and u.team == 0)
                hb = sum(u.hp_pct() for u in self.units if u.alive and u.team == 1)
                self.winner = 0 if ha > hb else 1
                break
        return self.result()

    def result(self):
        return {"winner": self.winner, "time": round(self.t, 2),
                "units": [{"uid": u.uid, "team": u.team, "id": u.hid, "name": u.name, "alive": u.alive, "hp": round(max(0, u.hp)), "max_hp": round(u.max_hp),
                           "is_summon": u.is_summon or u.is_turret, "stats": {k: round(v) for k, v in u.stats.items()}} for u in self.units]}


def run_battle(data, allies, enemies, seed=0, rules=None):
    return Battle(data, allies, enemies, seed, rules).run()
