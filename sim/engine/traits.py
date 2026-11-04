# -*- coding: utf-8 -*-
"""출신 14 · 직업 14 특성 구현."""
from .hexgrid import hdist
from .hooks import summon_spec_from


def _lvl(count, thresholds):
    lvl = 0
    for i, th in enumerate(thresholds):
        if count >= th: lvl = i + 1
    return lvl


def _v(arr, lvl):
    return arr[min(lvl, len(arr)) - 1]


def scale_eff(eff, mult):
    """리스트형 수치에 임계값 배율 적용. '_mult'로 끝나는 키는 (v-1)*mult+1 형태로 적용."""
    if abs(mult - 1.0) < 1e-9: return eff
    out = {}
    for k, v in eff.items():
        if isinstance(v, list) and v and all(isinstance(x, (int, float)) for x in v):
            out[k] = [((x - 1) * mult + 1) if k.endswith("_mult") else x * mult for x in v]
        else:
            out[k] = v
    return out


def apply_traits(b, only_units=None):
    data = b.data
    for team in (0, 1):
        units = [u for u in (only_units if only_units is not None else b.units) if u.team == team and not u.is_summon and not u.is_turret and not u.is_structure]
        if not units: continue
        counts = {}
        if b.trait_counts_override and team in b.trait_counts_override:
            counts = dict(b.trait_counts_override[team])
        else:
            seen = set()
            for u in units:
                key = u.hid
                if key in seen: continue
                seen.add(key)
                mult = 2 if u.state.get("double_trait") else 1
                for tr in (u.origin, u.cls, *u.state.get("extra_traits", [])):
                    if tr in data.origins or tr in data.classes:
                        counts[tr] = counts.get(tr, 0) + mult
        active = {}
        disabled = set(b.rules.get("disable_traits", {}).get(team, ()))
        for tr, c in counts.items():
            if tr in disabled: continue
            if tr in data.origins:
                lvl = _lvl(c, data.origins[tr]["thresholds"])
            else:
                lvl = _lvl(c, data.classes[tr]["thresholds"])
            if lvl > 0: active[tr] = lvl
        b.team_traits[team] = active
        n_origins = len([k for k in counts if k in data.origins])
        for tr, lvl in active.items():
            if tr in data.origins:
                tdef = data.origins[tr]
                eff = scale_eff(tdef["effects"], tdef.get("balance", {}).get("mult", [1.0] * 8)[lvl - 1])
                holders = [u for u in units if u.origin == tr or tr in u.state.get("extra_traits", [])]
                ORIGIN_IMPL[tr](b, units, holders, eff, lvl, n_origins)
            else:
                tdef = data.classes[tr]
                eff = scale_eff(tdef["effects"], tdef.get("balance", {}).get("mult", [1.0] * 8)[lvl - 1])
                holders = [u for u in units if u.cls == tr or tr in u.state.get("extra_traits", [])]
                CLASS_IMPL[tr](b, units, holders, eff, lvl)


# ───────── 출신 ─────────
def t_astel(b, units, holders, eff, lvl, n):
    for u in units: u.mod["armor"] += _v(eff["allies_armor"], lvl)
    pct = _v(eff["start_shield_pct"], lvl)
    for u in holders:
        u.on("start", lambda b, u, p: u.add_shield(u.max_hp * p["pct"] / 100.0, b.t + 10), {"pct": pct})


def t_valheim(b, units, holders, eff, lvl, n):
    as_, ov = _v(eff["low_hp_as"], lvl), _v(eff["low_hp_omnivamp"], lvl)
    def on_dmg(b, u, p, src, amt, kind, is_attack):
        if u.hp_pct() <= 0.5 and not u.state.get("berserk"):
            u.state["berserk"] = True
            u.add_buff("as_pct", p["as"], 1e9); u.add_buff("omnivamp", p["ov"], 1e9)
    for u in holders: u.on("damaged", on_dmg, {"as": as_, "ov": ov})


def t_sairam(b, units, holders, eff, lvl, n):
    for u in holders:
        u.mod["crit"] += _v(eff["crit"], lvl); u.mod["crit_dmg"] += _v(eff["crit_dmg"], lvl)


def t_karna(b, units, holders, eff, lvl, n):
    dr, dur, mana = _v(eff["dr"], lvl), eff["dr_dur"], _v(eff["start_mana"], lvl)
    for u in holders:
        u.mod["mana"] += mana
        u.on("start", lambda b, u, p: u.add_buff("durability", p["dr"], b.t + p["dur"]), {"dr": dr, "dur": dur})


def t_lies(b, units, holders, eff, lvl, n):
    for u in holders: u.mana_on_attack += _v(eff["mana_on_attack"], lvl)


def t_elowen(b, units, holders, eff, lvl, n):
    for u in holders:
        u.regen_pct += _v(eff["regen_pct"], lvl); u.mod["range"] += _v(eff["range_bonus"], lvl)


def t_grandur(b, units, holders, eff, lvl, n):
    for u in units:
        u.mod["armor"] += _v(eff["allies_armor"], lvl); u.mod["mr"] += _v(eff["allies_mr"], lvl)
    # 아이템 증폭은 items.apply_items에서 출신 카운트로 선적용


def t_neos(b, units, holders, eff, lvl, n):
    as_, dur, ex = _v(eff["start_as"], lvl), eff["start_as_dur"], _v(eff["kill_explode"], lvl)
    def on_kill(b, u, p, victim):
        for e in b.enemies_of(u):
            if hdist(e.pos, victim.pos) <= 1: b.damage(u, e, p["dmg"], "magic", is_skill=True)
    for u in holders:
        u.on("start", lambda b, u, p: u.add_buff("as_pct", p["as"], b.t + p["dur"]), {"as": as_, "dur": dur})
        u.on("kill", on_kill, {"dmg": ex})


def t_nox(b, units, holders, eff, lvl, n):
    ov = _v(eff["omnivamp"], lvl)
    charges = _v(eff.get("wraith_charges", [0, 1, 2, 3]), lvl)
    stat = _v(eff.get("wraith_stat_pct", [30, 30, 30, 30]), lvl)
    team_state = b.team_state.setdefault(holders[0].team if holders else 0, {})
    team_state["nox_charges"] = int(round(charges))
    def on_died(b, u, p, killer):
        ts = b.team_state.setdefault(u.team, {})
        if ts.get("nox_charges", 0) <= 0: return
        ts["nox_charges"] -= 1
        spec = summon_spec_from(u, p["stat"], p["stat"], name="망령", lifetime=10, t=b.t)
        spec["hp"] = u.max_hp * p["stat"] / 100.0; spec["ad"] = u.ad_base * p["stat"] / 100.0
        b.spawn(u, spec, near=u.pos)
    for u in holders:
        u.mod["omnivamp"] += ov
        if charges > 0: u.on("died", on_died, {"stat": stat})


def t_celestia(b, units, holders, eff, lvl, n):
    ap, mana = _v(eff["ap"], lvl), _v(eff["cast_mana_allies"], lvl)
    def on_cast(b, u, p):
        for a in b.allies_of(u): a.mana = min(a.mana_max, a.mana + p["mana"])
    for u in holders:
        u.mod["ap"] += ap; u.on("cast", on_cast, {"mana": mana})


def t_dragonkin(b, units, holders, eff, lvl, n):
    for u in holders:
        u.mod["hp_pct"] += _v(eff["hp_pct"], lvl); u.mod["skill_dmg"] += _v(eff["skill_dmg_pct"], lvl)


def t_torga(b, units, holders, eff, lvl, n):
    per, mx = _v(eff["ad_pct_per_stack"], lvl), eff["max_stacks"]
    def stack(b, u, p, *a):
        if u.state.get("torga", 0) < p["mx"]:
            u.state["torga"] = u.state.get("torga", 0) + 1; u.add_buff("ad_pct", p["per"], 1e9)
    for u in holders:
        u.on("damaged", stack, {"per": per, "mx": mx}); u.on("kill", stack, {"per": per, "mx": mx})


def t_lumen(b, units, holders, eff, lvl, n):
    # 팀 단위 발동 횟수 제한: 2/4/6/8 → 1/2/3/4회 (수직 구성에서 8명 전원이 두 번 사는 것을 방지)
    heal = _v(eff["cheat_death_heal"], lvl)
    inv = _v(eff["invuln"], lvl) if isinstance(eff["invuln"], list) else eff["invuln"]
    charges = int(round(_v(eff.get("charges", [1, 2, 3, 4]), lvl)))
    if holders: b.team_state.setdefault(holders[0].team, {})["lumen_charges"] = charges
    def on_death(b, u, p, killer):
        ts = b.team_state.setdefault(u.team, {})
        if u.state.get("lumen_used") or ts.get("lumen_charges", 0) <= 0: return None
        u.state["lumen_used"] = True; ts["lumen_charges"] -= 1
        u.hp = max(1.0, u.max_hp * p["heal"] / 100.0); u.stasis_until = b.t + p["inv"]
        return "cancel"
    for u in holders: u.on("death", on_death, {"heal": heal, "inv": inv})


def t_freelancer(b, units, holders, eff, lvl, n):
    # 기본 보너스 + 다른 출신 1종당 추가 (자유용병만으로 구성된 팀도 기본 보너스는 받는다)
    pct = _v(eff.get("base_pct", [0, 0, 0, 0]), lvl) + _v(eff["pct_per_origin"], lvl) * max(0, n - 1)
    for u in holders:
        u.mod["ad_pct"] += pct; u.mod["ap"] += pct


# ───────── 직업 ─────────
def c_knight(b, units, holders, eff, lvl):
    dr = _v(eff["front_dr"], lvl)
    for u in units:
        if u.front: u.mod["durability"] += dr


def c_warrior(b, units, holders, eff, lvl):
    for u in holders: u.mod["hp_pct"] += _v(eff["hp_pct"], lvl)


def c_assassin(b, units, holders, eff, lvl):
    for u in holders:
        u.mod["crit"] += _v(eff["crit"], lvl); u.mod["crit_dmg"] += _v(eff["crit_dmg"], lvl)


def c_ranger(b, units, holders, eff, lvl):
    for u in holders: u.mod["as_pct"] += _v(eff["as_pct"], lvl)


def c_mage(b, units, holders, eff, lvl):
    for u in holders:
        u.mod["ap"] += _v(eff["ap"], lvl); u.mana_max = u.mana_max * _v(eff["mana_max_mult"], lvl)


def c_priest(b, units, holders, eff, lvl):
    for u in holders: u.state["heal_power"] = u.state.get("heal_power", 0) + _v(eff["heal_pct"], lvl)
    for u in units: u.mod["omnivamp"] += _v(eff["allies_omnivamp"], lvl)


def c_guardian(b, units, holders, eff, lvl):
    sh = _v(eff["shield"], lvl)
    def on_start(b, u, p):
        u.add_shield(p["sh"], b.t + 12)
        for a in b.allies_of(u):
            if hdist(a.pos, u.pos) <= 1: a.add_shield(p["sh"], b.t + 12)
    for u in holders: u.on("start", on_start, {"sh": sh})


def c_duelist(b, units, holders, eff, lvl):
    per, mx = _v(eff["as_per_attack"], lvl), eff["max_stacks"]
    def on_attack(b, u, p, tgt):
        if u.state.get("duel", 0) < p["mx"]:
            u.state["duel"] = u.state.get("duel", 0) + 1; u.add_buff("as_pct", p["per"], 1e9)
    for u in holders: u.on("attack", on_attack, {"per": per, "mx": mx})


def c_summoner(b, units, holders, eff, lvl):
    for u in holders: u.state["summon_bonus_pct"] = u.state.get("summon_bonus_pct", 0) + _v(eff["summon_stat_pct"], lvl)


def c_artillerist(b, units, holders, eff, lvl):
    rb, ratio = _v(eff["range_bonus"], lvl), _v(eff["third_attack_ad"], lvl)
    def on_attack(b, u, p, tgt):
        if u.attack_count % 3 == 0 and tgt.alive: b.damage(u, tgt, u.e_ad * p["r"], "physical", is_attack=False)
    for u in holders:
        u.mod["range"] += rb; u.on("attack", on_attack, {"r": ratio})


def c_shaman(b, units, holders, eff, lvl):
    for u in holders: u.state["shaman_shred"] = _v(eff["shred"], lvl)


def c_bard(b, units, holders, eff, lvl):
    mana, mult = _v(eff["start_mana"], lvl), _v(eff["buff_mult"], lvl)
    for u in units: u.mod["mana"] += mana
    for u in holders: u.state["bard_buff_mult"] = mult


def c_dragoon(b, units, holders, eff, lvl):
    dr, dur, dd = _v(eff["start_dr"], lvl), eff["start_dr_dur"], _v(eff["dash_dmg_pct"], lvl)
    for u in holders:
        u.state["dash_dmg_pct"] = u.state.get("dash_dmg_pct", 0) + dd
        u.on("start", lambda b, u, p: u.add_buff("durability", p["dr"], b.t + p["dur"]), {"dr": dr, "dur": dur})


def c_engineer(b, units, holders, eff, lvl):
    for u in holders: u.state["turret_bonus_pct"] = u.state.get("turret_bonus_pct", 0) + _v(eff["turret_stat_pct"], lvl)
    for u in units: u.mod["as_pct"] += _v(eff["allies_as"], lvl)


ORIGIN_IMPL = {"astel": t_astel, "valheim": t_valheim, "sairam": t_sairam, "karna": t_karna, "lies": t_lies, "elowen": t_elowen, "grandur": t_grandur,
               "neos": t_neos, "nox": t_nox, "celestia": t_celestia, "dragonkin": t_dragonkin, "torga": t_torga, "lumen": t_lumen, "freelancer": t_freelancer}
CLASS_IMPL = {"knight": c_knight, "warrior": c_warrior, "assassin": c_assassin, "ranger": c_ranger, "mage": c_mage, "priest": c_priest, "guardian": c_guardian,
              "duelist": c_duelist, "summoner": c_summoner, "artillerist": c_artillerist, "shaman": c_shaman, "bard": c_bard, "dragoon": c_dragoon, "engineer": c_engineer}
