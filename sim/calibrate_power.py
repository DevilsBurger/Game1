# -*- coding: utf-8 -*-
"""
전력 → 전투 레벨 환산 측정 (경제 시뮬레이션 `run_economy.py`의 전력 모델 보정용).

실제 전투 엔진으로 '계층 t · 성급 s · 아이템 상태' 단일 구성 팀이 레벨별 지역 전투(보통 난이도, 몬스터 전력 보정 곡선 적용)를
상대로 내는 승률 곡선을 재고, 로지스틱으로 맞춰 승률 76%가 되는 전투 레벨(L76)과 기울기(k)를 구한다.
  승률(L) = 1 / (1 + exp((L − L50) / k)),  L76 = L50 − k·ln(0.76/0.24)
아이템 상태: none(없음) / completed(조합 3개 무작위) / radiant(빛나는 3개 무작위). 아이템은 역할을 가리지 않고 무작위로 끼우므로 보수적인 값이다.
난이도 간격: 아이템 없는 팀으로 어려움·악몽의 L76을 재서 보통과의 차이를 구한다.
출력: sim/reports/power_calibration.json
"""
import os, sys, json, math, random, argparse
from multiprocessing import Pool
sys.path.insert(0, os.path.dirname(__file__))
from engine import GameData, Battle  # noqa: E402
from scenario import build_scenario  # noqa: E402

ROOT = os.path.join(os.path.dirname(__file__), "..")
DATA = os.path.join(ROOT, "data"); REP = os.path.join(os.path.dirname(__file__), "reports")
ROLES = ["knight", "guardian", "warrior", "duelist", "ranger", "mage", "priest", "assassin", "artillerist", "bard"]
LEVELS = list(range(5, 96, 5))   # 지역 전투 최고 레벨 94
_G = {}


def _init():
    battles = json.load(open(os.path.join(DATA, "battles.json"), encoding="utf-8"))
    _G["d"] = GameData(battles=battles)
    _G["b"] = {b["id"]: b for b in battles["battles"]}
    _G["curve"] = json.load(open(os.path.join(DATA, "economy.json"), encoding="utf-8")).get("enemy_power_curve", {})
    items = json.load(open(os.path.join(DATA, "items.json"), encoding="utf-8"))["items"]
    _G["items"] = {c: sorted(i["id"] for i in items if i["category"] == c) for c in ("completed", "radiant")}


def team(d, tier, star, size, item_state, rng):
    pool = [h for h in d.heroes.values() if h["tier"] == tier]
    ids = []
    for r in ROLES[:size]:
        cands = [h["id"] for h in pool if h["class"] == r and h["id"] not in ids] or [h["id"] for h in pool if h["id"] not in ids]
        ids.append(rng.choice(sorted(cands)))
    return [d.hero_spec(h, star, items=(rng.sample(_G["items"][item_state], 3) if item_state != "none" else [])) for h in ids]


def _run(args):
    tier, star, item_state, diff, bid, seed = args
    d = _G["d"]; b = _G["b"][bid]; rng = random.Random(seed)
    want = {"solo": 1, "squad": 4, "team": 6, "free": 6, "army": (10 if b["level"] >= 70 else 8)}[b["participation"]["mode"]]
    size = max(b["participation"]["min"], min(b["participation"]["max"], want))
    allies, enemies, rules = build_scenario(d, b, diff, rng, curve=_G["curve"], allies=team(d, tier, star, size, item_state, rng))
    r = Battle(d, allies, enemies, seed=seed, rules=rules).run()
    return (tier, star, item_state, diff, b["level"]), 1 if r["winner"] == 0 else 0


def fit(points):
    """points: [(level, wins, n)] → (L50, k) 로지스틱 최대우도(격자 탐색). 전 구간 승률이 한쪽으로 쏠리면 None."""
    tot_w = sum(w for _, w, _ in points); tot_n = sum(n for _, _, n in points)
    if tot_w < 0.03 * tot_n or min(w / n for _, w, n in points) > 0.85: return None   # 최고 레벨에서도 85% 넘게 이기면 측정 범위 밖
    best = None
    for l50x2 in range(-80, 361):
        l50 = l50x2 / 2.0
        for k10 in range(20, 301, 5):
            k = k10 / 10.0; ll = 0.0
            for lv, w, n in points:
                p = min(1 - 1e-6, max(1e-6, 1 / (1 + math.exp((lv - l50) / k))))
                ll += w * math.log(p) + (n - w) * math.log(1 - p)
            if best is None or ll > best[0]: best = (ll, l50, k)
    return best[1], best[2]


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--battles", type=int, default=8); ap.add_argument("--fights", type=int, default=8); ap.add_argument("--procs", type=int, default=4)
    args = ap.parse_args()
    battles = json.load(open(os.path.join(DATA, "battles.json"), encoding="utf-8"))["battles"]
    rng = random.Random(7); by_level = {}
    for lv in LEVELS:
        cands = sorted((b for b in battles if b["kind"] == "regional" and abs(b["level"] - lv) <= 2 and b["participation"]["mode"] != "solo"), key=lambda b: b["id"])
        by_level[lv] = [b["id"] for b in rng.sample(cands, min(args.battles, len(cands)))]
    jobs = []; seed = 0
    for tier in range(1, 6):
        for star in (1, 2, 3):
            # 아이템 효과는 보통 난이도에서, 난이도 간격(어려움·악몽)은 아이템 없는 팀으로 잰다
            for st, diff in (("none", "normal"), ("completed", "normal"), ("radiant", "normal"), ("none", "hard"), ("none", "nightmare")):
                for lv in LEVELS:
                    for bid in by_level[lv]:
                        for _ in range(args.fights):
                            seed += 1; jobs.append((tier, star, st, diff, bid, seed))
    res = {}
    with Pool(args.procs, initializer=_init) as pool:
        for key, w in pool.imap_unordered(_run, jobs, chunksize=64):
            t, s, st, diff, lv = key; grid = min(LEVELS, key=lambda g: abs(g - lv))
            c = res.setdefault((t, s, st, diff), {}).setdefault(grid, [0, 0]); c[0] += w; c[1] += 1
    out = {"method": "승률 76% 전투 레벨(L76) = L50 − k·ln(0.76/0.24), 지역 전투, 팀 인원은 참전 모드 기준. L76이 null이면 측정 범위(레벨 95) 밖", "levels": LEVELS, "fights": len(jobs), "configs": {}}
    for (t, s, st, diff), g in sorted(res.items()):
        pts = [(lv, g[lv][0], g[lv][1]) for lv in sorted(g)]
        f = fit(pts)
        out["configs"][f"t{t}_s{s}_{st}_{diff}"] = {"tier": t, "star": s, "items": st, "difficulty": diff, "winrate": {str(lv): round(w / n, 3) for lv, w, n in pts},
                                             "L50": (f[0] if f else None), "k": (f[1] if f else None), "L76": (round(f[0] - f[1] * math.log(0.76 / 0.24), 1) if f else None)}
    os.makedirs(REP, exist_ok=True)
    json.dump(out, open(os.path.join(REP, "power_calibration.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    for k, v in out["configs"].items(): print(k, "L76", v["L76"], "k", v["k"], [v["winrate"][str(l)] for l in (10, 30, 50, 70, 90)])


if __name__ == "__main__":
    main()
