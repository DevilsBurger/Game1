# -*- coding: utf-8 -*-
"""스킬 원형 34종 구현."""
from .hexgrid import hdist, cells_within, hneighbors
from .hooks import summon_spec_from


def _p(params, key, star, default=0.0):
    v = params.get(key, default)
    if isinstance(v, list): return v[min(star, len(v)) - 1]
    return v


def _targets_radius(b, u, center_unit, radius, enemies=True):
    pool = b.enemies_of(u) if enemies else b.allies_of(u, include_self=True)
    return [x for x in pool if hdist(x.pos, center_unit.pos) <= radius]


def _lowest_enemy(b, u):
    es = b.enemies_of(u)
    return min(es, key=lambda e: (e.hp, b.rng.random())) if es else None


def _farthest_enemy(b, u):
    es = b.enemies_of(u)
    return max(es, key=lambda e: (hdist(u.pos, e.pos), b.rng.random())) if es else None


def _cluster_enemy(b, u):
    es = b.enemies_of(u)
    if not es: return None
    return max(es, key=lambda e: (sum(1 for x in es if hdist(x.pos, e.pos) <= 1), -e.hp))


def _dash_to(b, u, tgt):
    if hdist(u.pos, tgt.pos) <= 1: return True
    cands = [c for c in hneighbors(tgt.pos) if c not in b.occ]
    if not cands: return False
    cands.sort(key=lambda c: (hdist(c, u.pos), b.rng.random()))
    b.move_to(u, cands[0]); u.target = tgt
    return True


def skill_damage(u, params, star, mult_extra=1.0):
    dmg = _p(params, "dmg", star) * u.e_ap / 100.0 + _p(params, "ad_ratio", star) * u.e_ad + _p(params, "flat", star)
    return dmg * u.skill_mult * mult_extra


def cast_ability(b, u):
    sk = u.skill; params = sk["params"]; star = u.star; kind = params.get("kind")
    arche = sk["archetype"]
    t = b.t
    tgt = u.target if (u.target is not None and u.target.alive) else None
    sel = params.get("target", "current")
    if kind == "damage":
        can_crit = bool(params.get("crit")) or "ad_ratio" in params and arche in ("burst_ad", "dash_strike")
        dtype = "magic" if "dmg" in params and "ad_ratio" not in params else "physical"
        if sel == "farthest": tgt = _farthest_enemy(b, u)
        elif sel == "lowest_enemy": tgt = _lowest_enemy(b, u)
        elif sel == "cluster": tgt = _cluster_enemy(b, u)
        elif sel == "self": tgt = u
        if tgt is None:
            tgt = _lowest_enemy(b, u) if sel != "self" else u
            if tgt is None: return
        if params.get("dash") and tgt is not u:
            _dash_to(b, u, tgt)
        dash_mult = 1.0
        if params.get("dash"):
            dash_mult *= 1 + u.state.get("dash_dmg_pct", 0.0) / 100.0
        base = skill_damage(u, params, star, dash_mult)
        if params.get("execute_scale"):
            base *= 1 + params["execute_scale"] * (1 - tgt.hp_pct())
        radius = params.get("radius", 0)
        victims = []
        if sel == "self":
            victims = _targets_radius(b, u, u, max(1, radius))
        elif radius > 0:
            victims = _targets_radius(b, u, tgt, radius)
        elif params.get("line"):
            es = sorted(b.enemies_of(u), key=lambda e: hdist(e.pos, tgt.pos))
            behind = [e for e in es if e is not tgt and hdist(e.pos, u.pos) >= hdist(tgt.pos, u.pos) and hdist(e.pos, tgt.pos) <= params["line"]]
            victims = [tgt] + behind[:params["line"] - 1]
        else:
            victims = [tgt]
        shred = _p(params, "shred", star) if "shred" in params else 0
        stun = params.get("stun", 0); slow = params.get("slow", 0)
        killed_main = False
        for v in victims:
            before_alive = v.alive
            dealt = b.damage(u, v, base, dtype, is_skill=True, can_crit=can_crit, crit_forced=bool(params.get("crit")) and v is tgt)
            if params.get("heal_pct"): b.heal(u, u, dealt * params["heal_pct"] / 100.0)
            if shred and v.alive: b.shred(v, shred, params.get("shred_dur", 6))
            if stun and v.alive: b.stun(v, stun)
            if slow and v.alive: b.slow(v, slow, params.get("slow_dur", 3))
            if u.state.get("shaman_shred") and v.alive: b.shred(v, u.state["shaman_shred"], 6)
            if before_alive and not v.alive and v is tgt: killed_main = True
        if params.get("bounces") and tgt is not None:
            cur = tgt; dmg = base; hit = {tgt.uid}
            for _ in range(params["bounces"]):
                dmg *= params.get("falloff", 0.75)
                cands = [e for e in b.enemies_of(u) if e.uid not in hit and hdist(e.pos, cur.pos) <= 2]
                if not cands: break
                nxt = min(cands, key=lambda e: hdist(e.pos, cur.pos))
                hit.add(nxt.uid)
                b.damage(u, nxt, dmg, dtype, is_skill=True)
                cur = nxt
        if "self_ad_pct" in params:
            u.add_buff("ad_pct", _p(params, "self_ad_pct", star), t + params.get("buff_dur", 4))
        if params.get("reset_on_kill") and killed_main and u.state.get("exec_resets", 0) < 3:
            u.state["exec_resets"] = u.state.get("exec_resets", 0) + 1
            u.state["mana_refund"] = u.mana_max  # 즉시 재시전 가능
        if u.state.get("slow_on_cast"):
            for v in victims:
                if v.alive: b.slow(v, u.state["slow_on_cast"][0], u.state["slow_on_cast"][1])
        if u.state.get("true_dmg_pct"):
            for v in victims:
                if v.alive: b.damage(u, v, base * u.state["true_dmg_pct"] / 100.0, "true", is_skill=True)
    elif kind == "dot":
        if tgt is None: tgt = _lowest_enemy(b, u)
        if tgt is None: return
        total = _p(params, "dmg", star) * u.e_ap / 100.0 * u.skill_mult * (1 + u.mod["skill_dmg"] / 100.0)
        dur = params.get("duration", 6)
        tgt.dots.append([total / dur, t + dur, u, "magic"])
        if u.state.get("shaman_shred"): b.shred(tgt, u.state["shaman_shred"], 6)
    elif kind == "heal":
        amt = _p(params, "heal", star) * u.e_ap / 100.0 * u.skill_mult
        if sel == "lowest_ally":
            allies = b.allies_of(u, include_self=True)
            v = min(allies, key=lambda a: a.hp_pct())
            b.heal(u, v, amt)
            if arche == "heal_lowest" and u.origin == "nox" and tgt is not None:
                b.damage(u, tgt, amt * 0.5, "magic", is_skill=True)
        else:
            for a in b.allies_of(u, include_self=True):
                b.heal(u, a, amt)
        if arche == "heal_aoe" and u.name == "요한나 루멘" and not u.state.get("revived_once"):
            # 요한나: 전투 중 1회 부활
            dead = [x for x in b.units if x.team == u.team and not x.alive and not x.is_summon and not x.is_turret and x.dead_time is not None]
            if dead:
                v = max(dead, key=lambda x: x.max_hp)
                cell = b.free_cell_near(u.pos, 3)
                if cell:
                    v.alive = True; v.hp = v.max_hp * 0.4; v.pos = cell; b.occ[cell] = v; v.target = None; v.mana = v.mana_start
                    u.state["revived_once"] = True
    elif kind == "shield":
        amt = _p(params, "shield", star) * u.e_ap / 100.0 * u.skill_mult
        dur = params.get("duration", 5)
        if sel == "self":
            u.add_shield(amt, t + dur)
            if u.name == "로이드 하트윈":
                for a in b.allies_of(u): a.add_shield(amt * 0.5, t + dur)
            if params.get("taunt_radius"):
                for e in _targets_radius(b, u, u, params["taunt_radius"]):
                    if e.cc_immune_until <= t:
                        e.taunt_by = u; e.taunt_until = t + params.get("taunt_dur", 2.5); e.target = u
                if u.name in ("브롬 스톤하트", "가브리엘 아르망"):  # 브롬/가브리엘: 피해 감소
                    u.add_buff("durability", 15, t + dur)
        elif sel == "adjacent_allies":
            for a in b.allies_of(u, include_self=True):
                if hdist(a.pos, u.pos) <= 1 or u.tier >= 5: a.add_shield(amt, t + dur)
            if u.name in ("로이드 하트윈", "트리톤 바르"):
                for a in b.allies_of(u, include_self=True): a.add_buff("armor", 20, t + dur)
    elif kind == "buff":
        dur = params.get("duration", 5)
        mult = u.state.get("bard_buff_mult", 1.0)
        targets = [u] if sel == "self" else b.allies_of(u, include_self=True)
        for a in targets:
            if "as_pct" in params: a.add_buff("as_pct", _p(params, "as_pct", star) * (mult if sel != "self" else 1.0), t + dur)
            if "ad_pct" in params: a.add_buff("ad_pct", _p(params, "ad_pct", star) * mult, t + dur)
            if "ap_flat" in params: a.add_buff("ap", _p(params, "ap_flat", star) * mult, t + dur)
        if arche == "buff_as_self":
            u.state["onhit_magic"] = (0.0, t + dur)
            if u.name == "카시안":  # 카시안: 공격마다 추가 마법 피해
                u.state["onhit_magic"] = (0.35 * u.e_ap, t + dur)
            if u.name == "에이나르":  # 에이나르: 잃은 체력 비례 AD
                u.add_buff("ad_pct", 40 * (1 - u.hp_pct()), t + dur)
        if arche == "buff_as_allies" and u.name == "리라":  # 리라: 마나 충전
            for a in b.allies_of(u): a.mana = min(a.mana_max, a.mana + 20)
    elif kind == "empower":
        u.empowered = int(_p(params, "shots", star))
        u.state["empower"] = (_p(params, "bonus_ad_ratio", star) * u.skill_mult, _p(params, "bonus_flat", star) * u.skill_mult)
    elif kind in ("summon", "turret"):
        is_t = kind == "turret"
        active = [s for s in u.summons if s.alive]
        maxa = params.get("max_active", 1)
        count = params.get("count", 1)
        hp_pct = _p(params, "hp_pct", star) * u.skill_mult; ad_pct = _p(params, "ad_pct", star) * u.skill_mult
        n = 0
        while len(active) + n < maxa and n < count:
            spec = summon_spec_from(u, hp_pct, ad_pct, name=("포탑" if is_t else "소환수"), lifetime=params.get("lifetime", 12), is_turret=is_t, t=t)
            if is_t and params.get("radius"):
                spec["skill"] = None
            s = b.spawn(u, spec)
            if s is None: break
            if is_t and params.get("radius"): s.state["splash"] = params["radius"]
            n += 1
        if n == 0 and active:
            # 이미 최대: 소환수 회복/강화
            for s in active:
                b.heal(u, s, s.max_hp * 0.3)
                s.add_buff("ad_pct", 20, t + 5)
