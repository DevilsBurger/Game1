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
    byc = defaultdict(list)
    for x in r["items"]: byc[x["category"]].append(x)
    L = [f"기준선(아이템 없는 기준 팀 간 교차전 평균, 좌우 교대) 승률 {r['base']:.3f}. 목표 Δ는 분류 기본값 × 캐리어 역할 보정(탱커 1.5, 브루저 1.25).", "",
         "| 분류 | 개수 | 목표 Δ(평균) | 평균 Δ | 목표 대비 편차 | 목표 ±3%p 내 | 배율 범위 |", "|---|---|---|---|---|---|---|"]
    for c, xs in byc.items():
        v = [x["delta"] for x in xs]; m = [x["mult"] for x in xs]; tg = [x.get("target", 0) for x in xs]
        L.append(f"| {c} | {len(xs)} | {statistics.mean(tg):+.3f} | {statistics.mean(v):+.3f} | {statistics.pstdev(d - t for d, t in zip(v, tg)):.3f} | {sum(1 for d, t in zip(v, tg) if abs(d-t)<=0.03)/len(v):.0%} | {min(m):.2f}~{max(m):.2f} |")
    L += ["", "가장 크게 조정된 아이템(배율 기준):"]
    xs = sorted(r["items"], key=lambda x: abs(x["mult"] - 1), reverse=True)[:12]
    L.append(", ".join(f"{x['name']} ×{x['mult']:.2f}" for x in xs))
    flagged = [x for x in r["items"] if x.get("flag")]
    L += ["", f"상황 의존형(배율 한계 0.4~2.0에서도 목표 밖, 디자이너 검토 대상) {len(flagged)}개: " + ", ".join(f"{x['name']}(Δ{x['delta']:+.2f})" for x in flagged)]
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
        L += ["", "몬스터 전력 보정 곡선(economy.json `enemy_power_curve`, 난이도 × 레벨 10 구간):", "", "| 난이도 | " + " | ".join(f"L{lo}" for lo in range(1, 100, 10)) + " |", "|---|" + "---|" * 10]
        for d in ("normal", "hard", "nightmare"):
            L.append(f"| {d} | " + " | ".join(f"×{r['calibration'][f'{d} L{lo}-{lo+9}']:.2f}" for lo in range(1, 100, 10)) + " |")
    return "\n".join(L)


def followup_block():
    L = []
    # 9.1 fold
    p = os.path.join(REP, "hero_balance.json")
    if os.path.exists(p):
        r = json.load(open(p, encoding="utf-8")); hs = r["heroes"]
        sm = [x["star_mult"] for x in hs]
        h0 = r["history"][0] if r["history"] and "star1" in r["history"][0] else None
        if h0 is None:  # 아이템 단계가 hero_balance.json 이력을 비우므로 영웅 재수렴 로그에서 복원
            import re as _re
            lp = os.path.join(REP, "hero_fold.log")
            if os.path.exists(lp):
                m = _re.search(r"\[hero iter 0\] ★1: sd=([0-9.]+) band=(\d+)%", open(lp, encoding="utf-8").read())
                if m: h0 = {"star1": {"sd": float(m.group(1)), "in_band": int(m.group(2)) / 100}}
        L += ["#### 9.1 원형 전력 계수 반영 후 영웅 재수렴",
              (f"- 원형 계수 반영 직후(조정 전) ★1 참전 승률 표준편차 {h0['star1']['sd']:.3f}, 밴드 내 {h0['star1']['in_band']:.0%} (반영 전 0.107 / 37%). 설계 기본값만으로 대부분의 영웅이 밴드 근처에 놓인다." if h0 else "- (반영 직후 분포: sim/reports/hero_fold.log 참조)"),
              f"- 잔여 영웅별 배율 범위: ★1 {min(x[0] for x in sm):.2f}~{max(x[0] for x in sm):.2f}, ★3 {min(x[2] for x in sm):.2f}~{max(x[2] for x in sm):.2f} (반영 전 0.68~1.64 / 0.54~1.73).",
              "- 최종 수렴: " + ", ".join(f"{lbl} 표준편차 {statistics.pstdev([x[k] for x in hs]):.3f}·밴드 내 {sum(1 for x in hs if abs(x[k]-0.5)<=0.05)/len(hs):.0%}" for k, lbl in (("wr_team", "★1"), ("wr_team_star2", "★2"), ("wr_team_star3", "★3"))), ""]
    # 9.2 traits
    p = os.path.join(REP, "trait_balance.json")
    if os.path.exists(p):
        r = json.load(open(p, encoding="utf-8")); rows = r["rows"]; h = r["history"]
        dev = [x["value"] - x["target"] for x in rows]
        L += ["#### 9.2 특성 임계값 가치",
              f"- 측정 {len(rows)}개(출신 14×4, 직업 14×3). 조정 전 목표 대비 평균 편차 {h[0]['mean_dev']:+.3f}(sd {h[0]['sd']:.3f}, ±4%p 내 {h[0]['in_band']:.0%}) → 조정 후 {h[-1]['mean_dev']:+.3f}(sd {h[-1]['sd']:.3f}, ±4%p 내 {h[-1]['in_band']:.0%}).",
              "- 조정 후에도 목표 밖(±4%p)인 특성: " + (", ".join(f"{x['name']} {x['level']}단계({x['value']:+.2f}/목표 {x['target']:+.2f})" for x in rows if abs(x['value'] - x['target']) > 0.04) or "없음"),
              "- 배율이 가장 큰 특성: " + ", ".join(f"{x['name']} L{x['level']} ×{x['mult']:.2f}" for x in sorted(rows, key=lambda x: abs(x['mult'] - 1), reverse=True)[:8]), ""]
    # 9.3 combos
    p = os.path.join(REP, "item_combos.json")
    if os.path.exists(p):
        r = json.load(open(p, encoding="utf-8")); sm_ = r["summary"]
        L += ["#### 9.3 아이템 다중 장착 상호작용",
              f"- 2개 장착 {sm_['pairs']['n']}조합: 평균 Δ {sm_['pairs']['mean_delta']:+.3f} vs 단일 합 {sm_['pairs']['mean_sum_single']:+.3f} → 평균 시너지 {sm_['pairs']['mean_synergy']:+.3f} (sd {sm_['pairs']['sd_synergy']:.3f}).",
              f"- 3개 장착 {sm_['triples']['n']}조합: 평균 Δ {sm_['triples']['mean_delta']:+.3f} vs 단일 합 {sm_['triples']['mean_sum_single']:+.3f} → 평균 시너지 {sm_['triples']['mean_synergy']:+.3f} (sd {sm_['triples']['sd_synergy']:.3f}).",
              "- 해석: 승률은 0~1로 포화되므로 다중 장착은 자연히 열가산(상쇄)이다. 평균보다 크게 벗어나는 조합이 설계 포인트(부록 B5의 상·하위 목록).", ""]
    # 9.4 context
    p = os.path.join(REP, "context_items.json")
    if os.path.exists(p):
        r = json.load(open(p, encoding="utf-8")); rows = r["rows"]
        from collections import Counter
        c = Counter(x["verdict"] for x in rows)
        L += ["#### 9.4 상황 의존형 아이템 재평가",
              f"- 플래그 {len(rows)}종을 5개 시나리오(마법 중심 적·고체력 보스·공성·3웨이브·암살자 캐리어)에서 재평가: " + ", ".join(f"{k} {v}" for k, v in c.items()) + ".",
              "- 상황 특화 OK = 특정 상황에서 목표 Δ를 만족(의도된 상황 아이템, 현재 배율 유지). 전반 과강 = 모든 상황에서 목표 초과(효과 설계 변경 필요). 재설계 필요 = 어느 상황에서도 목표 미달.",
              "- 재설계 필요: " + (", ".join(f"{x['name']}(최적 {x['best_scenario']} {x['delta'][x['best_scenario']]:+.2f})" for x in rows if x["verdict"] == "재설계 필요") or "없음"),
              "- 전반 과강: " + (", ".join(x["name"] for x in rows if x["verdict"] == "전반 과강") or "없음"), ""]
    # 9.5 bosses
    p = os.path.join(REP, "boss_tuning.json")
    if os.path.exists(p):
        r = json.load(open(p, encoding="utf-8")); rows = r["rows"]
        L += ["#### 9.5 스토리 보스 튜닝",
              f"- 결전·레이드·토벌형 스토리 전투 {len(rows)}개의 보스 체력 배수를 목표(보통 65%/어려움 45%/악몽 25%)로 조정. 최종 평균 승률: 보통 {statistics.mean(x['wr']['normal'] for x in rows):.0%}, 어려움 {statistics.mean(x['wr']['hard'] for x in rows):.0%}, 악몽 {statistics.mean(x['wr']['nightmare'] for x in rows):.0%}.",
              "- " + ", ".join(f"{x['name']}({x['boss']}) ×{x['hp_mult']:.1f}" for x in rows if x["type"] == "decisive"), ""]
    # 9.6 calibration + vectors
    p = os.path.join(REP, "battle_validation.json")
    if os.path.exists(p):
        r = json.load(open(p, encoding="utf-8"))
        L += ["#### 9.6 고레벨 난이도 보정 · 테스트 벡터",
              "- 기대 팀 정의를 레벨 75+에서 ★3·★2 혼합으로 낮추고 유형별 규칙(웨이브·성벽·수호 대상·호위·암살·탈출·구출)을 적용해 8라운드 재보정: " + ", ".join(f"{d} {v['mean']:.1%}" for d, v in r["summary"].items()) + ".",
              "- 레벨 구간별: " + ", ".join(f"{k} {v:.0%}" for k, v in r["by_level_band"].items()) + "."]
        vp = os.path.join(HERE, "..", "tests", "vectors", "battle_vectors.json")
        if os.path.exists(vp):
            v = json.load(open(vp, encoding="utf-8"))
            L.append(f"- C# 포팅 검증용 테스트 벡터 {v['count']}개 생성(`tests/vectors/battle_vectors.json`): 무작위 팀전·결투·웨이브·성벽·수호·탈출·암살. `tests/test_vectors.py`가 승자·시간·생존자·총 피해를 재검증한다.")
    return "\n".join(L)


def main():
    s = open(DOC, encoding="utf-8").read()
    import re
    s = re.sub(r"### 6\.1 영웅\n.*?\n### 6\.2", "### 6.1 영웅\n" + hero_block() + "\n\n### 6.2", s, flags=re.S)
    s = re.sub(r"### 6\.2 아이템\n.*?\n### 6\.3", "### 6.2 아이템\n" + item_block() + "\n\n### 6.3", s, flags=re.S)
    s = re.sub(r"### 6\.3 전투 난이도\n.*?\n## 7\.", "### 6.3 전투 난이도\n" + battle_block() + "\n\n## 7.", s, flags=re.S)
    if "## 9. 후속 작업 결과" in s:
        s = re.sub(r"## 9\. 후속 작업 결과\n.*?(?=\n## |\Z)", "## 9. 후속 작업 결과\n(자동 생성: `python sim/fill_doc.py`. 전체 표는 부록 B4~B7.)\n\n" + followup_block() + "\n", s, flags=re.S)
    open(DOC, "w", encoding="utf-8").write(s)
    print("doc filled")


if __name__ == "__main__":
    main()
