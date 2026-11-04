# -*- coding: utf-8 -*-
"""
등가모델 밸런스 러너.

영웅 단계 (phase hero):
  계층별 무작위 5v5 몬테카를로 — 같은 계층 영웅끼리 양 팀을 무작위 편성(★1, 아이템 없음)하고
  각 영웅의 '참전 시 승률'(present win-rate)을 측정 → 50%로 수렴하도록 hp/ad/skill 배율을 반복 조정.
  보조 지표: 계층 내 1v1 라운드로빈(★2) 승률, 계층 간 교차 전력.
아이템 단계 (phase item):
  기준 팀(계층 3 혼합) 미러전에서 지정 캐리어 1명에게 아이템 1개를 장착했을 때의 승률 상승분(Δ)을 측정 →
  분류별 목표 Δ로 수렴하도록 아이템 배율(balance.mult)을 조정.
결과: data/heroes.json, data/items.json 갱신, sim/reports/*.json|md
"""
import argparse, json, os, sys, random, time, math, statistics
from multiprocessing import Pool
sys.path.insert(0, os.path.dirname(__file__))
from engine import GameData, Battle

ROOT = os.path.join(os.path.dirname(__file__), "..")
DATA = os.path.join(ROOT, "data")
REP = os.path.join(os.path.dirname(__file__), "reports")
os.makedirs(REP, exist_ok=True)

_G = {}


def _init(heroes_doc, items_doc):
    _G["data"] = GameData(heroes=heroes_doc, items=items_doc)


# ───────────────── 영웅: 팀전 몬테카를로 ─────────────────
def _team_fight(args):
    a_ids, b_ids, star, seed = args
    d = _G["data"]
    A = [d.hero_spec(h, star) for h in a_ids]; B = [d.hero_spec(h, star) for h in b_ids]
    r = Battle(d, A, B, seed=seed).run()
    out = {}
    for u in r["units"]:
        if u["is_summon"]: continue
        out[u["id"]] = (1 if r["winner"] == u["team"] else 0, u["stats"]["dmg"], u["stats"]["taken"], u["stats"]["heal"])
    return out


def hero_phase_eval(pool, heroes_by_tier, appearances, star, seed_base, team_size=5):
    jobs = []
    rng = random.Random(seed_base)
    for tier, ids in heroes_by_tier.items():
        n_fights = max(50, appearances * len(ids) // (2 * team_size))
        for i in range(n_fights):
            a = rng.sample(ids, team_size); rest = [x for x in ids if x not in a]; b = rng.sample(rest, team_size)
            jobs.append((a, b, star, seed_base * 100000 + i * 7 + tier))
    rng.shuffle(jobs)
    wins = {}; cnt = {}; dmg = {}; taken = {}; heal = {}
    for res in pool.imap_unordered(_team_fight, jobs, chunksize=16):
        for hid, (w, dm, tk, hl) in res.items():
            wins[hid] = wins.get(hid, 0) + w; cnt[hid] = cnt.get(hid, 0) + 1
            dmg[hid] = dmg.get(hid, 0) + dm; taken[hid] = taken.get(hid, 0) + tk; heal[hid] = heal.get(hid, 0) + hl
    return {h: dict(wr=wins[h] / cnt[h], n=cnt[h], dmg=dmg[h] / cnt[h], taken=taken[h] / cnt[h], heal=heal[h] / cnt[h]) for h in cnt}


def _duel(args):
    a, b, star, seed = args
    d = _G["data"]
    r = Battle(d, [d.hero_spec(a, star)], [d.hero_spec(b, star)], seed=seed).run()
    return a, b, r["winner"]


def duel_phase_eval(pool, heroes_by_tier, star, seed_base, reps=2):
    jobs = []
    for tier, ids in heroes_by_tier.items():
        for i in range(len(ids)):
            for j in range(i + 1, len(ids)):
                for k in range(reps):
                    jobs.append((ids[i], ids[j], star, seed_base + i * 1000 + j * 10 + k) if k % 2 == 0 else (ids[j], ids[i], star, seed_base + i * 1000 + j * 10 + k))
    wins = {}; cnt = {}
    for a, b, w in pool.imap_unordered(_duel, jobs, chunksize=32):
        for h, won in ((a, w == 0), (b, w == 1)):
            wins[h] = wins.get(h, 0) + (1 if won else 0); cnt[h] = cnt.get(h, 0) + 1
    return {h: wins[h] / cnt[h] for h in cnt}


def cross_tier_eval(pool, heroes_by_tier, seed_base, fights=120):
    """계층 t ★s 팀 vs 계층 t+1 ★1 팀 승률 (교차 전력 보고용)."""
    rng = random.Random(seed_base + 99)
    out = {}
    for t in range(1, 5):
        for star in (1, 2):
            jobs = []
            for i in range(fights):
                a = rng.sample(heroes_by_tier[t], 5); b = rng.sample(heroes_by_tier[t + 1], 5)
                jobs.append((a, b, star, 1, seed_base + 5000 + i))
            w = 0
            for res in pool.imap_unordered(_mixed_fight, jobs, chunksize=16): w += res
            out[f"T{t}★{star} vs T{t+1}★1"] = round(w / fights, 3)
    return out


def _mixed_fight(args):
    a_ids, b_ids, sa, sb, seed = args
    d = _G["data"]
    r = Battle(d, [d.hero_spec(h, sa) for h in a_ids], [d.hero_spec(h, sb) for h in b_ids], seed=seed).run()
    return 1 if r["winner"] == 0 else 0


# ───────────────── 아이템 ─────────────────
ROLE_OF_CLASS = {"knight": "tank", "guardian": "tank", "warrior": "bruiser", "duelist": "ad", "assassin": "ad", "ranger": "ad", "artillerist": "ad",
                 "mage": "ap", "summoner": "ap", "shaman": "ap", "priest": "support", "bard": "support", "engineer": "ap", "dragoon": "bruiser"}


def carriers_for_item(it):
    s = it.get("stats", {}); hooks = {h["type"] for h in it.get("hooks", [])}
    roles = []
    if any(k in s for k in ("ad_pct", "crit", "as_pct")) or hooks & {"stack_ad_on_kill", "giant_slayer", "shred_on_hit", "aoe_on_attack", "crit_dmg_bonus", "shred_on_crit", "as_stack_on_attack", "execute_low", "mana_on_attack", "stack_on_hit", "shock_every_n"}:
        roles += ["ad"]
    if "ap" in s or "mana" in s or hooks & {"spell_crit", "mana_refund_on_cast", "ap_stack_timer", "cast_mana_allies", "true_dmg_on_cast", "shield_on_cast", "first_cast_bonus", "burn_on_hit"}:
        roles += ["ap"]
    if any(k in s for k in ("hp", "armor", "mr", "durability")) or hooks & {"thorns", "gargoyle", "magic_dr", "low_hp_shield", "start_shield", "burn_aura", "as_slow_aura", "revive", "regen", "stasis_low_hp"}:
        roles += ["tank"]
    if "omnivamp" in s or hooks & {"omnivamp_bonus", "heal_on_kill", "overheal_shield", "hand_of_justice"}:
        roles += ["bruiser"]
    if it["category"] == "support" or hooks & {"aura_allies", "heal_allies_timer", "heal_on_cast_allies", "aura_enemies"}:
        roles = ["support"] + roles
    if not roles: roles = ["ad", "tank"]
    return list(dict.fromkeys(roles))[:2]


def _item_fight(args):
    team, carrier_idx, item_id, seed, star = args
    d = _G["data"]
    A = [d.hero_spec(h, star, items=([item_id] if (i == carrier_idx and item_id) else [])) for i, h in enumerate(team)]
    B = [d.hero_spec(h, star) for h in team]
    r = Battle(d, A, B, seed=seed).run()
    return item_id, 1 if r["winner"] == 0 else 0


def item_phase_eval(pool, data, ref_teams, item_ids, fights, seed_base, star=1):
    jobs = []
    # 기준선: 아이템 없음 (배치 비대칭 보정)
    for ti, (team, roles) in enumerate(ref_teams):
        for k in range(fights):
            jobs.append((team, 0, None, seed_base + ti * 1000 + k, star))
    for iid in item_ids:
        it = data.items[iid]
        cands = carriers_for_item(it)
        for ti, (team, roles) in enumerate(ref_teams):
            idxs = [i for i, r in enumerate(roles) if r in cands] or [0]
            for k in range(fights):
                ci = idxs[k % len(idxs)]
                jobs.append((team, ci, iid, seed_base + ti * 1000 + k, star))
    wins = {}; cnt = {}
    for iid, w in pool.imap_unordered(_item_fight, jobs, chunksize=32):
        wins[iid] = wins.get(iid, 0) + w; cnt[iid] = cnt.get(iid, 0) + 1
    base = wins[None] / cnt[None]
    return base, {iid: wins[iid] / cnt[iid] - base for iid in item_ids}


ITEM_TARGET = {"completed": 0.11, "radiant": 0.20, "artifact": 0.14, "support": 0.08, "national": 0.12}


def scale_item(it, f):
    it.setdefault("balance", {"mult": 1.0})
    it["balance"]["mult"] = round(it["balance"]["mult"] * f, 4)


# ───────────────── 메인 ─────────────────
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--phase", default="all", choices=["hero", "item", "all", "report"])
    ap.add_argument("--iters", type=int, default=8)
    ap.add_argument("--appearances", type=int, default=300)
    ap.add_argument("--item-iters", type=int, default=4)
    ap.add_argument("--item-fights", type=int, default=40)
    ap.add_argument("--procs", type=int, default=4)
    ap.add_argument("--band", type=float, default=0.05)
    ap.add_argument("--seed", type=int, default=2026)
    args = ap.parse_args()

    heroes_doc = json.load(open(os.path.join(DATA, "heroes.json"), encoding="utf-8"))
    items_doc = json.load(open(os.path.join(DATA, "items.json"), encoding="utf-8"))
    heroes = {h["id"]: h for h in heroes_doc["heroes"]}
    by_tier = {t: [h["id"] for h in heroes_doc["heroes"] if h["tier"] == t] for t in range(1, 6)}
    history = {"hero": [], "item": []}
    t0 = time.time()

    if args.phase in ("hero", "all"):
        for it in range(args.iters):
            with Pool(args.procs, initializer=_init, initargs=(heroes_doc, items_doc)) as pool:
                ev1 = hero_phase_eval(pool, by_tier, args.appearances, 1, args.seed + it)
                ev3 = hero_phase_eval(pool, by_tier, args.appearances * 2 // 3, 3, args.seed + 50 + it)
            # 혼합 목적함수: ★1 60% + ★3 40%
            ev = {h: dict(v, wr=0.6 * v["wr"] + 0.4 * ev3[h]["wr"], wr1=v["wr"], wr3=ev3[h]["wr"]) for h, v in ev1.items()}
            wrs = [v["wr"] for v in ev.values()]
            inband = sum(1 for w in wrs if abs(w - 0.5) <= args.band) / len(wrs)
            sd = statistics.pstdev(wrs)
            print(f"[hero iter {it}] mean={statistics.mean(wrs):.3f} sd={sd:.3f} in-band={inband:.1%} min={min(wrs):.3f} max={max(wrs):.3f} t={time.time()-t0:.0f}s", flush=True)
            history["hero"].append({"iter": it, "sd": sd, "in_band": inband, "min": min(wrs), "max": max(wrs),
                                    "sd_star1": statistics.pstdev([v["wr1"] for v in ev.values()]), "sd_star3": statistics.pstdev([v["wr3"] for v in ev.values()])})
            if inband >= 0.97 and it >= 2: break
            # 조정
            for hid, v in ev.items():
                wr = v["wr"]
                f = (0.5 / max(0.05, wr)) ** 0.42
                f = max(0.86, min(1.16, f))
                if abs(wr - 0.5) <= args.band * 0.5: f = 1.0
                b = heroes[hid]["balance"]
                b["hp_mult"] = round(b["hp_mult"] * f, 4); b["ad_mult"] = round(b["ad_mult"] * f, 4); b["skill_mult"] = round(b["skill_mult"] * f, 4)
            json.dump(heroes_doc, open(os.path.join(DATA, "heroes.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    # 최종 평가 (영웅)
    with Pool(args.procs, initializer=_init, initargs=(heroes_doc, items_doc)) as pool:
        ev = hero_phase_eval(pool, by_tier, max(args.appearances, 500), 1, args.seed + 777)
        ev3 = hero_phase_eval(pool, by_tier, 200, 3, args.seed + 778)
        duel = duel_phase_eval(pool, by_tier, 2, args.seed + 999)
        cross = cross_tier_eval(pool, by_tier, args.seed)
    hero_report = []
    for hid in sorted(ev, key=lambda h: heroes[h]["tier"] * 1000 + int(h[1:])):
        h = heroes[hid]; v = ev[hid]
        hero_report.append(dict(id=hid, name=h["name_ko"], tier=h["tier"], origin=h["origin"], cls=h["class"], arche=h["skill"]["archetype"],
                                wr_team=round(v["wr"], 3), wr_team_star3=round(ev3[hid]["wr"], 3), wr_duel=round(duel.get(hid, 0.5), 3), n=v["n"],
                                dmg=round(v["dmg"]), taken=round(v["taken"]), heal=round(v["heal"]),
                                hp_mult=h["balance"]["hp_mult"], ad_mult=h["balance"]["ad_mult"], skill_mult=h["balance"]["skill_mult"]))
    json.dump({"history": history["hero"], "cross_tier": cross, "heroes": hero_report}, open(os.path.join(REP, "hero_balance.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    wrs = [r["wr_team"] for r in hero_report]
    print(f"[hero final] sd={statistics.pstdev(wrs):.3f} in-band={sum(1 for w in wrs if abs(w-0.5)<=args.band)/len(wrs):.1%} cross={cross}", flush=True)

    if args.phase in ("item", "all"):
        data = GameData(heroes=heroes_doc, items=items_doc)
        rng = random.Random(args.seed + 31)
        t3 = by_tier[3]
        ref_teams = []
        for k in range(6):
            team = []
            # 역할 구성: tank, bruiser, ad, ap, support
            for role in ("tank", "bruiser", "ad", "ap", "support"):
                cands = [h for h in t3 if ROLE_OF_CLASS[heroes[h]["class"]] == role and h not in team]
                team.append(rng.choice(cands))
            ref_teams.append((team, ["tank", "bruiser", "ad", "ap", "support"]))
        cats = list(ITEM_TARGET.keys())
        item_ids = [i["id"] for i in items_doc["items"] if i["category"] in cats]
        for it in range(args.item_iters):
            with Pool(args.procs, initializer=_init, initargs=(heroes_doc, items_doc)) as pool:
                base, deltas = item_phase_eval(pool, data, ref_teams, item_ids, args.item_fights, args.seed + 500 + it)
            by_cat = {}
            for iid, dl in deltas.items(): by_cat.setdefault(data.items[iid]["category"], []).append(dl)
            summary = {c: (round(statistics.mean(v), 3), round(statistics.pstdev(v), 3)) for c, v in by_cat.items()}
            print(f"[item iter {it}] base={base:.3f} {summary} t={time.time()-t0:.0f}s", flush=True)
            history["item"].append({"iter": it, "base": base, "summary": summary})
            for iid, dl in deltas.items():
                it_ = data.items[iid]; target = ITEM_TARGET[it_["category"]]
                if abs(dl - target) <= 0.03: continue
                f = ((target + 0.05) / max(0.01, dl + 0.05)) ** 0.6
                f = max(0.8, min(1.25, f))
                scale_item(it_, f)
            json.dump(items_doc, open(os.path.join(DATA, "items.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        with Pool(args.procs, initializer=_init, initargs=(heroes_doc, items_doc)) as pool:
            base, deltas = item_phase_eval(pool, data, ref_teams, item_ids, max(args.item_fights, 60), args.seed + 900)
        item_report = [dict(id=iid, name=data.items[iid]["name_ko"], category=data.items[iid]["category"], delta=round(dl, 3),
                            mult=data.items[iid].get("balance", {"mult": 1.0})["mult"], carriers=carriers_for_item(data.items[iid])) for iid, dl in deltas.items()]
        json.dump({"history": history["item"], "base": base, "ref_teams": ref_teams, "items": item_report}, open(os.path.join(REP, "item_balance.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print("[item final] base=%.3f" % base, flush=True)
    print("done in %.0fs" % (time.time() - t0))


if __name__ == "__main__":
    main()
