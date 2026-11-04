# -*- coding: utf-8 -*-
"""
상황 의존형(context_dependent) 아이템의 유형별 전투 재평가.
시나리오:
  magic_heavy : 상대가 마법사·주술사 중심 (마저/마법 피해 감소 아이템)
  boss_hp     : 상대에 고체력 보스(계층 5, 체력 ×4) 포함 (거인 학살자/처형 계열)
  siege       : 적 성벽 구조물 (공성 사다리 등 구조물 피해)
  waves       : 3웨이브 방어전 (보급 마차·재생 계열)
  assassin    : 캐리어가 암살자 직업 (암살자의 가면)
각 시나리오에서 Δ(아이템 장착 캐리어 vs 미장착)를 측정해 '어느 상황에서 가치가 있는가'를 보고한다.
출력: sim/reports/context_items.json
"""
import argparse, json, os, sys, random, statistics, time
from multiprocessing import Pool
sys.path.insert(0, os.path.dirname(__file__))
from engine import GameData, Battle
from run_balance import carriers_for_item, ROLE_OF_CLASS, item_target
from scenario import structure_spec

ROOT = os.path.join(os.path.dirname(__file__), "..")
DATA = os.path.join(ROOT, "data")
REP = os.path.join(os.path.dirname(__file__), "reports")
_G = {}


def _init(heroes_doc, items_doc, battles_doc):
    _G["d"] = GameData(heroes=heroes_doc, items=items_doc, battles=battles_doc)


def _fight(args):
    scen, team, carrier_idx, item_id, opp, rules, seed, star, key = args
    d = _G["d"]
    A = [d.hero_spec(h, star, items=([item_id] if (i == carrier_idx and item_id) else [])) for i, h in enumerate(team)]
    B = []
    for o in opp:
        if isinstance(o, str): B.append(d.hero_spec(o, star))
        elif o.get("monster"): B.append(d.monster_spec(o["monster"], star=star, tier_override=o.get("tier"), hp_mult=o.get("hp_mult", 1.0)))
        else: B.append(o)
    r = Battle(d, A, B, seed=seed, rules=rules).run()
    return key, (scen, team[0], tuple(str(x) for x in opp[:1]), star), 1 if r["winner"] == 0 else 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--per", type=int, default=10); ap.add_argument("--procs", type=int, default=4); ap.add_argument("--seed", type=int, default=9191)
    ap.add_argument("--all", action="store_true", help="플래그 아이템뿐 아니라 전 아이템 평가")
    args = ap.parse_args()
    heroes_doc = json.load(open(os.path.join(DATA, "heroes.json"), encoding="utf-8"))
    items_doc = json.load(open(os.path.join(DATA, "items.json"), encoding="utf-8"))
    battles_doc = json.load(open(os.path.join(DATA, "battles.json"), encoding="utf-8"))
    data = GameData(heroes=heroes_doc, items=items_doc, battles=battles_doc)
    heroes = {h["id"]: h for h in heroes_doc["heroes"]}
    rng = random.Random(args.seed)
    t3 = [h["id"] for h in heroes_doc["heroes"] if h["tier"] == 3]
    pick = lambda role, excl: rng.choice([h for h in t3 if ROLE_OF_CLASS[heroes[h]["class"]] == role and h not in excl])
    teams = []
    for k in range(4):
        team = []
        for role in ("tank", "bruiser", "ad", "ap", "support"): team.append(pick(role, team))
        teams.append((team, ["tank", "bruiser", "ad", "ap", "support"]))
    # 암살자 캐리어 팀
    assassins = [h["id"] for h in heroes_doc["heroes"] if h["tier"] == 3 and h["class"] == "assassin"]
    teams_assassin = []
    for k in range(4):
        team = [pick("tank", []), pick("bruiser", []), rng.choice(assassins), pick("ap", []), pick("support", [])]
        teams_assassin.append((team, ["tank", "bruiser", "ad", "ap", "support"]))
    mages = [h["id"] for h in heroes_doc["heroes"] if h["tier"] == 3 and h["class"] in ("mage", "shaman")]
    scenarios = {
        "magic_heavy": dict(teams=teams, opp=lambda: [pick("tank", [])] + rng.sample(mages, 3) + [pick("support", [])], rules={}),
        # 보스/공성은 기준선 승률이 20~80% 구간에 오도록 강도를 맞춘다(0% 또는 100%면 Δ를 잴 수 없음)
        "boss_hp": dict(teams=teams, opp=lambda: [{"monster": "ash_general", "tier": 4, "hp_mult": 2.2}] + [pick("ad", []), pick("ap", [])], rules={}),
        "siege": dict(teams=teams, opp=lambda: [structure_spec("성벽", 3000, state={"priority": True, "arrow_aura_pct": 0.6})] + [pick("tank", []), pick("bruiser", []), pick("ad", []), pick("ap", []), pick("support", [])], rules={}),
        "waves": dict(teams=teams, opp=lambda: [pick("tank", []), pick("ad", []), pick("ap", [])], rules={"waves": 3}),
        "assassin": dict(teams=teams_assassin, opp=lambda: [pick("tank", []), pick("bruiser", []), pick("ad", []), pick("ap", []), pick("support", [])], rules={}),
    }
    flagged = [i for i in items_doc["items"] if i.get("balance", {}).get("flag") == "context_dependent"] if not args.all else \
              [i for i in items_doc["items"] if i["category"] in ("completed", "radiant", "artifact", "support", "national")]
    jobs = []
    for scen, sc in scenarios.items():
        opps = [sc["opp"]() for _ in range(3)]
        for ti, (team, roles) in enumerate(sc["teams"]):
            for oi, opp in enumerate(opps):
                rules = dict(sc["rules"])
                if rules.get("waves"):
                    rules = {"waves": [[dict(data.hero_spec(o, 1)) if isinstance(o, str) else o for o in opp] for _ in range(rules["waves"] - 1)]}
                for star in (1, 2):
                    for k in range(args.per):
                        seed = args.seed + ti * 100000 + oi * 10000 + star * 100 + k
                        jobs.append((scen, team, 0, None, opp, rules, seed, star, None))
                        for it in flagged:
                            cands = carriers_for_item(it)
                            idxs = [i for i, r in enumerate(roles) if r in cands] or [0]
                            if scen == "assassin": idxs = [2]
                            jobs.append((scen, team, idxs[k % len(idxs)], it["id"], opp, rules, seed, star, it["id"]))
    print(f"jobs {len(jobs)} for {len(flagged)} items", flush=True)
    t0 = time.time()
    wins = {}; cnt = {}
    with Pool(args.procs, initializer=_init, initargs=(heroes_doc, items_doc, battles_doc)) as pool:
        for key, mk, w in pool.imap_unordered(_fight, jobs, chunksize=32):
            wins[(key, mk)] = wins.get((key, mk), 0) + w; cnt[(key, mk)] = cnt.get((key, mk), 0) + 1
    base_wr = {}
    for scen in scenarios:
        mks = [mk for (k, mk) in wins if k is None and mk[0] == scen]
        base_wr[scen] = round(sum(wins[(None, mk)] for mk in mks) / sum(cnt[(None, mk)] for mk in mks), 3)
    print("baseline win-rate by scenario:", base_wr, flush=True)
    rows = []
    for it in flagged:
        row = dict(id=it["id"], name=it["name_ko"], category=it["category"], mult=it.get("balance", {}).get("mult", 1.0), target=item_target(it), delta={})
        for scen in scenarios:
            mks = [mk for (k, mk) in wins if k is None and mk[0] == scen]
            ds = [wins[(it["id"], mk)] / cnt[(it["id"], mk)] - wins[(None, mk)] / cnt[(None, mk)] for mk in mks if (it["id"], mk) in wins]
            row["delta"][scen] = round(sum(ds) / len(ds), 3) if ds else None
        best = max((v for v in row["delta"].values() if v is not None), default=0)
        row["best_scenario"] = max(row["delta"], key=lambda s: row["delta"][s] if row["delta"][s] is not None else -9)
        row["verdict"] = "상황 특화 OK" if best >= row["target"] - 0.03 else ("전반 과강" if min(v for v in row["delta"].values() if v is not None) > row["target"] + 0.05 else "재설계 필요")
        rows.append(row)
    json.dump({"scenarios": list(scenarios), "baseline_wr": base_wr, "rows": rows}, open(os.path.join(REP, "context_items.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"done {len(rows)} items, t={time.time()-t0:.0f}s")
    for r in rows: print(r["name"], r["delta"], r["verdict"])


if __name__ == "__main__":
    main()
