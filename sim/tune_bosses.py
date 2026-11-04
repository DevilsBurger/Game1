# -*- coding: utf-8 -*-
"""
스토리 결전(decisive)·레이드(raid)·토벌(hunt) 전투의 보스 체력 배수 튜닝.
목표(기대 팀 기준): 보통 65% / 어려움 45% / 악몽 25% (일반 전투보다 어렵게).
방법: 각 전투를 난이도별 N회 시뮬레이션 → 보통 승률로 boss.hp_mult를 조정(±25%/라운드), 3라운드. 결과를 battles.json에 기록.
출력: sim/reports/boss_tuning.json
"""
import argparse, json, os, sys, random, statistics, time
from multiprocessing import Pool
sys.path.insert(0, os.path.dirname(__file__))
from engine import GameData, Battle
from scenario import build_scenario

ROOT = os.path.join(os.path.dirname(__file__), "..")
DATA = os.path.join(ROOT, "data")
REP = os.path.join(os.path.dirname(__file__), "reports")
TARGET = {"normal": 0.65, "hard": 0.45, "nightmare": 0.25}
_G = {}


def _init(curve):
    battles = json.load(open(os.path.join(DATA, "battles.json"), encoding="utf-8"))
    _G["d"] = GameData(battles=battles)
    _G["b"] = {b["id"]: b for b in battles["battles"]}
    _G["curve"] = curve


def _run(args):
    bid, diff, seed, hp_mult = args
    d = _G["d"]; b = _G["b"][bid]
    rng = random.Random(seed)
    allies, enemies, rules = build_scenario(d, b, diff, rng, curve=_G["curve"], boss_hp_override=hp_mult)
    r = Battle(d, allies, enemies, seed=seed, rules=rules).run()
    return bid, diff, 1 if r["winner"] == 0 else 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rounds", type=int, default=3); ap.add_argument("--fights", type=int, default=16); ap.add_argument("--procs", type=int, default=4)
    args = ap.parse_args()
    path = os.path.join(DATA, "battles.json")
    doc = json.load(open(path, encoding="utf-8"))
    econ = json.load(open(os.path.join(DATA, "economy.json"), encoding="utf-8"))
    curve = econ.get("enemy_power_curve", {})
    targets = [b for b in doc["battles"] if b["kind"] == "story" and b["enemy"]["boss"] and b["type"] in ("decisive", "raid", "hunt")]
    hp = {b["id"]: b["enemy"]["boss"]["hp_mult"] for b in targets}
    hist = []
    for rnd in range(args.rounds + 1):
        jobs = [(b["id"], diff, 1000 * rnd + i, hp[b["id"]]) for b in targets for diff in TARGET for i in range(args.fights if rnd < args.rounds else args.fights * 2)]
        wins = {}
        with Pool(args.procs, initializer=_init, initargs=(curve,)) as pool:
            for bid, diff, w in pool.imap_unordered(_run, jobs, chunksize=8):
                wins.setdefault((bid, diff), []).append(w)
        wr = {k: sum(v) / len(v) for k, v in wins.items()}
        devs = [wr[(b["id"], diff)] - TARGET[diff] for b in targets for diff in TARGET]
        print(f"[boss round {rnd}] mean dev={statistics.mean(devs):+.3f} sd={statistics.pstdev(devs):.3f}", flush=True)
        hist.append({"round": rnd, "mean_dev": statistics.mean(devs), "sd": statistics.pstdev(devs)})
        if rnd == args.rounds: break
        for b in targets:
            obs = wr[(b["id"], "normal")]
            f = ((obs + 0.05) / (TARGET["normal"] + 0.05)) ** 0.5
            hp[b["id"]] = round(max(1.0, min(8.0, hp[b["id"]] * max(0.75, min(1.3, f)))), 2)
    for b in targets:
        b["enemy"]["boss"]["hp_mult"] = hp[b["id"]]
        b["enemy"]["boss"]["tuned"] = True
    json.dump(doc, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    rows = [dict(id=b["id"], name=b["name_ko"], act=b["act"], type=b["type"], level=b["level"], boss=b["enemy"]["boss"]["name_ko"], hp_mult=hp[b["id"]],
                 wr={diff: round(wr[(b["id"], diff)], 3) for diff in TARGET}) for b in targets]
    json.dump({"targets": TARGET, "history": hist, "rows": rows}, open(os.path.join(REP, "boss_tuning.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    for r in rows: print(r["id"], r["name"], r["boss"], r["hp_mult"], r["wr"])


if __name__ == "__main__":
    main()
