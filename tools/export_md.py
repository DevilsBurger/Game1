# -*- coding: utf-8 -*-
"""data/*.json → docs/appendix/*.md 부록 표 생성."""
import json, os
from collections import Counter, defaultdict

ROOT = os.path.join(os.path.dirname(__file__), "..")
D = lambda n: json.load(open(os.path.join(ROOT, "data", n), encoding="utf-8"))
OUT = os.path.join(ROOT, "docs", "appendix")
os.makedirs(OUT, exist_ok=True)

heroes = D("heroes.json"); traits = D("traits.json"); items = D("items.json"); nations = D("nations.json"); battles = D("battles.json"); quests = D("quests.json")
ON = {o["key"]: o["name_ko"] for o in traits["origins"]}; CN = {c["key"]: c["name_ko"] for c in traits["classes"]}
HN = {h["id"]: h["name_ko"] for h in heroes["heroes"]}
NN = {n["key"]: n["name_ko"] for n in nations["nations"]}


def w(name, lines):
    with open(os.path.join(OUT, name), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


# ── A1 영웅 목록
L = ["# 부록 A1. 영웅 목록 (196)", "", "자동 생성: `python tools/export_md.py`. 수치는 1성 기준(밸런스 조정 반영).", ""]
L += ["## 출신 × 직업 격자 (계층)", "", "| 출신 \\ 직업 | " + " | ".join(CN[c["key"]] for c in traits["classes"]) + " |", "|---|" + "---|" * len(traits["classes"])]
grid = {(h["origin"], h["class"]): h for h in heroes["heroes"]}
for o in traits["origins"]:
    L.append(f"| **{ON[o['key']]}** | " + " | ".join(f"{grid[(o['key'], c['key'])]['name_ko']} T{grid[(o['key'], c['key'])]['tier']}" for c in traits["classes"]) + " |")
L += ["", "## 계층별 분포", "", "| 계층 | 등급 | 인원 |", "|---|---|---|"]
RAR = {1: '일반', 2: '고급', 3: '희귀', 4: '영웅', 5: '전설'}
for t in range(1, 6):
    L.append(f"| {t} | {RAR[t]} | {sum(1 for h in heroes['heroes'] if h['tier']==t)} |")
L += ["", "## 전체 목록 (밸런스 배율 반영 최종 수치)", "", "| ID | 이름 | 칭호 | 출신 | 직업 | 계층 | HP ★1/★2/★3 | AD ★1/★2/★3 | AS | 방어 | 마저 | 사거리 | 마나 | 스킬 | 스킬 원형 | 스킬 설명 |", "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
for h in heroes["heroes"]:
    s = h["stats"]; b = h.get("balance", {}); sm = b.get("star_mult", [1, 1, 1])
    hp = "/".join(str(round(s["hp"] * b.get("hp_mult", 1) * sm[i] * h["star_scaling"]["hp"][i])) for i in range(3))
    ad = "/".join(str(round(s["ad"] * b.get("ad_mult", 1) * sm[i] * h["star_scaling"]["ad"][i])) for i in range(3))
    L.append(f"| {h['id']} | {h['name_ko']} | {h['title']} | {ON[h['origin']]} | {CN[h['class']]} | {h['tier']} | {hp} | {ad} | {s['attack_speed']} | {s['armor']} | {s['mr']} | {s['range']} | {s['mana_start']}/{s['mana_max']} | {h['skill']['name']} | {h['skill']['archetype']} | {h['skill']['desc']} |")
L += ["", "## 서사 한 줄", ""]
for h in heroes["heroes"]:
    L.append(f"- **{h['name_ko']}** ({ON[h['origin']]}·{CN[h['class']]}·T{h['tier']}): {h['lore']}")
w("A1_영웅_목록.md", L)

# ── A2 아이템 목록
L = ["# 부록 A2. 아이템 목록 (%d)" % items["count"], "", "자동 생성. 분류별 개수: " + ", ".join(f"{k} {v}" for k, v in items["by_category"].items()), ""]
cat_ko = {"component": "기본 재료", "completed": "조합 아이템", "emblem": "상징/특수", "radiant": "빛나는 아이템", "artifact": "유물", "support": "지원 아이템", "national": "국가 특산품", "consumable": "소모품", "material": "승급 재료"}
for cat, ko in cat_ko.items():
    L += [f"## {ko}", "", "| ID | 이름 | 영문 | 능력치 | 효과 | 조합/비고 | 가격(골드) |", "|---|---|---|---|---|---|---|"]
    for it in items["items"]:
        if it["category"] != cat: continue
        stats = ", ".join(f"{k} +{v}" for k, v in it["stats"].items()) or "-"
        rec = "+".join(it["recipe"]) if it.get("recipe") else (it.get("base_item") or ("보석 %d" % it["price_gem"] if it.get("price_gem") else "-"))
        price = it.get("price_gold") if it.get("price_gold") is not None else "보석 전용"
        bm = it.get("balance", {}).get("mult")
        stats = stats + (f" (×{bm:.2f})" if bm and abs(bm - 1) > 0.005 else "")
        L.append(f"| {it['id']} | {it['name_ko']} | {it['name_en']} | {stats} | {it['desc']} | {rec} | {price} |")
    L.append("")
w("A2_아이템_목록.md", L)

# ── A3 국가/전투
L = ["# 부록 A3. 국가 및 전투 목록 (전투 %d)" % battles["count"], "", "자동 생성.", "", "## 국가 24", "",
     "| 키 | 국가 | 권역 | 분류 | 문명 | 위험도 | 막 | 수도 | 통치자 | 토착 출신 | 전투 수 | 지역 |", "|---|---|---|---|---|---|---|---|---|---|---|---|"]
for n in nations["nations"]:
    L.append(f"| {n['key']} | {n['name_ko']} | {n['region_group']} | {n['category']} | {n['civilization']} | {n['danger']} | {n['act']} | {n['capital']} | {n['ruler']} | {n['native_origin_ko']} | {n['battle_count']} | {', '.join(n['regions'])} |")
L += ["", "## 전투 종류별 수", "", "| 종류 | 수 |", "|---|---|"] + [f"| {k} | {v} |" for k, v in battles["by_type"].items()]
L += ["", "## 스토리 전투 (76)", "", "| ID | 막 | 국가 | 지역 | 이름 | 유형 | 참전 | 레벨 | 보통 골드 | 첫 클리어 영웅 | 시놉시스 |", "|---|---|---|---|---|---|---|---|---|---|---|"]
for b in battles["battles"]:
    if b["kind"] != "story": continue
    hero = b["difficulties"].get("first_clear_bonus", {}).get("hero_guaranteed", {})
    L.append(f"| {b['id']} | {b['act']} | {b['nation_ko']} | {b['region']} | {b['name_ko']} | {b['type_ko']} | {b['participation']['name']} | {b['level']} | {b['difficulties']['normal']['rewards']['gold']} | {hero.get('name_ko','-')} | {b['flavor']} |")
L += ["", "## 지역 전투 (1080) — 국가별", ""]
by_nat = defaultdict(list)
for b in battles["battles"]:
    if b["kind"] == "regional": by_nat[b["nation"]].append(b)
for n in nations["nations"]:
    L += [f"### {n['name_ko']} ({len(by_nat[n['key']])})", "", "| ID | 지역 | 이름 | 유형 | 참전 | 레벨 | 보통/어려움/악몽 골드 | 스태미너(보통) | 적 편성 |", "|---|---|---|---|---|---|---|---|---|"]
    for b in by_nat[n["key"]]:
        d = b["difficulties"]; comp = Counter(u["name_ko"] for u in b["enemy"]["units"])
        cs = ", ".join(f"{k}×{v}" for k, v in comp.items()) + (f" / 보스: {b['enemy']['boss']['name_ko']}" if b["enemy"]["boss"] else "")
        L.append(f"| {b['id']} | {b['region']} | {b['name_ko']} | {b['type_ko']} | {b['participation']['name']} | {b['level']} | {d['normal']['rewards']['gold']}/{d['hard']['rewards']['gold']}/{d['nightmare']['rewards']['gold']} | {d['normal']['stamina_per_hero']} | {cs} |")
    L.append("")
L += ["## 영웅 조우 전투 (196)", "", "| ID | 영웅 | 계층 | 국가 | 지역 | 레벨 | 드랍 확률 보통/어려움/악몽 |", "|---|---|---|---|---|---|---|"]
for b in battles["battles"]:
    if b["kind"] != "encounter": continue
    d = b["difficulties"]; hd = lambda k: d[k]["rewards"]["hero_drop"]["chance_pct"]
    L.append(f"| {b['id']} | {HN[b['hero_id']]} | {b['enemy']['hero_enemy']['tier']} | {b['nation_ko']} | {b['region']} | {b['level']} | {hd('normal')}% / {hd('hard')}% / {hd('nightmare')}% |")
L += ["", "## 퀘스트 전투 (252)", "", "| ID | 퀘스트 | 이름 | 국가 | 유형 | 레벨 | 클리어 조건 |", "|---|---|---|---|---|---|---|"]
for b in battles["battles"]:
    if b["kind"] != "quest": continue
    L.append(f"| {b['id']} | {b['quest_id']} | {b['name_ko']} | {b['nation_ko']} | {b['type_ko']} | {b['level']} | {b['clear_condition']['desc']} |")
w("A3_국가_전투_목록.md", L)

# ── A4 퀘스트
L = ["# 부록 A4. 퀘스트 목록 (%d)" % quests["count"], "", "자동 생성.", ""]
for kind, ko in [("story", "스토리 퀘스트"), ("hero_chain", "영웅 서사 체인 (계층 4·5 확정 영입)"), ("origin_pact", "출신 맹약"), ("class_trial", "직업 시련")]:
    L += [f"## {ko}", "", "| ID | 이름 | 단계 수 | 조건 요약 | 보상 |", "|---|---|---|---|---|"]
    for q in quests["quests"]:
        if q["kind"] != kind: continue
        conds = "; ".join(f"{s['battle_id']}({s['condition']['desc']})" if s.get("condition") else s["battle_id"] for s in q["steps"][:6]) + (" …" if len(q["steps"]) > 6 else "")
        r = q["reward"]; rew = []
        if r.get("hero_guaranteed"): rew.append("영웅 확정: " + HN.get(r["hero_guaranteed"], r["hero_guaranteed"]))
        if r.get("story_heroes"): rew.append("스토리 영웅: " + ", ".join(x["name_ko"] for x in r["story_heroes"]))
        if r.get("gold"): rew.append(f"골드 {r['gold']}")
        if r.get("gems"): rew.append(f"보석 {r['gems']}")
        for it in r.get("items", []): rew.append(it["pool"])
        L.append(f"| {q['id']} | {q['name_ko']} | {len(q['steps'])} | {conds} | {', '.join(rew)} |")
    L.append("")
w("A4_퀘스트_목록.md", L)
print("appendix written")
