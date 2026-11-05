# -*- coding: utf-8 -*-
"""
잔여 밸런스 판단표 (C5): 특성 임계값 중 목표 ±4%p 밖인 항목과 상황 의존형 아이템 15종을 '측정 노이즈 / 구조적 / 상한 도달 / 의도된 상황 특화'로 분류하고
디자이너 결정(유지·효과 재설계·목표 재설정)을 기록한다. 입력: sim/reports/trait_balance.json, context_items.json. 출력: docs/appendix/B8_잔여_밸런스_판단표.md
"""
import json, os, math
ROOT = os.path.join(os.path.dirname(__file__), "..")
REP = os.path.join(os.path.dirname(__file__), "reports")
tb = json.load(open(os.path.join(REP, "trait_balance.json"), encoding="utf-8"))
ci = json.load(open(os.path.join(REP, "context_items.json"), encoding="utf-8"))
traits = json.load(open(os.path.join(ROOT, "data", "traits.json"), encoding="utf-8"))
items = {i["id"]: i for i in json.load(open(os.path.join(ROOT, "data", "items.json"), encoding="utf-8"))["items"]}
MULT_LO, MULT_HI = 0.2, 3.0

def effect_summary(t, L):
    """임계값 L의 효과 수치 요약(리스트형 수치의 해당 단계 값)."""
    out = []
    for e in t.get("effects", []):
        idx = t["thresholds"].index(L)
        parts = []
        for k, v in e.items():
            if isinstance(v, list) and len(v) == len(t["thresholds"]):
                parts.append(f"{k}={v[idx]}")
        if parts: out.append(e.get("type", e.get("kind", "")) + "(" + ", ".join(parts) + ")")
    return "; ".join(out) or "—"

rows = []
tmap = {t["key"]: t for t in traits["origins"] + traits["classes"]}
for r in tb["rows"]:
    dev = r["value"] - r["target"]
    if abs(dev) <= 0.04: continue
    n = r["n"]
    se = math.sqrt(0.5 / n)  # 승리 차(-1/0/1)의 분산 ≤ 0.5 가정
    t = tmap[r["key"]]
    li = t["thresholds"].index(r["level"])
    at_cap = r["mult"] <= MULT_LO + 1e-6 or r["mult"] >= MULT_HI - 1e-6
    first_level = li == 0
    last_level = li == len(t["thresholds"]) - 1
    if abs(dev) <= 2 * se:
        cls, decision = "측정 노이즈", "유지 (표본 확대 재측정만)"
    elif at_cap:
        cls = "배율 상한 도달"
        decision = ("효과 재설계: 배율로 못 낮추는 이진 효과(도발·부활·즉사형)이므로 지속·범위·발동 조건을 축소" if r["mult"] <= MULT_LO + 1e-6
                    else "효과 재설계: 배율 3배에도 미달 → 효과 종류 추가(예: 추가 능력치 1종)")
    elif first_level and r["value"] < r["target"] - 0.04:
        cls, decision = "구조적(2단계 저효용)", "목표 재설정 +2~3%p 또는 2단계에 즉시 체감 효과(공속/체력 소량) 추가"
    elif last_level and r["value"] < r["target"] - 0.04:
        cls, decision = "구조적(수직 포화)", "유지 — 8/6단계 수직 편성은 포화 승률 구간(0.9+)이라 한계 가치가 압축됨. 상위 보상은 연출·칭호로 보완"
    elif dev > 0:
        cls, decision = "과강(배율 여유 있음)", f"배율 {r['mult']:.2f} → {max(MULT_LO, r['mult'] * ((r['target']+0.08)/(r['value']+0.08))**0.6):.2f} 추가 1회 조정 후 재측정"
    else:
        cls, decision = "과약(배율 여유 있음)", f"배율 {r['mult']:.2f} → {min(MULT_HI, r['mult'] * ((r['target']+0.08)/(r['value']+0.08))**0.6):.2f} 추가 1회 조정 후 재측정"
    rows.append(dict(kind="출신" if r["kind"] == "origin" else "직업", name=r["name"], level=r["level"], value=r["value"], target=r["target"], dev=dev, se=se, n=n,
                     mult=r["mult"], effect=effect_summary(t, r["level"]), cls=cls, decision=decision))

CTX_KO = {"magic_heavy": "마법 중심 적", "boss_hp": "고체력 보스", "siege": "공성", "waves": "3웨이브", "assassin": "암살자 캐리어"}
TOOLTIP = {"magic_heavy": "마법 피해가 많은 적에게 유리", "boss_hp": "체력이 높은 단일 대상(보스)에게 유리", "siege": "공성·구조물 전투에 유리", "waves": "연속 웨이브 전투에 유리", "assassin": "암살자·돌진형 캐리어에 장착 시 유리"}
irows = []
for r in ci["rows"]:
    best = r["best_scenario"]; d = r["delta"]
    worst = min(d, key=d.get)
    spread = d[best] - d[worst]
    ratio_ok = sum(1 for v in d.values() if v >= r["target"] * 0.8)
    if r["verdict"] != "상황 특화 OK": cls = r["verdict"]
    elif ratio_ok >= 4: cls = "범용에 가까움(배율 유지, 플래그 해제 검토)"
    elif d[worst] < 0: cls = "양날(불리 상황 존재) — 툴팁 필수"
    else: cls = "상황 특화(의도)"
    irows.append(dict(id=r["id"], name=r["name"], cat=r["category"], mult=r["mult"], target=r["target"], best=best, best_v=d[best], worst=worst, worst_v=d[worst], spread=spread, cls=cls,
                      tooltip=TOOLTIP[best], shop_tag=f"상황 아이템 · {CTX_KO[best]}"))

L = ["# 부록 B8. 잔여 밸런스 판단표 (C5)", "",
     "(자동 생성: `python3 sim/judgment_table.py`. 입력: 부록 B4 특성 가치 최종 측정, 부록 B6 상황 의존형 아이템 재평가.)", "",
     "## 1. 판단 기준",
     "- **측정 노이즈**: |편차| ≤ 2×표준오차(SE = √(0.5/n)). 표본을 늘려도 ±4%p 밴드 안으로 들어올 확률이 높다 → 배율 유지.",
     "- **배율 상한 도달**: 배율이 0.2 또는 3.0에 닿아 더 조정할 수 없다 → 효과 설계 자체를 바꾼다(이진 효과는 지속·범위·조건을, 미달 효과는 종류를 추가).",
     "- **구조적(2단계 저효용)**: 첫 임계값 효과가 2명만으로는 체감이 작다 → 목표를 낮추거나 즉시 체감 효과를 덧붙인다.",
     "- **구조적(수직 포화)**: 6/8단계 수직 편성은 이미 승률 0.9+ 구간이어서 한계 가치가 압축된다 → 수치 대신 연출·칭호 보상.",
     "- **과강/과약(여유 있음)**: 배율 여유가 있고 노이즈 범위 밖 → 1회 추가 조정 후 재측정.", "",
     f"## 2. 특성 임계값 — 목표 ±4%p 밖 {len(rows)}건 (측정 {len(tb['rows'])}개 중)", "",
     "| 구분 | 특성 | 단계 | 측정 | 목표 | 편차 | SE | 배율 | 단계 효과 | 분류 | 결정 |", "|---|---|---|---|---|---|---|---|---|---|---|"]
for r in sorted(rows, key=lambda r: (r["cls"], -abs(r["dev"]))):
    L.append(f"| {r['kind']} | {r['name']} | {r['level']} | {r['value']:+.3f} | {r['target']:+.2f} | {r['dev']:+.3f} | ±{r['se']:.3f} | ×{r['mult']:.2f} | {r['effect']} | {r['cls']} | {r['decision']} |")
from collections import Counter
c = Counter(r["cls"] for r in rows)
L += ["", "분류 집계: " + ", ".join(f"{k} {v}" for k, v in c.most_common()), ""]
L += ["## 3. 상황 의존형 아이템 15종 — 운영 결정", "",
      "모두 '상황 특화 OK'(부록 B6). 배율은 유지하고 **UI에서 상황을 드러내는 것**으로 마무리한다: 아이템 툴팁 2줄째에 상황 문구, 상점·인벤토리에 '상황 아이템' 태그, 전투 정보 모달(S05)에서 해당 상황 전투일 때 추천 배지.", "",
      "| ID | 아이템 | 분류 | 배율 | 목표 Δ | 최적 상황(Δ) | 최악 상황(Δ) | 폭 | 분류 | 툴팁 문구 | 상점 태그 |", "|---|---|---|---|---|---|---|---|---|---|---|"]
for r in irows:
    L.append(f"| {r['id']} | {r['name']} | {r['cat']} | ×{r['mult']:.2f} | +{r['target']:.2f} | {CTX_KO[r['best']]}({r['best_v']:+.2f}) | {CTX_KO[r['worst']]}({r['worst_v']:+.2f}) | {r['spread']:.2f} | {r['cls']} | {r['tooltip']} | {r['shop_tag']} |")
L += ["", "- 문자열 키: `item.{id}.situational`(툴팁), `ui.shop.tag.situational`(태그) — 17 문서 테이블에 추가 대상.",
      "- 라이브 검증: 22 문서 `equip_change`·`battle_end`로 아이템별 장착 전투 유형 분포와 승률을 보고, 최적 상황 외 장착률이 70%를 넘는 아이템은 툴팁 노출 위치를 재검토한다."]
out = os.path.join(ROOT, "docs", "appendix", "B8_잔여_밸런스_판단표.md")
open(out, "w", encoding="utf-8").write("\n".join(L) + "\n")
print("B8 written:", len(rows), "trait rows,", len(irows), "items;", dict(c))
