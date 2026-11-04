# -*- coding: utf-8 -*-
"""
아이템 다중 장착(2개·3개) 상호작용 측정.
Δ(조합) vs Σ Δ(단일) → 시너지(초가산) / 상쇄(열가산). 캐리어는 역할 적합 영웅(기준 팀 6종, 교차전, ★1·★2, 좌우 교대).
출력: sim/reports/item_combos.json
"""
import argparse, json, os, sys, random, statistics, time
from multiprocessing import Pool
sys.path.insert(0, os.path.dirname(__file__))
from engine import GameData, Battle
from run_balance import carriers_for_item, ROLE_OF_CLASS

ROOT = os.path.join(os.path.dirname(__file__), "..")
DATA = os.path.join(ROOT, "data")
REP = os.path.join(os.path.dirname(__file__), "reports")
_G = {}


def _init(heroes_doc, items_doc):
    _G["d"] = GameData(heroes=heroes_doc, items=items_doc)


def _fight(args):
    team, opp, carrier_idx, item_ids, seed, star, key = args
    d = _G["d"]
    A = [d.hero_spec(h, star, items=(list(item_ids) if i == carrier_idx else [])) for i, h in enumerate(team)]
    B = [d.hero_spec(h, star) for h in opp]
    side = seed & 1
    r = Battle(d, A, B, seed=seed).run() if side == 0 else Battle(d, B, A, seed=seed).run()
    return key, (team[0], opp[0], star), 1 if r["winner"] == side else 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pairs", type=int, default=240); ap.add_argument("--triples", type=int, default=120)
    ap.add_argument("--per", type=int, default=4, help="매치업·성급당 전투 수"); ap.add_argument("--procs", type=int, default=4); ap.add_argument("--seed", type=int, default=4242)
    args = ap.parse_args()
    heroes_doc = json.load(open(os.path.join(DATA, "heroes.json"), encoding="utf-8"))
    items_doc = json.load(open(os.path.join(DATA, "items.json"), encoding="utf-8"))
    data = GameData(heroes=heroes_doc, items=items_doc)
    heroes = {h["id"]: h for h in heroes_doc["heroes"]}
    rng = random.Random(args.seed)
    t3 = [h["id"] for h in heroes_doc["heroes"] if h["tier"] == 3]
    ref_teams = []
    for k in range(6):
        team = []
        for role in ("tank", "bruiser", "ad", "ap", "support"):
            team.append(rng.choice([h for h in t3 if ROLE_OF_CLASS[heroes[h]["class"]] == role and h not in team]))
        ref_teams.append((team, ["tank", "bruiser", "ad", "ap", "support"]))
    completed = [i["id"] for i in items_doc["items"] if i["category"] == "completed"]
    # 같은 캐리어 역할을 공유하는 조합만 (현실적인 장착)
    by_role = {}
    for iid in completed:
        for r in carriers_for_item(data.items[iid]): by_role.setdefault(r, []).append(iid)
    combos = set()
    while len(combos) < args.pairs:
        role = rng.choice(list(by_role)); pool = by_role[role]
        if len(pool) < 2: continue
        combos.add((role, tuple(sorted(rng.sample(pool, 2)))))
    while len(combos) < args.pairs + args.triples:
        role = rng.choice(list(by_role)); pool = by_role[role]
        if len(pool) < 3: continue
        combos.add((role, tuple(sorted(rng.sample(pool, 3)))))
    singles = {(role, (iid,)) for role, c in combos for iid in c}
    allkeys = list(singles) + list(combos)
    matchups = [(i, j) for i in range(6) for j in range(6) if i != j]
    jobs = []
    for ti, tj in matchups:
        team, roles = ref_teams[ti]; opp, _ = ref_teams[tj]
        for star in (1, 2):
            for k in range(args.per):
                jobs.append((team, opp, 0, (), args.seed + ti * 100000 + tj * 1000 + star * 100 + k, star, None))
    for role, ids in allkeys:
        for ti, tj in matchups:
            team, roles = ref_teams[ti]; opp, _ = ref_teams[tj]
            ci = roles.index(role) if role in roles else 0
            for star in (1, 2):
                for k in range(args.per):
                    jobs.append((team, opp, ci, ids, args.seed + ti * 100000 + tj * 1000 + star * 100 + k, star, (role, ids)))
    print(f"jobs: {len(jobs)} (singles {len(singles)}, combos {len(combos)})", flush=True)
    t0 = time.time()
    wins = {}; cnt = {}
    with Pool(args.procs, initializer=_init, initargs=(heroes_doc, items_doc)) as pool:
        for key, mk, w in pool.imap_unordered(_fight, jobs, chunksize=32):
            wins[(key, mk)] = wins.get((key, mk), 0) + w; cnt[(key, mk)] = cnt.get((key, mk), 0) + 1
    mks = sorted({mk for (k, mk) in wins if k is None})
    base = {mk: wins[(None, mk)] / cnt[(None, mk)] for mk in mks}
    delta = {}
    for key in allkeys:
        ds = [wins[(key, mk)] / cnt[(key, mk)] - base[mk] for mk in mks if (key, mk) in wins]
        delta[key] = sum(ds) / len(ds)
    name = lambda i: data.items[i]["name_ko"]
    rows = []
    for role, ids in combos:
        d_combo = delta[(role, ids)]
        d_sum = sum(delta[(role, (i,))] for i in ids)
        rows.append(dict(role=role, items=[name(i) for i in ids], ids=list(ids), delta=round(d_combo, 3), sum_single=round(d_sum, 3), synergy=round(d_combo - d_sum, 3)))
    rows.sort(key=lambda r: r["synergy"])
    syn = [r["synergy"] for r in rows]
    pairs = [r for r in rows if len(r["ids"]) == 2]; triples = [r for r in rows if len(r["ids"]) == 3]
    summary = {
        "pairs": {"n": len(pairs), "mean_delta": round(statistics.mean(r["delta"] for r in pairs), 3), "mean_sum_single": round(statistics.mean(r["sum_single"] for r in pairs), 3), "mean_synergy": round(statistics.mean(r["synergy"] for r in pairs), 3), "sd_synergy": round(statistics.pstdev(r["synergy"] for r in pairs), 3)},
        "triples": {"n": len(triples), "mean_delta": round(statistics.mean(r["delta"] for r in triples), 3), "mean_sum_single": round(statistics.mean(r["sum_single"] for r in triples), 3), "mean_synergy": round(statistics.mean(r["synergy"] for r in triples), 3), "sd_synergy": round(statistics.pstdev(r["synergy"] for r in triples), 3)},
    }
    json.dump({"summary": summary, "base": round(statistics.mean(base.values()), 3), "rows": rows}, open(os.path.join(REP, "item_combos.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(summary, f"t={time.time()-t0:.0f}s")


if __name__ == "__main__":
    main()
