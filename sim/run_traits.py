# -*- coding: utf-8 -*-
"""
특성(출신/직업) 임계값 가치 측정 및 조정.

측정: 특성 T를 레벨 L로 활성화한 8인 팀 A(보유자 L명 + 무작위 비보유자) vs 계층 매칭 무작위 8인 팀 B.
      같은 시드로 '특성 활성'과 '특성 비활성(disable_traits)' 두 번 싸워 승리 차이의 평균 = 그 임계값의 **한계 가치**.
      (편성 자체의 강약 — 예: 수호자 6명은 화력 부족 — 을 분리해 시너지 효과만 잰다.)
목표: 출신 2/4/6/8 → +5/+14/+28/+42%p, 직업 2/4/6 → +6/+16/+32%p (±4%p).
조정: traits.json effects에 balance.mult[level] 배율을 두고 엔진이 리스트형 수치에 곱한다.
출력: sim/reports/trait_balance.json, data/traits.json 갱신
"""
import argparse, json, os, sys, random, statistics, time
from multiprocessing import Pool
sys.path.insert(0, os.path.dirname(__file__))
from engine import GameData, Battle

ROOT = os.path.join(os.path.dirname(__file__), "..")
DATA = os.path.join(ROOT, "data")
REP = os.path.join(os.path.dirname(__file__), "reports")
# 한계 가치(승률 차이) 목표. 1차 측정 결과 6·8단계 수직 구성의 한계 가치는 구조적으로 크므로(TFT에서도 수직 시너지가 승부를 가름)
# 상위 단계 목표를 TFT 수준으로 상향: 출신 2/4/6/8 → +5/+14/+28/+42%p, 직업 2/4/6 → +6/+16/+32%p.
TARGET_ORIGIN = {2: 0.05, 4: 0.14, 6: 0.28, 8: 0.42}
TARGET_CLASS = {2: 0.06, 4: 0.16, 6: 0.32}
_G = {}


def _init(heroes_doc, traits_doc):
    _G["d"] = GameData(heroes=heroes_doc, traits=traits_doc)


def _fight(args):
    """같은 시드·편성으로 특성 활성/비활성 2회 → 한계 가치(활성 승 - 비활성 승)."""
    a_ids, b_ids, star, seed, key = args
    d = _G["d"]
    side = seed & 1
    A = [d.hero_spec(h, star) for h in a_ids]; B = [d.hero_spec(h, star) for h in b_ids]
    out = []
    for disable in (False, True):
        rules = {"disable_traits": {side: {key[1]}}} if disable else {}
        r = Battle(d, A, B, seed=seed, rules=rules).run() if side == 0 else Battle(d, B, A, seed=seed, rules=rules).run()
        out.append(1 if r["winner"] == side else 0)
    return key, out[0] - out[1]


def build_jobs(heroes, traits, fights, seed_base, team_size=8):
    rng = random.Random(seed_base)
    by_tier = {}
    for h in heroes: by_tier.setdefault(h["tier"], []).append(h["id"])
    hid = {h["id"]: h for h in heroes}
    jobs = []
    specs = [("origin", o["key"], o["thresholds"]) for o in traits["origins"]] + [("class", c["key"], c["thresholds"]) for c in traits["classes"]]
    for kind, key, ths in specs:
        holders = [h["id"] for h in heroes if (h["origin"] if kind == "origin" else h["class"]) == key]
        others = [h["id"] for h in heroes if h["id"] not in holders]
        for L in ths:
            nxt = [t for t in ths if t > L]
            for k in range(fights):
                # 보유자 L명 (다음 임계값 미만), 나머지 무작위 비보유자. 비보유자 중 같은 다른 특성이 4명 이상 겹치지 않게 함.
                hs = rng.sample(holders, L)
                fill = rng.sample(others, team_size - L)
                a = hs + fill
                # B: A와 계층을 1:1 매칭한 무작위 영웅 (보유자 제외하여 같은 특성 효과가 B에 생기지 않도록)
                b = []
                for h in a:
                    cands = [x for x in by_tier[hid[h]["tier"]] if x not in a and x not in b and x not in holders]
                    b.append(rng.choice(cands))
                star = 1 if k % 3 else 2
                jobs.append((a, b, star, seed_base + len(jobs), (kind, key, L)))
    rng.shuffle(jobs)
    return jobs


def evaluate(pool, heroes, traits, fights, seed_base):
    jobs = build_jobs(heroes, traits, fights, seed_base)
    wins = {}; cnt = {}
    for key, w in pool.imap_unordered(_fight, jobs, chunksize=16):
        wins[key] = wins.get(key, 0) + w; cnt[key] = cnt.get(key, 0) + 1
    return {k: wins[k] / cnt[k] for k in wins}, {k: cnt[k] for k in cnt}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--iters", type=int, default=3); ap.add_argument("--fights", type=int, default=120); ap.add_argument("--procs", type=int, default=4)
    ap.add_argument("--seed", type=int, default=777)
    args = ap.parse_args()
    heroes_doc = json.load(open(os.path.join(DATA, "heroes.json"), encoding="utf-8"))
    traits_doc = json.load(open(os.path.join(DATA, "traits.json"), encoding="utf-8"))
    heroes = heroes_doc["heroes"]
    for t in traits_doc["origins"] + traits_doc["classes"]:
        t.setdefault("balance", {"mult": [1.0] * len(t["thresholds"])})
    history = []
    t0 = time.time()
    for it in range(args.iters + 1):
        with Pool(args.procs, initializer=_init, initargs=(heroes_doc, traits_doc)) as pool:
            val, n = evaluate(pool, heroes, traits_doc, args.fights if it < args.iters else args.fights * 2, args.seed + it * 10000)
        devs = []
        for (kind, key, L), v in val.items():
            tgt = (TARGET_ORIGIN if kind == "origin" else TARGET_CLASS)[L]
            devs.append(v - tgt)
        print(f"[trait iter {it}] mean dev={statistics.mean(devs):+.3f} sd={statistics.pstdev(devs):.3f} in-band(±4%p)={sum(1 for x in devs if abs(x)<=0.04)/len(devs):.0%} t={time.time()-t0:.0f}s", flush=True)
        history.append({"iter": it, "mean_dev": statistics.mean(devs), "sd": statistics.pstdev(devs), "in_band": sum(1 for x in devs if abs(x) <= 0.04) / len(devs)})
        if it == args.iters: break
        for t in traits_doc["origins"] + traits_doc["classes"]:
            kind = "origin" if t in traits_doc["origins"] else "class"
            for li, L in enumerate(t["thresholds"]):
                v = val.get((kind, t["key"], L))
                if v is None: continue
                tgt = (TARGET_ORIGIN if kind == "origin" else TARGET_CLASS)[L]
                if abs(v - tgt) <= 0.02: continue
                f = ((tgt + 0.08) / max(0.01, v + 0.08)) ** 0.6
                f = max(0.7, min(1.4, f))
                t["balance"]["mult"][li] = round(max(0.2, min(3.0, t["balance"]["mult"][li] * f)), 4)
        json.dump(traits_doc, open(os.path.join(DATA, "traits.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    rows = []
    name = {t["key"]: t["name_ko"] for t in traits_doc["origins"] + traits_doc["classes"]}
    mult = {t["key"]: t["balance"]["mult"] for t in traits_doc["origins"] + traits_doc["classes"]}
    for (kind, key, L), v in sorted(val.items(), key=lambda kv: (kv[0][0], kv[0][1], kv[0][2])):
        tgt = (TARGET_ORIGIN if kind == "origin" else TARGET_CLASS)[L]
        ths = next(t["thresholds"] for t in traits_doc["origins"] + traits_doc["classes"] if t["key"] == key)
        rows.append(dict(kind=kind, key=key, name=name[key], level=L, value=round(v, 3), target=tgt, n=n[(kind, key, L)], mult=mult[key][ths.index(L)]))
    json.dump({"history": history, "targets": {"origin": TARGET_ORIGIN, "class": TARGET_CLASS}, "rows": rows}, open(os.path.join(REP, "trait_balance.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("done")


if __name__ == "__main__":
    main()
