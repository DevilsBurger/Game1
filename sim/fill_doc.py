# -*- coding: utf-8 -*-
"""sim/reports/*.json → docs/09_밸런스_시뮬레이션.md 결과 요약 섹션 치환."""
import json, os, statistics
from collections import defaultdict

HERE = os.path.dirname(__file__)
REP = os.path.join(HERE, "reports")
DOC = os.path.join(HERE, "..", "docs", "09_밸런스_시뮬레이션.md")


def hero_block():
    r = json.load(open(os.path.join(REP, "hero_balance.json"), encoding="utf-8"))
    hs = r["heroes"]
    L = ["| 성급 | 평균 승률 | 표준편차 | ±5%p 밴드 내 | 최소 | 최대 |", "|---|---|---|---|---|---|"]
    for key, label in (("wr_team", "★1"), ("wr_team_star2", "★2"), ("wr_team_star3", "★3")):
        v = [x[key] for x in hs]
        L.append(f"| {label} | {statistics.mean(v):.3f} | {statistics.pstdev(v):.3f} | {sum(1 for w in v if abs(w-0.5)<=0.05)/len(v):.1%} | {min(v):.3f} | {max(v):.3f} |")
    L += ["", "계층 간 교차 전력(5v5 왼쪽 팀 승률): " + ", ".join(f"{k} {v:.0%}" for k, v in r["cross_tier"].items()), ""]
    L += ["스킬 원형별 평균 밸런스 배율(설계 기본값 대비; <1 = 기본값이 과강, >1 = 과약):", "", "| 원형 | 영웅 수 | ★1 | ★2 | ★3 |", "|---|---|---|---|---|"]
    ba = defaultdict(list)
    for x in hs: ba[x["arche"]].append(x["star_mult"])
    for a, v in sorted(ba.items(), key=lambda kv: statistics.mean(s[0] for s in kv[1])):
        L.append(f"| {a} | {len(v)} | {statistics.mean(s[0] for s in v):.2f} | {statistics.mean(s[1] for s in v):.2f} | {statistics.mean(s[2] for s in v):.2f} |")
    L += ["", "밴드 밖 영웅(★1 기준):"]
    out = [x for x in hs if abs(x["wr_team"] - 0.5) > 0.05]
    L.append(", ".join(f"{x['name']}({x['wr_team']:.2f})" for x in out) if out else "없음")
    return "\n".join(L)


def item_block():
    p = os.path.join(REP, "item_balance.json")
    if not os.path.exists(p): return "(미실행)"
    r = json.load(open(p, encoding="utf-8"))
    target = {"completed": 0.11, "radiant": 0.20, "artifact": 0.14, "support": 0.08, "national": 0.12}
    byc = defaultdict(list)
    for x in r["items"]: byc[x["category"]].append(x)
    L = [f"기준선(아이템 없는 미러전, 좌우 교대) 승률 {r['base']:.3f}.", "", "| 분류 | 개수 | 목표 Δ | 평균 Δ | 표준편차 | 목표 ±3%p 내 | 배율 범위 |", "|---|---|---|---|---|---|---|"]
    for c, xs in byc.items():
        v = [x["delta"] for x in xs]; m = [x["mult"] for x in xs]
        L.append(f"| {c} | {len(xs)} | {target[c]:+.2f} | {statistics.mean(v):+.3f} | {statistics.pstdev(v):.3f} | {sum(1 for d in v if abs(d-target[c])<=0.03)/len(v):.0%} | {min(m):.2f}~{max(m):.2f} |")
    L += ["", "가장 크게 조정된 아이템(배율 기준):"]
    xs = sorted(r["items"], key=lambda x: abs(x["mult"] - 1), reverse=True)[:12]
    L.append(", ".join(f"{x['name']} ×{x['mult']:.2f}" for x in xs))
    return "\n".join(L)


def battle_block():
    p = os.path.join(REP, "battle_validation.json")
    if not os.path.exists(p): return "(미실행)"
    r = json.load(open(p, encoding="utf-8"))
    L = ["| 난이도 | 기대 팀 평균 승률 | 목표 |", "|---|---|---|"]
    tgt = {"normal": "70~85%", "hard": "45~65%", "nightmare": "20~40%"}
    for d, v in r["summary"].items(): L.append(f"| {d} | {v['mean']:.1%} | {tgt[d]} |")
    L += ["", "레벨 구간별: " + ", ".join(f"{k} {v:.0%}" for k, v in r["by_level_band"].items())]
    if "calibration" in r:
        L += ["", "몬스터 전력 보정 곡선(economy.json `enemy_power_curve`): " + ", ".join(f"{k}: ×{v:.2f}" for k, v in r["calibration"].items())]
    return "\n".join(L)


def main():
    s = open(DOC, encoding="utf-8").read()
    import re
    s = re.sub(r"### 6\.1 영웅\n.*?\n### 6\.2", "### 6.1 영웅\n" + hero_block() + "\n\n### 6.2", s, flags=re.S)
    s = re.sub(r"### 6\.2 아이템\n.*?\n### 6\.3", "### 6.2 아이템\n" + item_block() + "\n\n### 6.3", s, flags=re.S)
    s = re.sub(r"### 6\.3 전투 난이도\n.*?\n## 7\.", "### 6.3 전투 난이도\n" + battle_block() + "\n\n## 7.", s, flags=re.S)
    open(DOC, "w", encoding="utf-8").write(s)
    print("doc filled")


if __name__ == "__main__":
    main()
