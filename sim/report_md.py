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
         "## 분류별 목표/결과", "", "| 분류 | 목표 Δ | 평균 Δ | 편차 | 개수 |", "|---|---|---|---|---|"]
    byc = defaultdict(list)
    for x in r["items"]: byc[x["category"]].append(x)
    for c, xs in byc.items():
        L.append(f"| {c} | {statistics.mean(x.get('target', 0) for x in xs):+.3f}(역할 보정 평균) | {statistics.mean(x['delta'] for x in xs):+.3f} | {statistics.pstdev(x['delta'] - x.get('target', 0) for x in xs):.3f}(목표 대비) | {len(xs)} |")
    L += ["", "역할 보정: 탱커 캐리어 ×1.5, 브루저 ×1.25 (전열 아이템은 구조적으로 팀 승률 기여가 큼)."]
    L += ["", "## 수렴 이력", ""]
    for h in r["history"]: L.append(f"- 반복 {h['iter']}: 기준선 {h['base']:.3f}, " + ", ".join(f"{c} 평균 {v[0]:+.3f}(sd {v[1]:.3f})" for c, v in h["summary"].items()))
    flagged = [x for x in r["items"] if x.get("flag")]
    L += ["", f"## 상황 의존형 아이템 (배율 한계 0.4~2.0에서도 목표 밖, 디자이너 검토 대상: {len(flagged)}개)", ""]
    for x in flagged: L.append(f"- {x['name']} ({x['category']}): Δ {x['delta']:+.3f}, 배율 ×{x['mult']:.2f}")
    L += ["", "## 아이템별 결과", "", "| ID | 아이템 | 분류 | 목표 Δ | Δ 승률 | 배율 | 캐리어 역할 | 비고 |", "|---|---|---|---|---|---|---|---|"]
    for x in sorted(r["items"], key=lambda x: (x["category"], x["id"])):
        L.append(f"| {x['id']} | {x['name']} | {x['category']} | {x.get('target', 0):+.2f} | {x['delta']:+.3f} | {x['mult']:.2f} | {', '.join(x['carriers'])} | {x.get('flag','')} |")
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


def trait_md():
    p = os.path.join(REP, "trait_balance.json")
    if not os.path.exists(p): return
    r = json.load(open(p, encoding="utf-8"))
    L = ["# 부록 B4. 특성 임계값 가치 측정", "", "특성 T를 레벨 L로 활성화한 8인 팀(보유자 L명 + 무작위 비보유자) vs 계층 1:1 매칭 무작위 8인 팀(보유자 제외). 같은 시드로 특성 활성/비활성 두 번 싸운 승리 차이의 평균 = **한계 가치**(편성 강약과 분리된 시너지 효과).",
         f"목표: 출신 {r['targets']['origin']}, 직업 {r['targets']['class']} (±4%p). 조정은 traits.json effects의 `balance.mult[레벨]`.", "", "## 수렴 이력", "", "| 반복 | 평균 편차 | 표준편차 | ±4%p 내 |", "|---|---|---|---|"]
    for h in r["history"]: L.append(f"| {h['iter']} | {h['mean_dev']:+.3f} | {h['sd']:.3f} | {h['in_band']:.0%} |")
    L += ["", "## 특성별 결과", "", "| 구분 | 특성 | 레벨 | 한계 가치(승률 차) | 목표 | 배율 | 표본 |", "|---|---|---|---|---|---|---|"]
    for x in r["rows"]:
        L.append(f"| {'출신' if x['kind']=='origin' else '직업'} | {x['name']} | {x['level']} | {x['value']:+.3f} {band(x['value'] - x['target'] + 0.5, 0.04)} | {x['target']:+.2f} | ×{x['mult']:.2f} | {x['n']} |")
    open(os.path.join(OUT, "B4_특성_가치.md"), "w", encoding="utf-8").write("\n".join(L) + "\n")


def combos_md():
    p = os.path.join(REP, "item_combos.json")
    if not os.path.exists(p): return
    r = json.load(open(p, encoding="utf-8"))
    L = ["# 부록 B5. 아이템 다중 장착 상호작용", "", "같은 캐리어 역할의 조합 아이템 2개·3개를 한 캐리어에 장착했을 때 Δ와 단일 Δ 합의 차이(시너지 = Δ조합 - ΣΔ단일). 음수 = 열가산(상쇄), 양수 = 초가산.", ""]
    for k, v in r["summary"].items():
        L.append(f"- {k}: n={v['n']}, 평균 Δ조합 {v['mean_delta']:+.3f}, 평균 ΣΔ단일 {v['mean_sum_single']:+.3f}, 평균 시너지 {v['mean_synergy']:+.3f} (sd {v['sd_synergy']:.3f})")
    L += ["", "## 상쇄(열가산) 상위 15", "", "| 역할 | 아이템 | Δ조합 | ΣΔ단일 | 시너지 |", "|---|---|---|---|---|"]
    for x in r["rows"][:15]: L.append(f"| {x['role']} | {' + '.join(x['items'])} | {x['delta']:+.3f} | {x['sum_single']:+.3f} | {x['synergy']:+.3f} |")
    L += ["", "## 시너지(초가산) 상위 15", "", "| 역할 | 아이템 | Δ조합 | ΣΔ단일 | 시너지 |", "|---|---|---|---|---|"]
    for x in r["rows"][-15:][::-1]: L.append(f"| {x['role']} | {' + '.join(x['items'])} | {x['delta']:+.3f} | {x['sum_single']:+.3f} | {x['synergy']:+.3f} |")
    open(os.path.join(OUT, "B5_아이템_조합_상호작용.md"), "w", encoding="utf-8").write("\n".join(L) + "\n")


def context_md():
    p = os.path.join(REP, "context_items.json")
    if not os.path.exists(p): return
    r = json.load(open(p, encoding="utf-8"))
    sc = r["scenarios"]
    bw = r.get("baseline_wr", {})
    L = ["# 부록 B6. 상황 의존형 아이템의 유형별 전투 재평가", "", "시나리오: magic_heavy(마법 중심 적), boss_hp(계층 4 보스 체력 ×2.2), siege(적 성벽 + 화살비), waves(3웨이브), assassin(암살자 캐리어). 값 = Δ승률.",
         "기준선(아이템 없음) 승률: " + ", ".join(f"{k} {v:.2f}" for k, v in bw.items()), "",
         "| ID | 아이템 | 분류 | 배율 | 목표 Δ | " + " | ".join(sc) + " | 최적 상황 | 판정 |", "|---|---|---|---|---|" + "---|" * len(sc) + "---|---|"]
    for x in r["rows"]:
        L.append(f"| {x['id']} | {x['name']} | {x['category']} | ×{x['mult']:.2f} | {x['target']:+.2f} | " + " | ".join(f"{x['delta'][s]:+.2f}" if x['delta'].get(s) is not None else "-" for s in sc) + f" | {x['best_scenario']} | {x['verdict']} |")
    open(os.path.join(OUT, "B6_상황의존_아이템.md"), "w", encoding="utf-8").write("\n".join(L) + "\n")


def boss_md():
    p = os.path.join(REP, "boss_tuning.json")
    if not os.path.exists(p): return
    r = json.load(open(p, encoding="utf-8"))
    L = ["# 부록 B7. 스토리 보스 전투 튜닝", "", f"목표(기대 팀): {r['targets']}. 보스 체력 배수(hp_mult)를 보통 승률로 조정, battles.json에 기록.", "",
         "| ID | 전투 | 막 | 유형 | 레벨 | 보스 | 체력 배수 | 전력 배수(보통/어려움/악몽) | 보통 | 어려움 | 악몽 |", "|---|---|---|---|---|---|---|---|---|---|---|"]
    for x in r["rows"]:
        pmv = x.get("power_mult", {})
        L.append(f"| {x['id']} | {x['name']} | {x['act']} | {x['type']} | {x['level']} | {x['boss']} | ×{x['hp_mult']:.2f} | {pmv.get('normal', 1):.2f}/{pmv.get('hard', 1):.2f}/{pmv.get('nightmare', 1):.2f} | {x['wr']['normal']:.2f} | {x['wr']['hard']:.2f} | {x['wr']['nightmare']:.2f} |")
    open(os.path.join(OUT, "B7_보스_튜닝.md"), "w", encoding="utf-8").write("\n".join(L) + "\n")


if __name__ == "__main__":
    hero_md(); item_md(); battle_md(); trait_md(); combos_md(); context_md(); boss_md(); print("reports written")
