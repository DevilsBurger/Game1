# -*- coding: utf-8 -*-
"""아이템 능력치/훅 구현."""
from .hexgrid import hdist
from .hooks import summon_spec_from

STAT_MAP = {"ad_pct": "ad_pct", "ap": "ap", "hp": "hp", "armor": "armor", "mr": "mr", "as_pct": "as_pct", "mana": "mana", "crit": "crit",
            "omnivamp": "omnivamp", "durability": "durability"}


def apply_items(b, only_units=None):
    data = b.data
    # 그란두르 item_mult은 traits 적용 전이므로 출신 카운트로 선계산
    for team in (0, 1):
        units = [u for u in (only_units if only_units is not None else b.units) if u.team == team and not u.is_summon]
        gcount = len({u.hid for u in units if u.origin == "grandur"})
        gl = 0
        for i, th in enumerate(data.origins["grandur"]["thresholds"]):
            if gcount >= th: gl = i + 1
        gmult = data.origins["grandur"]["effects"]["item_mult"][gl - 1] if gl else 1.0
        for u in units:
            for it in u.items:
                if it is None: continue
                mult = (gmult if u.origin == "grandur" else 1.0) * it.get("balance", {}).get("mult", 1.0)
                for k, v in it.get("stats", {}).items():
                    if k in STAT_MAP: u.mod[STAT_MAP[k]] += v * mult
                for h in it.get("hooks", []):
                    fn = HOOKS.get(h["type"])
                    if fn: fn(b, u, dict(h.get("params", {})), mult)
    # 오라(아군) 적용: 시작 배치 기준
    for u in (only_units if only_units is not None else b.units):
        for aura in u.state.pop("auras", []):
            r = aura.get("radius", 1)
            for a in b.units:
                if a.team != u.team or a is u or a.is_summon: continue
                if r >= 9 or hdist(a.pos, u.pos) <= r:
                    _apply_aura(b, a, aura)


def _apply_aura(b, a, aura):
    for k, v in aura.items():
        if k == "radius": continue
        if k in STAT_MAP: a.mod[STAT_MAP[k]] += v
        elif k == "hp_pct": a.mod["hp_pct"] += v
        elif k == "crit_dmg": a.mod["crit_dmg"] += v
        elif k == "range": a.mod["range"] += v
        elif k == "regen_pct": a.regen_pct += v
        elif k == "mana_regen": a.mana_regen += v
        elif k == "start_mana": a.mod["mana"] += v
        elif k == "start_shield_pct": a.on("start", lambda b, u, p: u.add_shield(u.max_hp * p["pct"] / 100.0, b.t + 8), {"pct": v})
        elif k == "thorns": a.on("damaged", _thorns, {"pct": v})
        elif k == "dash_dmg_pct": a.state["dash_dmg_pct"] = a.state.get("dash_dmg_pct", 0) + v
        elif k == "heal_pct": a.mod["heal_recv"] += v
        elif k == "summon_stat_pct": a.state["summon_bonus_pct"] = a.state.get("summon_bonus_pct", 0) + v
        elif k == "turret_stat_pct": a.state["turret_bonus_pct"] = a.state.get("turret_bonus_pct", 0) + v
        elif k == "start_as_pct": a.on("start", lambda b, u, p: u.add_buff("as_pct", p["v"], b.t + p["d"]), {"v": v, "d": aura.get("start_as_dur", 6)})
        elif k == "structure_dmg_pct": a.mod["structure_dmg"] += v
        elif k == "heal_on_wave_pct": a.on("wave_end", lambda b, u, p: b.heal(u, u, u.max_hp * p["pct"] / 100.0), {"pct": v})


# ── 훅 구현. 시그니처: fn(b, u, params, mult)
def h_stack_ad_on_kill(b, u, p, m):
    def on_kill(b, u, p, victim):
        if u.state.get("sk", 0) < p["max"]:
            u.state["sk"] = u.state.get("sk", 0) + 1; u.add_buff("ad_pct", p["pct"] * p["m"], 1e9)
    u.on("kill", on_kill, {"pct": p["pct"], "max": p["max"], "m": m})


def h_giant_slayer(b, u, p, m):
    def pre(b, u, p, dst, raw, kind, is_skill):
        return 1 + p["bonus_pct"] * p["m"] / 100.0 if dst.max_hp >= p["hp_threshold"] else None
    u.on("pre_damage", pre, {"hp_threshold": p["hp_threshold"], "bonus_pct": p["bonus_pct"], "m": m})


def h_low_hp_shield(b, u, p, m):
    def on_dmg(b, u, p, src, amt, kind, is_attack):
        if not u.state.get("lhs") and u.hp_pct() <= p["threshold"] / 100.0:
            u.state["lhs"] = True
            u.add_shield(u.max_hp * p["shield_pct"] * p["m"] / 100.0, b.t + p["duration"])
            if p.get("ad_pct"): u.add_buff("ad_pct", p["ad_pct"] * p["m"], b.t + p["duration"])
            if p.get("def"): u.add_buff("armor", p["def"] * p["m"], b.t + p["duration"]); u.add_buff("mr", p["def"] * p["m"], b.t + p["duration"])
    u.on("damaged", on_dmg, dict(p, m=m))


def h_shred_on_hit(b, u, p, m):
    u.on("attack", lambda b, u, p, tgt: tgt.alive and b.shred(tgt, p["pct"] * p["m"], p["duration"], mr=False), dict(p, m=m))


def h_omnivamp_bonus(b, u, p, m): u.mod["omnivamp"] += p["pct"] * m


def h_aoe_on_attack(b, u, p, m):
    def on_attack(b, u, p, tgt):
        others = sorted([e for e in b.enemies_of(u) if e is not tgt and hdist(e.pos, tgt.pos) <= 1], key=lambda e: e.hp)
        for e in others[:p["targets"]]: b.damage(u, e, u.e_ad * p["ad_ratio"] * p["m"], "physical")
    u.on("attack", on_attack, dict(p, m=m))


def h_mana_on_attack(b, u, p, m): u.mana_on_attack += p["mana"] * m


def h_crit_dmg_bonus(b, u, p, m): u.mod["crit_dmg"] += p["pct"] * m


def h_heal_on_kill(b, u, p, m):
    u.on("kill", lambda b, u, p, v: b.heal(u, u, u.max_hp * p["pct"] * p["m"] / 100.0), dict(p, m=m))


def h_start_shield(b, u, p, m):
    u.on("start", lambda b, u, p: u.add_shield(u.max_hp * p["pct"] * p["m"] / 100.0, b.t + p["duration"]), dict(p, m=m))


def h_burn_on_hit(b, u, p, m):
    def on_dd(b, u, p, dst, amt, kind, is_skill, is_attack):
        if not dst.alive: return
        dps = dst.max_hp * p["pct_per_sec"] * p["m"] / 100.0
        for d in dst.dots:
            if d[2] is u and d[3] == "true":
                d[0] = max(d[0], dps); d[1] = b.t + p["duration"]; break
        else:
            dst.dots.append([dps, b.t + p["duration"], u, "true"])
        dst.state["grievous_until"] = b.t + p["duration"]; dst.state["grievous_pct"] = p.get("grievous", 33)
    u.on("damage_dealt", on_dd, dict(p, m=m))


def h_shield_on_cast(b, u, p, m):
    u.on("cast", lambda b, u, p: u.add_shield(u.max_hp * p["pct"] * p["m"] / 100.0, b.t + p["duration"]), dict(p, m=m))


def h_as_stack_on_attack(b, u, p, m):
    def on_attack(b, u, p, tgt):
        if u.state.get("asst", 0) < p["max"]:
            u.state["asst"] = u.state.get("asst", 0) + 1; u.add_buff("as_pct", p["pct"] * p["m"], 1e9)
    u.on("attack", on_attack, dict(p, m=m))


def h_mana_refund_on_cast(b, u, p, m):
    u.on("cast", lambda b, u, p: u.state.__setitem__("mana_refund", u.state.get("mana_refund", 0) + p["mana"] * p["m"]), dict(p, m=m))


def h_spell_crit(b, u, p, m): u.state["spell_crit"] = True


def h_burn_aura(b, u, p, m):
    def tick(b, u, p):
        for e in b.enemies_of(u):
            if hdist(e.pos, u.pos) <= p["radius"]:
                b.damage(u, e, e.max_hp * p["pct_per_sec"] * p["m"] / 100.0, "true", is_skill=True)
                e.state["grievous_until"] = b.t + 2; e.state["grievous_pct"] = p.get("grievous", 33)
    u.on("tick1s", tick, dict(p, m=m))


def h_as_slow_aura(b, u, p, m):
    def tick(b, u, p):
        for e in b.enemies_of(u):
            if hdist(e.pos, u.pos) <= p["radius"]: b.slow(e, p["pct"] * p["m"], 1.1)
    u.on("tick1s", tick, dict(p, m=m))


def h_stack_on_hit(b, u, p, m):
    def stack(b, u, p, *a):
        if u.state.get("titan", 0) < p["max"]:
            u.state["titan"] = u.state.get("titan", 0) + 1
            if p.get("ad_pct"): u.add_buff("ad_pct", p["ad_pct"] * p["m"], 1e9)
            if p.get("ap"): u.add_buff("ap", p["ap"] * p["m"], 1e9)
            if p.get("armor"): u.add_buff("armor", p["armor"] * p["m"], 1e9)
            if u.state["titan"] == p["max"] and p.get("max_bonus_def"):
                u.add_buff("armor", p["max_bonus_def"], 1e9); u.add_buff("mr", p["max_bonus_def"], 1e9)
    u.on("attack", stack, dict(p, m=m)); u.on("damaged", stack, dict(p, m=m))


def h_heal_allies_timer(b, u, p, m):
    def tick(b, u, p):
        if b.t < p["delay"]: return
        if int(b.t - p["delay"]) % p["interval"] != 0: return
        for a in b.allies_of(u, include_self=True):
            if p["radius"] >= 9 or hdist(a.pos, u.pos) <= p["radius"]:
                b.heal(u, a, (a.max_hp - a.hp) * p["missing_pct"] * p["m"] / 100.0)
    u.on("tick1s", tick, dict(p, m=m))


def _thorns(b, u, p, src, amt, kind, is_attack):
    if src is not None and src.alive and kind == "physical" and src is not u:
        b.damage(None, src, amt * p["pct"] / 100.0, "magic")


def h_thorns(b, u, p, m): u.on("damaged", _thorns, {"pct": p["pct"] * m})


def h_gargoyle(b, u, p, m):
    def tick(b, u, p):
        n = sum(1 for e in b.enemies_of(u) if e.target is u)
        u.buffs = [x for x in u.buffs if x[0] != "garg_armor" and x[0] != "garg_mr"]
        u.add_buff("armor", n * p["per_enemy"] * p["m"], b.t + 1.1); u.add_buff("mr", n * p["per_enemy"] * p["m"], b.t + 1.1)
    u.on("tick1s", tick, dict(p, m=m))


def h_shred_on_crit(b, u, p, m):
    u.on("crit", lambda b, u, p, tgt: tgt.alive and b.shred(tgt, p["pct"] * p["m"], p["duration"], mr=False), dict(p, m=m))


def h_magic_dr(b, u, p, m): u.mod["magic_dr"] += p["pct"] * m


def h_shock_every_n(b, u, p, m):
    def on_attack(b, u, p, tgt):
        if u.attack_count % p["n"] == 0:
            es = sorted(b.enemies_of(u), key=lambda e: hdist(e.pos, tgt.pos))[:p["targets"]]
            for e in es:
                b.damage(u, e, p["dmg"] * p["m"] * (u.e_ap / 100.0), "magic", is_skill=True)
                if p.get("mr_shred") and e.alive: e.add_buff("mr_shred", p["mr_shred"], b.t + p.get("duration", 4))
    u.on("attack", on_attack, dict(p, m=m))


def h_cast_mana_allies(b, u, p, m):
    def on_cast(b, u, p):
        for a in b.allies_of(u):
            if p["radius"] >= 9 or hdist(a.pos, u.pos) <= p["radius"]: a.mana = min(a.mana_max, a.mana + p["mana"] * p["m"])
    u.on("cast", on_cast, dict(p, m=m))


def h_cc_immune(b, u, p, m): u.on("start", lambda b, u, p: setattr(u, "cc_immune_until", b.t + p["duration"]), p)


def h_extra_range(b, u, p, m): u.mod["range"] += p["range"]


def h_ap_stack_timer(b, u, p, m):
    u.on("tick1s", lambda b, u, p: (int(b.t) % p["interval"] == 0 and int(b.t) > 0) and u.add_buff("ap", p["ap"] * p["m"], 1e9), dict(p, m=m))


def h_hand_of_justice(b, u, p, m):
    u.mod["dmg_amp"] += p["dmg_pct"] * m; u.mod["omnivamp"] += p["omnivamp"] * m


def h_mana_on_kill(b, u, p, m):
    u.on("kill", lambda b, u, p, v: setattr(u, "mana", min(u.mana_max, u.mana + p["mana"] * p["m"])), dict(p, m=m))


def h_mana_regen(b, u, p, m): u.mana_regen += p["per_sec"] * m


def h_random_items(b, u, p, m):
    pool = [it for it in b.data.items.values() if it["category"] == "completed"]
    for _ in range(p["count"]):
        it = pool[b.rng.randrange(len(pool))]
        for k, v in it.get("stats", {}).items():
            if k in STAT_MAP: u.mod[STAT_MAP[k]] += v * m


def h_shield_on_crit(b, u, p, m):
    u.on("crit", lambda b, u, p, tgt: u.add_shield(u.max_hp * p["pct"] * p["m"] / 100.0, b.t + p["duration"]), dict(p, m=m))


def h_overheal_shield(b, u, p, m): u.state["overheal_shield_pct"] = p["max_pct"] * m


def h_revive(b, u, p, m):
    def on_death(b, u, p, killer):
        if u.state.get("revived"): return None
        u.state["revived"] = True
        u.hp = u.max_hp * p["hp_pct"] * p["m"] / 100.0; u.stasis_until = b.t + 1.0; u.mana = u.mana_start
        u.fire(b, "revived")
        return "cancel"
    u.on("death", on_death, dict(p, m=m))


def h_heal_on_revive_allies(b, u, p, m):
    u.on("revived", lambda b, u, p: [b.heal(u, a, a.max_hp * p["pct"] / 100.0) for a in b.allies_of(u)], p)


def h_aura_allies(b, u, p, m):
    a = dict(p)
    for k in list(a.keys()):
        if k != "radius" and isinstance(a[k], (int, float)): a[k] = a[k] * m
    u.state.setdefault("auras", []).append(a)


def h_aura_enemies(b, u, p, m):
    def tick(b, u, p):
        for e in b.enemies_of(u):
            if hdist(e.pos, u.pos) <= p["radius"]:
                if p.get("armor"): e.add_buff("armor", p["armor"] * p["m"], b.t + 1.1)
                if p.get("mr"): e.add_buff("mr", p["mr"] * p["m"], b.t + 1.1)
    u.on("tick1s", tick, dict(p, m=m))


def h_regen(b, u, p, m): u.regen_pct += p["pct_per_sec"] * m


def h_kill_explode(b, u, p, m):
    def on_kill(b, u, p, v):
        for e in b.enemies_of(u):
            if hdist(e.pos, v.pos) <= p["radius"]: b.damage(u, e, p["dmg"] * p["m"], "magic", is_skill=True)
    u.on("kill", on_kill, dict(p, m=m))


def h_execute_low(b, u, p, m):
    def on_dd(b, u, p, dst, amt, kind, is_skill, is_attack):
        # 재진입 방지(처형 피해 자체가 damage_dealt를 다시 발생시킴) + 방어막 포함 즉사
        if u.state.get("executing"): return
        if dst.alive and dst.hp_pct() <= p["threshold"] / 100.0 and not dst.is_structure and dst.stasis_until <= b.t:
            u.state["executing"] = True
            try:
                b.damage(u, dst, dst.hp + dst.shield_total() + 1, "true")
            finally:
                u.state["executing"] = False
    u.on("damage_dealt", on_dd, p)


def h_dodge(b, u, p, m):
    def pre(b, u, p, src, mit, kind):
        return 0.0 if (kind == "physical" and src is not None and b.rng.random() * 100 < p["pct"] * p["m"]) else None
    u.on("pre_taken", pre, dict(p, m=m))


def h_true_dmg_on_cast(b, u, p, m): u.state["true_dmg_pct"] = u.state.get("true_dmg_pct", 0) + p["pct"] * m


def h_heal_on_cast_allies(b, u, p, m):
    u.on("cast", lambda b, u, p: [b.heal(u, a, a.max_hp * p["pct"] * p["m"] / 100.0) for a in b.allies_of(u, include_self=True)], dict(p, m=m))


def h_summon_on_kill(b, u, p, m):
    def on_kill(b, u, p, v):
        if sum(1 for s in u.summons if s.alive) >= p["max"]: return
        b.spawn(u, summon_spec_from(u, p["hp_pct"] * p["m"], p["ad_pct"] * p["m"], name="망령", lifetime=12, t=b.t), near=v.pos)
    u.on("kill", on_kill, dict(p, m=m))


def h_summon_on_cast(b, u, p, m):
    def on_cast(b, u, p):
        if sum(1 for s in u.summons if s.alive) >= p["max"]: return
        b.spawn(u, summon_spec_from(u, p["hp_pct"] * p["m"], p["ad_pct"] * p["m"], name="정령", lifetime=12, t=b.t))
    u.on("cast", on_cast, dict(p, m=m))


def h_first_cast_bonus(b, u, p, m):
    def pre(b, u, p, dst, raw, kind, is_skill):
        if is_skill and u.stats["casts"] == 1 and not u.state.get("fcb_done"): return 1 + p["pct"] * p["m"] / 100.0
        return None
    u.on("pre_damage", pre, dict(p, m=m))
    u.on("cast", lambda b, u, p: u.stats["casts"] >= 2 and u.state.__setitem__("fcb_done", True), {})


def h_slow_on_cast(b, u, p, m): u.state["slow_on_cast"] = (p["pct"] * m, p["duration"])


def h_stasis_low_hp(b, u, p, m):
    def on_dmg(b, u, p, src, amt, kind, is_attack):
        if not u.state.get("stasis_used") and u.hp_pct() <= p["threshold"] / 100.0:
            u.state["stasis_used"] = True; u.stasis_until = b.t + p["duration"]
    u.on("damaged", on_dmg, p)


def h_backline_jump(b, u, p, m):
    def on_start(b, u, p):
        es = b.enemies_of(u)
        if not es: return
        far = max(es, key=lambda e: hdist(e.pos, u.pos))
        from .hexgrid import hneighbors
        cands = [c for c in hneighbors(far.pos) if c not in b.occ]
        if cands: b.move_to(u, cands[0]); u.target = far
    u.on("start", on_start, {})


def h_dash_dmg_bonus(b, u, p, m): u.state["dash_dmg_pct"] = u.state.get("dash_dmg_pct", 0) + p["pct"] * m


def h_turret_stat_bonus(b, u, p, m):
    u.state["turret_bonus_pct"] = u.state.get("turret_bonus_pct", 0) + p["pct"] * m
    u.state["summon_bonus_pct"] = u.state.get("summon_bonus_pct", 0) + p["pct"] * m


def h_as_pct_penalty(b, u, p, m): u.mod["as_pct"] += p["pct"]


def h_grant_trait(b, u, p, m): u.state.setdefault("extra_traits", []).append(p["trait"])


def h_double_trait_count(b, u, p, m): u.state["double_trait"] = True


def h_noop(b, u, p, m): pass


HOOKS = {
    "stack_ad_on_kill": h_stack_ad_on_kill, "giant_slayer": h_giant_slayer, "low_hp_shield": h_low_hp_shield, "shred_on_hit": h_shred_on_hit,
    "omnivamp_bonus": h_omnivamp_bonus, "aoe_on_attack": h_aoe_on_attack, "mana_on_attack": h_mana_on_attack, "crit_dmg_bonus": h_crit_dmg_bonus,
    "heal_on_kill": h_heal_on_kill, "start_shield": h_start_shield, "burn_on_hit": h_burn_on_hit, "shield_on_cast": h_shield_on_cast,
    "as_stack_on_attack": h_as_stack_on_attack, "mana_refund_on_cast": h_mana_refund_on_cast, "spell_crit": h_spell_crit, "burn_aura": h_burn_aura,
    "as_slow_aura": h_as_slow_aura, "stack_on_hit": h_stack_on_hit, "heal_allies_timer": h_heal_allies_timer, "thorns": h_thorns, "gargoyle": h_gargoyle,
    "shred_on_crit": h_shred_on_crit, "magic_dr": h_magic_dr, "shock_every_n": h_shock_every_n, "cast_mana_allies": h_cast_mana_allies, "cc_immune": h_cc_immune,
    "extra_range": h_extra_range, "ap_stack_timer": h_ap_stack_timer, "hand_of_justice": h_hand_of_justice, "mana_on_kill": h_mana_on_kill, "mana_regen": h_mana_regen,
    "random_items": h_random_items, "shield_on_crit": h_shield_on_crit, "overheal_shield": h_overheal_shield, "revive": h_revive, "heal_on_revive_allies": h_heal_on_revive_allies,
    "aura_allies": h_aura_allies, "aura_enemies": h_aura_enemies, "regen": h_regen, "kill_explode": h_kill_explode, "execute_low": h_execute_low, "dodge": h_dodge,
    "true_dmg_on_cast": h_true_dmg_on_cast, "heal_on_cast_allies": h_heal_on_cast_allies, "summon_on_kill": h_summon_on_kill, "summon_on_cast": h_summon_on_cast,
    "first_cast_bonus": h_first_cast_bonus, "slow_on_cast": h_slow_on_cast, "stasis_low_hp": h_stasis_low_hp, "backline_jump": h_backline_jump,
    "dash_dmg_bonus": h_dash_dmg_bonus, "turret_stat_bonus": h_turret_stat_bonus, "as_pct_penalty": h_as_pct_penalty, "grant_trait": h_grant_trait,
    "double_trait_count": h_double_trait_count, "team_slot": h_noop, "gold_bonus": h_noop, "drop_bonus": h_noop, "hero_drop_bonus": h_noop,
}
