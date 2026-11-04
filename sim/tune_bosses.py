# -*- coding: utf-8 -*-
"""
스토리 결전(decisive)·레이드(raid)·토벌(hunt) 전투의 보스 체력 배수 튜닝.
목표(기대 팀 기준): 보통 65% / 어려움 45% / 악몽 25% (일반 전투보다 어렵게).
방법: 보스 체력 배수는 설계값(토벌 2.0/레이드 4.0/결전 3.0) 유지. 고정 매치업의 승률은 전력 배수의 계단 함수에 가까우므로
      난이도별로 '승률 50% 교차점(절벽)'을 이분 탐색(7단계)으로 찾고, 여유 배수(보통 0.96 / 어려움 1.00 / 악몽 1.035; 절벽 전이 폭이 ±5% 수준)를 곱해
      difficulties[diff].tuned_power_mult(적 HP·AD·AP 배수)를 정한다. power_cliff도 함께 기록. 결과를 battles.json에 기록.
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
    bid, diff, seed, hp_mult, pmult = args
    d = _G["d"]; b = _G["b"][bid]
    b = dict(b); b["difficulties"] = {k: dict(v, tuned_power_mult=pmult.get(k, 1.0)) if isinstance(v, dict) and "rewards" in v else v for k, v in b["difficulties"].items()}
    rng = random.Random(seed)
    allies, enemies, rules = build_scenario(d, b, diff, rng, curve=_G["curve"], boss_hp_override=hp_mult)
    r = Battle(d, allies, enemies, seed=seed, rules=rules).run()
    return bid, diff, 1 if r["winner"] == 0 else 0


def measure(pool, targets, pm_of, fights, seed0):
    """pm_of(bid, diff) → 전력 배수. 반환 wr[(bid, diff)]"""
    jobs = [(b["id"], diff, seed0 + i, b["enemy"]["boss"]["hp_mult"], {diff: pm_of(b["id"], diff)}) for b in targets for diff in TARGET for i in range(fights)]
    wins = {}
    for bid, diff, w in pool.imap_unordered(_run, jobs, chunksize=8):
        wins.setdefault((bid, diff), []).append(w)
    return {k: sum(v) / len(v) for k, v in wins.items()}


MARGIN = {"normal": 0.96, "hard": 1.0, "nightmare": 1.035}   # 50% 교차점(절벽) 대비 전력 배수 (전이 폭이 ±5% 수준으로 좁다)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--steps", type=int, default=7, help="이분 탐색 단계"); ap.add_argument("--fights", type=int, default=24); ap.add_argument("--procs", type=int, default=4)
    ap.add_argument("--reset", action="store_true", help="보스 체력 배수를 설계값으로 초기화")
    args = ap.parse_args()
    path = os.path.join(DATA, "battles.json")
    doc = json.load(open(path, encoding="utf-8"))
    econ = json.load(open(os.path.join(DATA, "economy.json"), encoding="utf-8"))
    curve = econ.get("enemy_power_curve", {})
    targets = [b for b in doc["battles"] if b["kind"] == "story" and b["enemy"]["boss"] and b["type"] in ("decisive", "raid", "hunt")]
    DESIGN_HP = {"hunt": 2.0, "raid": 4.0, "decisive": 3.0}
    for b in targets:
        if args.reset or not b["enemy"]["boss"].get("tuned"): b["enemy"]["boss"]["hp_mult"] = DESIGN_HP[b["type"]]
    # 팀전 승률은 전력 배수에 대해 계단 함수에 가깝다(고정 매치업은 거의 결정론적). 따라서 승률 자체가 아니라
    # '승률 50% 교차점(절벽)'을 이분 탐색으로 찾고, 난이도별 여유 배수(MARGIN)를 곱해 전력 배수를 정한다.
    lo = {(b["id"], d): 0.3 for b in targets for d in TARGET}; hi = {(b["id"], d): 2.5 for b in targets for d in TARGET}
    hist = []
    with Pool(args.procs, initializer=_init, initargs=(curve,)) as pool:
        for step in range(args.steps):
            mid = {k: (lo[k] + hi[k]) / 2 for k in lo}
            wr = measure(pool, targets, lambda bid, d: mid[(bid, d)], args.fights, 10000 * step)
            for k in lo:
                if wr[k] >= 0.5: lo[k] = mid[k]   # 아직 이김 → 더 강하게
                else: hi[k] = mid[k]
            print(f"[bisect {step}] mean cliff={statistics.mean((lo[k]+hi[k])/2 for k in lo):.3f}", flush=True)
            hist.append({"step": step, "mean_cliff": statistics.mean((lo[k] + hi[k]) / 2 for k in lo)})
        cliff = {k: round((lo[k] + hi[k]) / 2, 3) for k in lo}
        pm = {b["id"]: {d: round(max(0.3, min(2.5, cliff[(b["id"], d)] * MARGIN[d])), 3) for d in TARGET} for b in targets}
        wr = measure(pool, targets, lambda bid, d: pm[bid][d], args.fights * 2, 999999)
    devs = [wr[(b["id"], d)] - TARGET[d] for b in targets for d in TARGET]
    print(f"[boss final] mean dev={statistics.mean(devs):+.3f} sd={statistics.pstdev(devs):.3f}", flush=True)
    for b in targets:
        b["enemy"]["boss"]["tuned"] = True
        for d in TARGET:
            b["difficulties"][d]["tuned_power_mult"] = pm[b["id"]][d]
            b["difficulties"][d]["power_cliff"] = cliff[(b["id"], d)]
    json.dump(doc, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    rows = [dict(id=b["id"], name=b["name_ko"], act=b["act"], type=b["type"], level=b["level"], boss=b["enemy"]["boss"]["name_ko"], hp_mult=b["enemy"]["boss"]["hp_mult"],
                 cliff={d: cliff[(b["id"], d)] for d in TARGET}, power_mult=pm[b["id"]], wr={d: round(wr[(b["id"], d)], 3) for d in TARGET}) for b in targets]
    json.dump({"targets": TARGET, "margin": MARGIN, "history": hist, "rows": rows}, open(os.path.join(REP, "boss_tuning.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    for r in rows: print(r["id"], r["name"], r["boss"], r["cliff"], r["wr"])


if __name__ == "__main__":
    main()
