# -*- coding: utf-8 -*-
"""
스토리 결전(decisive)·레이드(raid)·토벌(hunt) 전투의 보스 체력 배수 튜닝 (--scope boss, 기본) / 스토리 전투 76 전체의 난이도별 전력 배수 튜닝 (--scope story).
--scope story: 단독(solo) 스토리 전투는 레온(P000, 성급 = 1막·2막 ★1 / 3막·4막 ★2 / 5막 ★3)으로 싸운다(스토리 결투는 레온 고정, 03 §5). 나머지는 기대 팀.
               출력 sim/reports/story_tuning.json + docs/appendix/B9_스토리_전투_튜닝.md
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
from validate_tutorial import ftue_team, story_exp_table

ROOT = os.path.join(os.path.dirname(__file__), "..")
DATA = os.path.join(ROOT, "data")
REP = os.path.join(os.path.dirname(__file__), "reports")
TARGET = {"normal": 0.65, "hard": 0.45, "nightmare": 0.25}
_G = {}


LEON_STAR_BY_ACT = {1: 1, 2: 1, 3: 2, 4: 2, 5: 3}


def _init(curve, scope="boss"):
    battles = json.load(open(os.path.join(DATA, "battles.json"), encoding="utf-8"))
    _G["d"] = GameData(battles=battles)
    _G["b"] = {b["id"]: b for b in battles["battles"]}
    _G["curve"] = curve
    _G["scope"] = scope
    _G["econ"] = json.load(open(os.path.join(DATA, "economy.json"), encoding="utf-8"))
    _G["story_exp"] = story_exp_table(_G["b"]) if scope == "story" else {}


def _run(args):
    bid, diff, seed, hp_mult, pmult = args
    d = _G["d"]; b = _G["b"][bid]
    b = dict(b); b["difficulties"] = {k: dict(v, tuned_power_mult=pmult.get(k, 1.0)) if isinstance(v, dict) and "rewards" in v else v for k, v in b["difficulties"].items()}
    rng = random.Random(seed)
    allies = None
    if _G.get("scope") == "story":
        if b["participation"]["mode"] == "solo":
            allies = [d.hero_spec("P000", LEON_STAR_BY_ACT.get(b["act"], 1))]
        elif b["act"] == 1:
            allies = ftue_team(d, b, _G["econ"], _G["story_exp"])[0]   # 1막: 스토리 진행 로스터(레온+브랜든+영입 일정, 슬롯 규칙)
    allies, enemies, rules = build_scenario(d, b, diff, rng, curve=_G["curve"], allies=allies, boss_hp_override=hp_mult)
    r = Battle(d, allies, enemies, seed=seed, rules=rules).run()
    return bid, diff, 1 if r["winner"] == 0 else 0


def measure(pool, targets, pm_of, fights, seed0):
    """pm_of(bid, diff) → 전력 배수. 반환 wr[(bid, diff)]"""
    jobs = [(b["id"], diff, seed0 + i, (b["enemy"]["boss"]["hp_mult"] if b["enemy"]["boss"] else None), {diff: pm_of(b["id"], diff)}) for b in targets for diff in TARGET for i in range(fights)]
    wins = {}
    for bid, diff, w in pool.imap_unordered(_run, jobs, chunksize=8):
        wins.setdefault((bid, diff), []).append(w)
    return {k: sum(v) / len(v) for k, v in wins.items()}


MARGIN = {"normal": 0.96, "hard": 1.0, "nightmare": 1.035}   # 50% 교차점(절벽) 대비 전력 배수 (전이 폭이 ±5% 수준으로 좁다)
MARGIN_ACT1 = {"normal": 0.85, "hard": 0.95, "nightmare": 1.02}        # 1막(온보딩): 보통 승률 ≥ 75% 목표 (20 §5)
MARGIN_TUTORIAL = {"normal": 0.75, "hard": 0.92, "nightmare": 1.0}     # S001~S004: 보통 ≥ 85~97%
TUTORIAL_IDS = {"S001", "S002", "S003", "S004"}


def margin_of(b, d, scope):
    if scope == "story" and b["id"] in TUTORIAL_IDS: return MARGIN_TUTORIAL[d]
    if scope == "story" and b["act"] == 1: return MARGIN_ACT1[d]
    return MARGIN[d]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--steps", type=int, default=7, help="이분 탐색 단계"); ap.add_argument("--fights", type=int, default=24); ap.add_argument("--procs", type=int, default=4)
    ap.add_argument("--reset", action="store_true", help="보스 체력 배수를 설계값으로 초기화")
    ap.add_argument("--scope", choices=["boss", "story"], default="boss")
    args = ap.parse_args()
    path = os.path.join(DATA, "battles.json")
    doc = json.load(open(path, encoding="utf-8"))
    econ = json.load(open(os.path.join(DATA, "economy.json"), encoding="utf-8"))
    curve = econ.get("enemy_power_curve", {})
    if args.scope == "story":
        targets = [b for b in doc["battles"] if b["kind"] == "story"]
    else:
        targets = [b for b in doc["battles"] if b["kind"] == "story" and b["enemy"]["boss"] and b["type"] in ("decisive", "raid", "hunt")]
    DESIGN_HP = {"hunt": 2.0, "raid": 4.0, "decisive": 3.0}
    for b in targets:
        if b["enemy"]["boss"] and b["type"] in DESIGN_HP and (args.reset or not b["enemy"]["boss"].get("tuned")): b["enemy"]["boss"]["hp_mult"] = DESIGN_HP[b["type"]]
    # 팀전 승률은 전력 배수에 대해 계단 함수에 가깝다(고정 매치업은 거의 결정론적). 따라서 승률 자체가 아니라
    # '승률 50% 교차점(절벽)'을 이분 탐색으로 찾고, 난이도별 여유 배수(MARGIN)를 곱해 전력 배수를 정한다.
    lo = {(b["id"], d): 0.3 for b in targets for d in TARGET}; hi = {(b["id"], d): 2.5 for b in targets for d in TARGET}
    hist = []
    with Pool(args.procs, initializer=_init, initargs=(curve, args.scope)) as pool:
        for step in range(args.steps):
            mid = {k: (lo[k] + hi[k]) / 2 for k in lo}
            wr = measure(pool, targets, lambda bid, d: mid[(bid, d)], args.fights, 10000 * step)
            for k in lo:
                if wr[k] >= 0.5: lo[k] = mid[k]   # 아직 이김 → 더 강하게
                else: hi[k] = mid[k]
            print(f"[bisect {step}] mean cliff={statistics.mean((lo[k]+hi[k])/2 for k in lo):.3f}", flush=True)
            hist.append({"step": step, "mean_cliff": statistics.mean((lo[k] + hi[k]) / 2 for k in lo)})
        cliff = {k: round((lo[k] + hi[k]) / 2, 3) for k in lo}
        pm = {b["id"]: {d: round(max(0.3, min(2.5, cliff[(b["id"], d)] * margin_of(b, d, args.scope))), 3) for d in TARGET} for b in targets}
        wr = measure(pool, targets, lambda bid, d: pm[bid][d], args.fights * 2, 999999)
    devs = [wr[(b["id"], d)] - TARGET[d] for b in targets for d in TARGET]
    print(f"[boss final] mean dev={statistics.mean(devs):+.3f} sd={statistics.pstdev(devs):.3f}", flush=True)
    for b in targets:
        if b["enemy"]["boss"]: b["enemy"]["boss"]["tuned"] = True
        for d in TARGET:
            b["difficulties"][d]["tuned_power_mult"] = pm[b["id"]][d]
            b["difficulties"][d]["power_cliff"] = cliff[(b["id"], d)]
    json.dump(doc, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    rows = [dict(id=b["id"], name=b["name_ko"], act=b["act"], type=b["type"], mode=b["participation"]["mode"], level=b["level"],
                 boss=(b["enemy"]["boss"]["name_ko"] if b["enemy"]["boss"] else None), hp_mult=(b["enemy"]["boss"]["hp_mult"] if b["enemy"]["boss"] else None),
                 cliff={d: cliff[(b["id"], d)] for d in TARGET}, power_mult=pm[b["id"]], wr={d: round(wr[(b["id"], d)], 3) for d in TARGET}) for b in targets]
    out_name = "story_tuning.json" if args.scope == "story" else "boss_tuning.json"
    json.dump({"targets": TARGET, "margin": MARGIN, "scope": args.scope, "history": hist, "rows": rows}, open(os.path.join(REP, out_name), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    for r in rows: print(r["id"], r["name"], r["boss"], r["cliff"], r["wr"])
    if args.scope == "story":
        L = ["# 부록 B9. 스토리 전투 76 개별 튜닝", "",
             f"(자동 생성: `python3 sim/tune_bosses.py --scope story --steps {args.steps} --fights {args.fights}`.) 스토리 전투는 손으로 짠 세트피스이므로 지역 전투의 레벨 구간 보정(B3)과 별도로 **전투마다** 난이도별 전력 배수를 맞춘다.",
             f"목표(기대 팀 기준): 보통 {TARGET['normal']:.0%} / 어려움 {TARGET['hard']:.0%} / 악몽 {TARGET['nightmare']:.0%}. 단독 전투는 레온(1·2막 ★1, 3·4막 ★2, 5막 ★3) 고정. 방법은 B7과 같은 50% 절벽 이분 탐색 + 여유 배수.",
             f"**1막은 온보딩 구간**이므로 기대 팀 대신 스토리 진행 로스터(레온 + 브랜든 + 영입 일정, 참전 슬롯 = max(레벨 슬롯, 최소 인원), 20 §4·§10)로 싸우고 여유 배수를 낮춘다: 튜토리얼 S001~S004 보통 {MARGIN_TUTORIAL['normal']}, 그 외 1막 보통 {MARGIN_ACT1['normal']} (2막 이후 {MARGIN['normal']}).", "",
             f"최종 평균 승률: 보통 {statistics.mean(wr[(b['id'],'normal')] for b in targets):.0%} / 어려움 {statistics.mean(wr[(b['id'],'hard')] for b in targets):.0%} / 악몽 {statistics.mean(wr[(b['id'],'nightmare')] for b in targets):.0%} (편차 평균 {statistics.mean(devs):+.3f}, sd {statistics.pstdev(devs):.3f})", "",
             "| 막 | ID | 전투 | 유형 · 참전 | 레벨 | 보스 | 절벽(보통/어려움/악몽) | 전력 배수 | 승률(보통/어려움/악몽) |", "|---|---|---|---|---|---|---|---|---|"]
        for r in rows:
            L.append(f"| {r['act']} | {r['id']} | {r['name']} | {r['type']} · {r['mode']} | {r['level']} | {r['boss'] or '—'} | {r['cliff']['normal']:.2f}/{r['cliff']['hard']:.2f}/{r['cliff']['nightmare']:.2f} | {r['power_mult']['normal']:.2f}/{r['power_mult']['hard']:.2f}/{r['power_mult']['nightmare']:.2f} | {r['wr']['normal']:.0%}/{r['wr']['hard']:.0%}/{r['wr']['nightmare']:.0%} |")
        low = [r for r in rows if r["cliff"]["normal"] < 0.5]
        L += ["", "- 절벽(보통) < 0.5인 전투는 기대 팀 대비 설계 편성이 2배 이상 강하다는 뜻이다(적 수·웨이브 과다). 전력 배수로 맞춰 두었지만 콘텐츠 측 재설계(적 수 감소) 후보: " + (", ".join(f"{r['id']}({r['cliff']['normal']:.2f})" for r in low) if low else "없음") + "."]
        open(os.path.join(ROOT, "docs", "appendix", "B9_스토리_전투_튜닝.md"), "w", encoding="utf-8").write("\n".join(L) + "\n")


if __name__ == "__main__":
    main()
