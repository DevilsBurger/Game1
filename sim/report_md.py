# -*- coding: utf-8 -*-
"""sim/reports/*.json → 마크다운 보고서 (docs/appendix/B1_영웅_밸런스.md, B2_아이템_밸런스.md, B3_전투_난이도_검증.md)."""
import json, os, statistics
from collections import defaultdict

HERE = os.path.dirname(__file__)
REP = os.path.join(HERE, "reports")
OUT = os.path.join(HERE, "..", "docs", "appendix")
os.makedirs(OUT, exist_ok=True)
traits = json.load(open(os.path.join(HERE, "..", "data", "traits.json"), encoding="utf-8"))
ON = {o["key"]: o["name_ko"] for o in traits["origins"]}; CN = {c["key"]: c["name_ko"] for c in traits["classes"]}


def band(v, w=0.05): return "✅" if abs(v - 0.5) <= w else ("⚠️" if abs(v - 0.5) <= 0.08 else "❌")


def hero_md():
    r = json.load(open(os.path.join(REP, "hero_balance.json"), encoding="utf-8"))
    L = ["# 부록 B1. 영웅 밸런스 시뮬레이션 결과", "", "자동 생성: `python sim/run_balance.py` → `python sim/report_md.py`.", "",
         "## 수렴 이력", "", "| 반복 | ★1 sd | ★1 밴드 내 | ★2 sd | ★2 밴드 내 | ★3 sd | ★3 밴드 내 |", "|---|---|---|---|---|---|---|"]
    for h in r["history"]:
        if "star1" in h:
            L.append(f"| {h['iter']} | {h['star1']['sd']:.3f} | {h['star1']['in_band']:.0%} | {h['star2']['sd']:.3f} | {h['star2']['in_band']:.0%} | {h['star3']['sd']:.3f} | {h['star3']['in_band']:.0%} |")
    hs = r["heroes"]
    for key, label in (("wr_team", "★1"), ("wr_team_star2", "★2"), ("wr_team_star3", "★3")):
        v = [x[key] for x in hs]
        L.append(f"\n최종 {label} 팀전 참전 승률: 평균 {statistics.mean(v):.3f}, 표준편차 {statistics.pstdev(v):.3f}, ±5%p 밴드 내 {sum(1 for w in v if abs(w-0.5)<=0.05)/len(v):.1%}, 최소 {min(v):.3f}, 최대 {max(v):.3f}")
    L += ["", "## 계층 간 교차 전력 (5v5, 왼쪽 팀 승률)", "", "| 대결 | 승률 |", "|---|---|"]
    for k, v in r["cross_tier"].items(): L.append(f"| {k} | {v:.1%} |")
    L += ["", "## 직업별 평균 (★1)", "", "| 직업 | 평균 승률 | 평균 피해 | 평균 받은 피해 | 평균 치유 |", "|---|---|---|---|---|"]
    byc = defaultdict(list)
    for x in hs: byc[x["cls"]].append(x)
    for c, xs in byc.items():
        L.append(f"| {CN[c]} | {statistics.mean(y['wr_team'] for y in xs):.3f} | {statistics.mean(y['dmg'] for y in xs):.0f} | {statistics.mean(y['taken'] for y in xs):.0f} | {statistics.mean(y['heal'] for y in xs):.0f} |")
    L += ["", "## 출신별 평균 (★1)", "", "| 출신 | 평균 승률 |", "|---|---|"]
    byo = defaultdict(list)
    for x in hs: byo[x["origin"]].append(x["wr_team"])
    for o, v in byo.items(): L.append(f"| {ON[o]} | {statistics.mean(v):.3f} |")
    L += ["", "## 영웅별 결과", "", "| ID | 영웅 | 계층 | 출신 | 직업 | 원형 | ★1 승률 | ★2 승률 | ★3 승률 | 1v1(★2) | 피해 | 받은 피해 | 치유 | 배율 ★1/★2/★3 |", "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for x in hs:
        sm = x["star_mult"]
        L.append(f"| {x['id']} | {x['name']} | {x['tier']} | {ON[x['origin']]} | {CN[x['cls']]} | {x['arche']} | {x['wr_team']:.3f} {band(x['wr_team'])} | {x['wr_team_star2']:.3f} {band(x['wr_team_star2'])} | {x['wr_team_star3']:.3f} {band(x['wr_team_star3'])} | {x['wr_duel']:.2f} | {x['dmg']} | {x['taken']} | {x['heal']} | {sm[0]:.2f}/{sm[1]:.2f}/{sm[2]:.2f} |")
    open(os.path.join(OUT, "B1_영웅_밸런스.md"), "w", encoding="utf-8").write("\n".join(L) + "\n")


def item_md():
    p = os.path.join(REP, "item_balance.json")
    if not os.path.exists(p): return
    r = json.load(open(p, encoding="utf-8"))
    L = ["# 부록 B2. 아이템 밸런스 시뮬레이션 결과", "", f"기준: 계층 3 기준 팀 6종의 교차전(5v5, i≠j 30매치업, ★1·★2 혼합, 좌우 교대), 캐리어 1명에게 아이템 1개 장착 시 매치업별 승률 상승분 Δ의 평균. 기준선(아이템 없음) 평균 승률 {r['base']:.3f}.", "",
         "## 분류별 목표/결과", "", "| 분류 | 목표 Δ | 평균 Δ | 표준편차 | 개수 |", "|---|---|---|---|---|"]
    target = {"completed": 0.11, "radiant": 0.20, "artifact": 0.14, "support": 0.08, "national": 0.12}
    byc = defaultdict(list)
    for x in r["items"]: byc[x["category"]].append(x["delta"])
    for c, v in byc.items(): L.append(f"| {c} | {target.get(c, '-')} | {statistics.mean(v):+.3f} | {statistics.pstdev(v):.3f} | {len(v)} |")
    L += ["", "## 수렴 이력", ""]
    for h in r["history"]: L.append(f"- 반복 {h['iter']}: 기준선 {h['base']:.3f}, " + ", ".join(f"{c} 평균 {v[0]:+.3f}(sd {v[1]:.3f})" for c, v in h["summary"].items()))
    L += ["", "## 아이템별 결과", "", "| ID | 아이템 | 분류 | Δ 승률 | 배율 | 캐리어 역할 |", "|---|---|---|---|---|---|"]
    for x in sorted(r["items"], key=lambda x: (x["category"], x["id"])):
        L.append(f"| {x['id']} | {x['name']} | {x['category']} | {x['delta']:+.3f} | {x['mult']:.2f} | {', '.join(x['carriers'])} |")
    open(os.path.join(OUT, "B2_아이템_밸런스.md"), "w", encoding="utf-8").write("\n".join(L) + "\n")


def battle_md():
    p = os.path.join(REP, "battle_validation.json")
    if not os.path.exists(p): return
    r = json.load(open(p, encoding="utf-8"))
    L = ["# 부록 B3. 전투 난이도 검증", "", "지역·스토리 전투 표본에 대해 '레벨에 맞는 기대 팀'(계층 = 1+레벨/22, 성급 = 레벨 35/75 기준)으로 난이도별 승률을 측정.", "",
         "| 난이도 | 평균 승률 | 표준편차 |", "|---|---|---|"]
    for d, v in r["summary"].items(): L.append(f"| {d} | {v['mean']:.3f} | {v['sd']:.3f} |")
    L += ["", "## 레벨 구간별", "", "| 구간 · 난이도 | 승률 |", "|---|---|"]
    for k, v in r["by_level_band"].items(): L.append(f"| {k} | {v:.3f} |")
    L += ["", "## 표본 전투", "", "| ID | 전투 | 유형 | 레벨 | 난이도 | 승률 |", "|---|---|---|---|---|---|"]
    for x in r["rows"]: L.append(f"| {x['id']} | {x['name']} | {x['type']} | {x['level']} | {x['diff']} | {x['wr']:.2f} |")
    open(os.path.join(OUT, "B3_전투_난이도_검증.md"), "w", encoding="utf-8").write("\n".join(L) + "\n")


if __name__ == "__main__":
    hero_md(); item_md(); battle_md(); print("reports written")
