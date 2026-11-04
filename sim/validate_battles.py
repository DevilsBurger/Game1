# -*- coding: utf-8 -*-
"""
전투 난이도 검증: battles.json의 적 편성을 몬스터 템플릿으로 생성하고, 전투 레벨에 맞는 '기대 팀'으로 싸워
난이도별 승률을 측정한다. 목표: 보통 70~85%, 어려움 45~65%, 악몽 20~40% (기대 팀 기준).
출력: sim/reports/battle_validation.json
"""
import json, os, sys, random, statistics, argparse
from multiprocessing import Pool
sys.path.insert(0, os.path.dirname(__file__))
from engine import GameData, Battle

ROOT = os.path.join(os.path.dirname(__file__), "..")
DATA = os.path.join(ROOT, "data")
REP = os.path.join(os.path.dirname(__file__), "reports")
_G = {}


def _init(curve=None):
    battles = json.load(open(os.path.join(DATA, "battles.json"), encoding="utf-8"))
    _G["d"] = GameData(battles=battles)
    _G["b"] = {b["id"]: b for b in battles["battles"]}
    _G["curve"] = curve or {}


def expected_team(d, level, size, rng):
    """레벨에 맞는 기대 팀: 계층 = 1 + level//22, 성급 = 1(레벨<35) / 2(35~75) / 3(75+). 역할 혼합."""
    tier = max(1, min(5, 1 + level // 22))
    star = 1 if level < 35 else (2 if level < 75 else 3)
    pool = [h for h in d.heroes.values() if h["tier"] in (tier, max(1, tier - 1))]
    roles = ["knight", "guardian", "warrior", "duelist", "ranger", "mage", "priest", "assassin", "artillerist", "bard"]
    team = []
    for r in roles[:size]:
        cands = [h for h in pool if h["class"] == r]
        team.append(rng.choice(cands)["id"])
    return [d.hero_spec(h, star) for h in team]


def band_of(level):
    lo = (level - 1) // 10 * 10 + 1
    return f"{lo}-{lo+9}"


def enemy_power(level, diff, curve):
    bands = curve.get("bands", {})
    if isinstance(bands.get(diff), dict):  # 난이도별 × 구간별
        return bands[diff].get(band_of(level), 1.0)
    return bands.get(band_of(level), 1.0) * curve.get("difficulty_mult", {}).get(diff, 1.0)


def enemy_team(d, b, diff, curve=None):
    dd = b["difficulties"][diff]
    star = dd["enemy_star"]; pm = dd["enemy_power_mult"]
    # 전력 배수는 성급 상승으로 대부분 반영되므로 잔여분만 능력치에 적용
    star_gain = {1: 1.0, 2: 1.8 * 1.5, 3: 3.24 * 2.25}
    residual = max(0.75, min(1.6, (pm / (star_gain[star] / star_gain[b["difficulties"]["normal"]["enemy_star"]])) ** 0.5))
    residual *= enemy_power(b["level"], diff, curve or _G.get("curve", {}))
    units = []
    for u in b["enemy"]["units"]:
        units.append(d.monster_spec(u["unit"], star=star, tier_override=u["tier"], power_mult=residual))
    if b["enemy"]["boss"]:
        bs = b["enemy"]["boss"]
        units.append(d.monster_spec(bs["unit"], star=star, tier_override=bs["tier"], hp_mult=bs["hp_mult"], power_mult=residual))
    return units[:12]


def _run(args):
    bid, diff, seed = args
    d = _G["d"]; b = _G["b"][bid]
    rng = random.Random(seed)
    size = max(b["participation"]["min"], min(b["participation"]["max"], 6 if b["participation"]["mode"] != "solo" else 1))
    if b["participation"]["mode"] == "solo":
        allies = [d.hero_spec(rng.choice([h["id"] for h in d.heroes.values() if h["tier"] == max(1, min(5, 1 + b["level"] // 22)) and h["class"] in ("duelist", "warrior", "knight")]),
                              1 if b["level"] < 35 else (2 if b["level"] < 75 else 3))]
    else:
        allies = expected_team(d, b["level"], size, rng)
    enemies = enemy_team(d, b, diff)
    r = Battle(d, allies, enemies, seed=seed).run()
    return bid, diff, 1 if r["winner"] == 0 else 0


TARGET = {"normal": 0.78, "hard": 0.55, "nightmare": 0.30}


def evaluate(sample, fights, procs, curve, seed0=0):
    jobs = [(b["id"], diff, seed0 + i) for b in sample for diff in ("normal", "hard", "nightmare") for i in range(fights)]
    wins = {}
    with Pool(procs, initializer=_init, initargs=(curve,)) as pool:
        for bid, diff, w in pool.imap_unordered(_run, jobs, chunksize=16):
            wins.setdefault((bid, diff), []).append(w)
    return wins


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--sample", type=int, default=240); ap.add_argument("--fights", type=int, default=12); ap.add_argument("--procs", type=int, default=4)
    ap.add_argument("--calibrate", type=int, default=0, help="몬스터 전력 보정 곡선을 N라운드 피팅하여 economy.json에 기록")
    args = ap.parse_args()
    battles = json.load(open(os.path.join(DATA, "battles.json"), encoding="utf-8"))["battles"]
    econ_path = os.path.join(DATA, "economy.json")
    econ = json.load(open(econ_path, encoding="utf-8"))
    DIFFS = ("normal", "hard", "nightmare")
    BANDS = [f"{lo}-{lo+9}" for lo in range(1, 100, 10)]
    curve = econ.get("enemy_power_curve")
    if not curve or not isinstance(curve.get("bands", {}).get("normal"), dict):
        curve = {"bands": {d: {b: 1.0 for b in BANDS} for d in DIFFS}}
    rng = random.Random(7)
    pool_b = [b for b in battles if b["kind"] in ("regional", "story")]
    for rnd in range(args.calibrate):
        sample = rng.sample(pool_b, max(150, args.sample * 3 // 4))
        wins = evaluate(sample, max(6, args.fights * 2 // 3), args.procs, curve, seed0=1000 * rnd)
        bmap = {b["id"]: b for b in sample}
        acc = {}
        for (bid, diff), ws in wins.items():
            acc.setdefault((diff, band_of(bmap[bid]["level"])), []).extend(ws)
        for (diff, band), ws in acc.items():
            obs = sum(ws) / len(ws)
            f = ((obs + 0.05) / (TARGET[diff] + 0.05)) ** 0.3   # 능력치 배수는 HP·AD·AP에 함께 곱해지므로 완만하게
            f = max(0.8, min(1.25, f))
            curve["bands"][diff][band] = round(max(0.3, min(3.0, curve["bands"][diff].get(band, 1.0) * f)), 3)
        print(f"[calibrate {rnd}] " + " | ".join(f"{d}: " + ",".join(f"{curve['bands'][d][b]:.2f}" for b in BANDS) for d in DIFFS), flush=True)
        econ["enemy_power_curve"] = dict(curve, desc="기대 팀 기준 난이도 목표(보통 78%/어려움 55%/악몽 30%)로 피팅한 몬스터 능력치 배수. 난이도별 × 레벨 10 구간별. 클라이언트는 몬스터 HP·AD·AP에 곱한다.")
        json.dump(econ, open(econ_path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    sample = rng.sample(pool_b, args.sample)
    wins = evaluate(sample, args.fights, args.procs, curve, seed0=99999)
    bmap = {b["id"]: b for b in sample}
    rows = []
    for (bid, diff), ws in wins.items():
        b = bmap[bid]
        rows.append(dict(id=bid, name=b["name_ko"], type=b["type"], level=b["level"], diff=diff, wr=round(sum(ws) / len(ws), 3)))
    summary = {}
    for diff in ("normal", "hard", "nightmare"):
        v = [r["wr"] for r in rows if r["diff"] == diff]
        summary[diff] = dict(mean=round(statistics.mean(v), 3), sd=round(statistics.pstdev(v), 3))
    by_level = {}
    for r in rows:
        band = f"L{(r['level']-1)//20*20+1}-{(r['level']-1)//20*20+20}"
        by_level.setdefault((band, r["diff"]), []).append(r["wr"])
    by_level = {f"{k[0]} {k[1]}": round(statistics.mean(v), 3) for k, v in sorted(by_level.items())}
    os.makedirs(REP, exist_ok=True)
    calib = {f"{d} L{b}": curve["bands"][d][b] for d in DIFFS for b in BANDS}
    json.dump({"summary": summary, "by_level_band": by_level, "calibration": calib, "rows": sorted(rows, key=lambda r: (r["level"], r["id"], r["diff"]))},
              open(os.path.join(REP, "battle_validation.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(summary); print(by_level)


if __name__ == "__main__":
    main()
