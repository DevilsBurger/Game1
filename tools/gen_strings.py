# -*- coding: utf-8 -*-
"""
문자열 테이블 생성: data/strings_ko.json, data/strings_en.json, data/strings_unity.csv (Unity Localization CSV: Key,Korean(ko),English(en))
키 체계: ui.* / origin.{key}.* / class.{key}.* / hero.{id}.{name,title,lore,skill_name,skill_desc} / item.{id}.{name,desc} / nation.{key}.* / region.{nation}.{i}
         battle_type.{key}.* / battle.{id}.{name,flavor} / quest.{id}.{name,desc} / story.{battle_id}.{pre|post}.{i} / cutscene.{id}.{title|shot.{i}.visual|line.{j}} / recruit.{hero} / lobby.{hero}.{i}
EN 미번역은 빈 문자열로 두고 보고서에 집계한다(스토리 대사 EN은 번역 대기).
"""
import json, os, sys, csv, re
sys.path.insert(0, os.path.dirname(__file__))
from strings_en_1 import UI, TRAIT_EN, BATTLE_TYPE_EN, NATION_EN, FACTION_EN, MONSTER_EN, BATTLE_NAME_EN, BATTLE_FLAVOR_EN, STRUCTURE_EN
from strings_en_2 import HERO_EN, SPECIAL_EN, ARCHETYPE_DESC_EN, HERO_SKILL_DESC_EN_OVERRIDE, HOOK_EN, STAT_EN
from strings_en_3 import CUTSCENE_EN
from world_data import NATIONS, BATTLE_TYPES

ROOT = os.path.join(os.path.dirname(__file__), "..")
D = lambda n: json.load(open(os.path.join(ROOT, "data", n), encoding="utf-8"))
heroes = D("heroes.json"); items = D("items.json"); traits = D("traits.json"); nations = D("nations.json"); battles = D("battles.json"); quests = D("quests.json")
story = D("story_script.json") if os.path.exists(os.path.join(ROOT, "data", "story_script.json")) else None
ko, en = {}, {}
NKO = {n["key"]: n for n in nations["nations"]}
BT_KO = {b[0]: b for b in BATTLE_TYPES}
REGION_EN = {nk: dict(zip(NKO[nk]["regions"], NATION_EN[nk][3])) for nk in NKO}
ON_EN = {o["key"]: o["name_en"] for o in traits["origins"]}; CN_EN = {c["key"]: c["name_en"] for c in traits["classes"]}
ON_KO = {o["key"]: o["name_ko"] for o in traits["origins"]}; CN_KO = {c["key"]: c["name_ko"] for c in traits["classes"]}
MON_KO = {m["key"]: m["name_ko"] for m in battles["monsters"]}
MON_EN_BY_KO = {MON_KO[k]: v for k, v in MONSTER_EN.items() if k in MON_KO}


def put(key, k, e=""):
    ko[key] = k; en[key] = e


def item_desc_en(it):
    parts = []
    stats = it.get("stats", {})
    if stats: parts.append(", ".join(f"+{v}{'%' if k.endswith('_pct') or k in ('crit', 'omnivamp', 'durability') else ''} {STAT_EN[k]}" for k, v in stats.items()))
    for h in it.get("hooks", []):
        p = dict(h["params"]); p["ad_ratio_pct"] = round(p.get("ad_ratio", 0) * 100)
        if h["type"] == "grant_trait": p["trait"] = ON_EN.get(p["trait"], CN_EN.get(p["trait"], p["trait"]))
        tpl = HOOK_EN.get(h["type"], "")
        try: parts.append(tpl.format(**p))
        except (KeyError, IndexError): parts.append(tpl)
    if it["category"] == "radiant": parts.insert(0, "Radiant: stats ×1.6, effects ×1.5.")
    if it["category"] == "consumable":
        eff = it.get("effect", {}); parts.append({"stamina": "Restores stamina.", "drop": "Boosts drop chance for one battle.", "affinity": "Raises a hero's affinity.", "key": "Admission to a treasure battle."}.get(it.get("kind"), ""))
    return " ".join(p for p in parts if p)


def main():
    for k, (a, b) in UI.items(): put(f"ui.{k}", a, b)
    for o in traits["origins"]:
        put(f"origin.{o['key']}.name", o["name_ko"], o["name_en"]); put(f"origin.{o['key']}.desc", o["desc"], TRAIT_EN[o["key"]][0]); put(f"origin.{o['key']}.synergy", o["synergy_desc"], TRAIT_EN[o["key"]][1])
    for c in traits["classes"]:
        put(f"class.{c['key']}.name", c["name_ko"], c["name_en"]); put(f"class.{c['key']}.desc", c["desc"], TRAIT_EN[c["key"]][0]); put(f"class.{c['key']}.synergy", c["synergy_desc"], TRAIT_EN[c["key"]][1])
    allh = [heroes["player_unit"]] + heroes["heroes"]
    for h in allh:
        hid = h["id"]; e = HERO_EN.get(h["name_ko"]) or SPECIAL_EN.get(h["name_ko"], ("", "", ""))
        put(f"hero.{hid}.name", h["name_ko"], h.get("name_en", "")); put(f"hero.{hid}.title", h.get("title", ""), e[0]); put(f"hero.{hid}.lore", h.get("lore", ""), e[2])
        put(f"hero.{hid}.skill_name", h["skill"]["name"], e[1]); put(f"hero.{hid}.skill_desc", h["skill"].get("desc", ""), HERO_SKILL_DESC_EN_OVERRIDE.get(h["name_ko"], ARCHETYPE_DESC_EN.get(h["skill"]["archetype"], "")))
    put("hero.NPC_ELIA.name", "엘리아", "Elia"); put("hero.NPC_ELIA.title", "하론의 치유사", SPECIAL_EN["엘리아"][0]); put("hero.NPC_ELIA.lore", "레온의 연인. 국경 마을 하론의 치유사이자 자신도 모르는 이셀라의 마지막 후손.", SPECIAL_EN["엘리아"][2])
    for it in items["items"]:
        put(f"item.{it['id']}.name", it["name_ko"], it["name_en"]); put(f"item.{it['id']}.desc", it["desc"], item_desc_en(it))
    # 상황 의존형 아이템 툴팁(부록 B6·B8): sim/reports/context_items.json의 최적 상황 → 2줄째 문구 + 상점 태그
    SITU = {"magic_heavy": ("마법 피해가 많은 적에게 유리", "Strong against magic-heavy enemies"), "boss_hp": ("체력이 높은 단일 대상(보스)에게 유리", "Strong against high-health bosses"),
            "siege": ("공성·구조물 전투에 유리", "Strong in siege battles"), "waves": ("연속 웨이브 전투에 유리", "Strong across wave battles"), "assassin": ("암살자·돌진형 캐리어에 장착 시 유리", "Best on assassin or dive carries")}
    ctx_path = os.path.join(ROOT, "sim", "reports", "context_items.json")
    if os.path.exists(ctx_path):
        for r in json.load(open(ctx_path, encoding="utf-8"))["rows"]:
            ko_, en_ = SITU[r["best_scenario"]]; put(f"item.{r['id']}.situational", ko_, en_)
    put("ui.shop.tag.situational", "상황 아이템", "Situational")
    for n in nations["nations"]:
        nk = n["key"]; e = NATION_EN[nk]
        put(f"nation.{nk}.name", n["name_ko"], n["name_en"]); put(f"nation.{nk}.desc", n["desc"], e[0]); put(f"nation.{nk}.capital", n["capital"], e[1]); put(f"nation.{nk}.ruler", n["ruler"], e[2])
        put(f"nation.{nk}.category", n["category"], {"자유도시": "Free City", "대국": "Great Power", "소국": "Minor State", "중견국": "Middle Power", "숨겨진 나라": "Hidden Nation", "고립국": "Isolated Nation", "적 본거지": "Enemy Stronghold"}.get(n["category"], ""))
        for i, r in enumerate(n["regions"]): put(f"region.{nk}.{i}", r, e[3][i])
        for f in n["enemy_factions"]: put(f"faction.{f}", f, FACTION_EN.get(f, ""))
    for m in battles["monsters"]: put(f"monster.{m['key']}.name", m["name_ko"], MONSTER_EN.get(m["key"], ""))
    for b in BATTLE_TYPES:
        put(f"battle_type.{b[0]}.name", b[1], BATTLE_TYPE_EN[b[0]][0]); put(f"battle_type.{b[0]}.desc", b[2], BATTLE_TYPE_EN[b[0]][1]); put(f"battle_type.{b[0]}.rule", b[5], "")
    for b in battles["battles"]:
        nm_en = ""; fl_en = ""
        if b["kind"] == "regional":
            nk = b["nation"]; region = REGION_EN[nk].get(b["region"], b["region"]); faction = FACTION_EN.get(b["enemy"]["factions"][0], b["enemy"]["factions"][0]) if b["enemy"]["factions"] else ""
            boss = MON_EN_BY_KO.get(b["enemy"]["boss"]["name_ko"], "") if b["enemy"]["boss"] else (MON_EN_BY_KO.get(b["enemy"]["units"][0]["name_ko"], "") if b["enemy"]["units"] else "")
            structure = STRUCTURE_EN.get(b["enemy"]["structures"][0]["name_ko"], "structure") if b["enemy"]["structures"] else "supply depot"
            m = re.search(r"(\d+)회전", b["name_ko"]); n_ = m.group(1) if m else ""
            nm_en = BATTLE_NAME_EN[b["type"]].format(region=region, faction=faction, boss=boss, structure=structure, n=n_)
            fl_en = BATTLE_FLAVOR_EN[b["type"]].format(nation=NKO[nk]["name_en"], region=region, faction=faction, boss=boss, structure=structure)
        elif b["kind"] == "encounter":
            hn = next((h for h in heroes["heroes"] if h["id"] == b["hero_id"]), None); e = HERO_EN.get(hn["name_ko"], ("", "", "")) if hn else ("", "", "")
            nm_en = f"Hero Encounter: {e[0]} {hn['name_en']}" if hn else ""; nk = b["nation"]
            fl_en = f"{hn['name_en']} blocks Leon's path at {REGION_EN[nk].get(b['region'], b['region'])} in {NKO[nk]['name_en']}. Win for a chance to recruit them (Tier {hn['tier']})." if hn else ""
        elif b["kind"] == "quest":
            q = b.get("quest_id", "")
            if q.startswith("HQ"):
                hn = b["name_ko"].split("의 서사")[0].lstrip("[")
                he = next((h for h in heroes["heroes"] if h["name_ko"] == hn), None)
                step = b["step"]; nk = b["nation"]
                nm_en = f"[{he['name_en'] if he else hn}'s Saga {step}/3] " + {1: "First Meeting", 2: "Proof of Trust", 3: "The Pact"}[step] + f": {REGION_EN[nk].get(b['region'], b['region'])}"
                fl_en = {1: f"{he['name_en'] if he else hn} asks Leon a first favor. {BATTLE_TYPE_EN[b['type']][1]}", 2: f"{he['name_en'] if he else hn} wants further proof of Leon's skill. Condition: {{cond}}.", 3: f"The final test. Clear it as required and {he['name_en'] if he else hn} formally joins. Condition: {{cond}}."}[step]
                fl_en = fl_en.replace("{cond}", ko_cond_en(b["clear_condition"]["key"]))
            else:
                cls = b["clear_condition"]["key"].split(":")[1]; nk = b["nation"]
                nm_en = f"[{CN_EN[cls]} Trial {b['step']}/3] {NKO[nk]['name_en']} {REGION_EN[nk].get(b['region'], b['region'])}"; fl_en = f"A trial fought with {CN_EN[cls]} heroes only."
        put(f"battle.{b['id']}.name", b["name_ko"], nm_en); put(f"battle.{b['id']}.flavor", b["flavor"], fl_en)
    for q in quests["quests"]:
        if q["kind"] == "hero_chain":
            he = next(h for h in heroes["heroes"] if h["id"] == q["hero_id"]); nm = f"{he['name_en']}'s Saga"
            ds = f"A three-step saga quest unlocked by clearing {he['name_en']}'s encounter once. Clear all steps as required to recruit {he['name_en']} for certain."
        elif q["kind"] == "class_trial":
            nm = f"{CN_EN[q['class']]} Trial"; rh = next(h for h in heroes["heroes"] if h["id"] == q["reward"]["hero_guaranteed"])
            ds = f"Clear three battles with {CN_EN[q['class']]} heroes only to earn {rh['name_en']} (Tier 2) and the {CN_EN[q['class']]} Emblem."
        elif q["kind"] == "origin_pact":
            nm = f"Pact of {ON_EN[q['origin']]}"; rh = next(h for h in heroes["heroes"] if h["id"] == q["reward"]["hero_guaranteed"])
            ds = f"Clear the encounters of all nine Tier 1–3 {ON_EN[q['origin']]} heroes on Hard or above to earn {rh['name_en']} (Tier 3) and the {ON_EN[q['origin']]} Emblem."
        else:
            nm = UI[f"act.{q['act']}"][1]; ds = f"Clear every story battle of Act {q['act']}. Completing the act grants Leon's star-up material and an artifact."
        put(f"quest.{q['id']}.name", q["name_ko"], nm); put(f"quest.{q['id']}.desc", q["desc"], ds)
    if story:
        for s in story["battles"]:
            for i, x in enumerate(s["pre"]): put(f"story.{s['battle_id']}.pre.{i}", x["line"], "")
            for i, x in enumerate(s["post"]): put(f"story.{s['battle_id']}.post.{i}", x["line"], "")
            put(f"story.{s['battle_id']}.direction", s["direction"], "")
        for c in story["cutscenes"]:
            ce = CUTSCENE_EN.get(c["id"], {})
            put(f"cutscene.{c['id']}.title", c["title"], ce.get("title", ""))
            for i, sh in enumerate(c["shots"]):
                she = (ce.get("shots") or [{}] * 99)[i] if i < len(ce.get("shots", [])) else {}
                put(f"cutscene.{c['id']}.shot.{i}.visual", sh["visual"], she.get("visual", ""))
                for j, x in enumerate(sh["lines"]): put(f"cutscene.{c['id']}.shot.{i}.line.{j}", x["line"], (she.get("lines") or [])[j] if j < len(she.get("lines", [])) else "")
        for r in story["recruit"]: put(f"recruit.{r['hero_id']}", r["line"], "")
        for lo in story["lobby"]:
            for i, l in enumerate(lo["lines"]): put(f"lobby.{lo['hero_id']}.{i}", l, "")
        speakers = sorted({x["speaker"] for s in story["battles"] for x in s["pre"] + s["post"]} | {x["speaker"] for c in story["cutscenes"] for sh in c["shots"] for x in sh["lines"]})
        for sp in speakers:
            if sp == "N": continue
            he = next((h for h in heroes["heroes"] if h["name_ko"] == sp), None)
            put(f"speaker.{sp}", sp, he["name_en"] if he else SPEAKER_EN.get(sp, ""))
    json.dump(ko, open(os.path.join(ROOT, "data", "strings_ko.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    json.dump(en, open(os.path.join(ROOT, "data", "strings_en.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    with open(os.path.join(ROOT, "data", "strings_unity.csv"), "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f); w.writerow(["Key", "Korean(ko)", "English(en)"])
        for k in ko: w.writerow([k, ko[k], en[k]])
    # 집계
    groups = {}
    for k in ko:
        g = k.split(".")[0]; t = groups.setdefault(g, [0, 0]); t[0] += 1; t[1] += 1 if en[k] else 0
    total = len(ko); done = sum(1 for k in ko if en[k])
    print(f"strings: {total} keys, en translated {done} ({done/total:.0%})")
    for g, (n, d) in sorted(groups.items()): print(f"  {g:12s} {d:5d}/{n:5d} en")
    GROUP_KO = {"ui": "UI 문자열", "origin": "출신 특성", "class": "직업 특성", "hero": "영웅(이름·칭호·서사·스킬)", "item": "아이템", "nation": "국가", "region": "지역", "faction": "적 세력", "monster": "몬스터",
                "battle_type": "전투 유형", "battle": "전투(이름·플레이버)", "quest": "퀘스트", "story": "스토리 대사(전투 전후)", "cutscene": "컷신", "recruit": "영입 대사", "lobby": "로비 대사", "speaker": "화자명"}
    L = ["# 17. 로컬라이즈 문자열 테이블", "", "자동 생성: `python tools/gen_strings.py`. 산출물: `data/strings_ko.json`, `data/strings_en.json`(평탄 키→문자열), `data/strings_unity.csv`(Unity Localization CSV Extension 임포트용: Key, Korean(ko), English(en)).",
         "원본: 한글은 데이터(JSON)·대본에서 추출, 영문은 `tools/strings_en_1.py`(UI·특성·국가·세력·몬스터·전투 유형·템플릿), `strings_en_2.py`(영웅 칭호·스킬·서사, 아이템 효과 템플릿), `strings_en_3.py`(컷신).", "",
         "## 키 체계", "", "```", "ui.{section}.{key}                    UI 문자열 ({act}, {n} 등 중괄호 치환자 사용)", "origin.{key}.name|desc|synergy       출신 특성", "class.{key}.name|desc|synergy        직업 특성",
         "hero.{id}.name|title|lore|skill_name|skill_desc   영웅 (P000 레온, NPC_ELIA 엘리아 포함)", "item.{id}.name|desc                 아이템 (영문 desc는 능력치+훅 템플릿으로 생성)", "nation.{key}.name|desc|capital|ruler|category   국가",
         "region.{nation}.{0..4}               지역", "faction.{ko}                         적 세력", "monster.{key}.name                   몬스터", "battle_type.{key}.name|desc|rule     전투 유형",
         "battle.{id}.name|flavor              전투 1,604 (영문은 템플릿 치환)", "quest.{id}.name|desc                 퀘스트 103", "story.{battle_id}.pre|post.{i}, story.{battle_id}.direction   스토리 전투 대사", "cutscene.{id}.title|shot.{i}.visual|shot.{i}.line.{j}      컷신",
         "recruit.{hero_id}, lobby.{hero_id}.{i}   영입·로비 대사", "speaker.{ko}                         화자 표시명", "```", "",
         "## 커버리지", "", f"총 {total:,}개 키, 영문 {done:,}개({done/total:.0%}).", "", "| 그룹 | 키 수 | 영문 완료 | 비고 |", "|---|---|---|---|"]
    note = {"story": "번역 대기 (494줄, 한글 확정 후 일괄 번역)", "recruit": "번역 대기", "lobby": "번역 대기", "battle_type": "rule(특수 규칙) 영문 대기", "item": "소모품 설명 일부 대기"}
    for g, (n, d) in sorted(groups.items()): L.append(f"| {GROUP_KO.get(g, g)} | {n:,} | {d:,} ({d/n:.0%}) | {note.get(g, '') if d < n else '완료'} |")
    L += ["", "## Unity 임포트", "", "1. Package Manager: Localization + CSV Extension. 2. Locales ko-KR, en-US 생성. 3. String Table `Game` 생성 후 `data/strings_unity.csv` 임포트(Key 열 = 키, 열 헤더의 로케일 코드 매칭).",
          "4. 코드: `LocalizationSettings.StringDatabase.GetLocalizedString(\"Game\", \"hero.H001.name\")`. 치환자는 Smart String `{act}` 형식으로 그대로 사용. 5. 데이터 재생성 시 CSV를 다시 임포트(키 안정: 데이터 ID 기반).", "",
          "## 번역 규칙", "", "- 고유명사 표기 고정: 아르켄 Arken, 쐐기 the (World) Spire, 재의 날개 the Ashwing, 푸른 비늘 the Bluescale, 용의 신부 the Dragon Bride, 조화의 봉인 the Seal of Harmony, 용의 보석 Dragon Gems.",
          "- 영웅 이름은 데이터의 name_en, 국가는 name_en, 지역·세력·몬스터는 본 테이블의 영문을 기준으로 통일.", "- 영문 길이 확장 +30%를 UI 폭에 반영(12 문서 §3)."]
    open(os.path.join(ROOT, "docs", "17_로컬라이즈_문자열_테이블.md"), "w", encoding="utf-8").write("\n".join(L) + "\n")
    return groups, total, done


def ko_cond_en(key):
    base = key.split(":")[0]
    if base == "origin_count": _, o, n = key.split(":"); return f"Include {n}+ {ON_EN[o]} heroes"
    if base == "class_count": _, c, n = key.split(":"); return f"Include {n}+ {CN_EN[c]} heroes"
    if base == "class_only": return f"{CN_EN[key.split(':')[1]]} heroes only"
    if base == "origin_only": return f"{ON_EN[key.split(':')[1]]} heroes only"
    return UI.get(f"cond.{key}", ("", key))[1]


SPEAKER_EN = {"레온": "Leon", "엘리아": "Elia", "스카르": "Skar", "베스카": "Veska", "이르자": "Irza", "모르가스": "Morgath", "바르그라드": "Vargrad", "재의 병사": "Ash Soldier", "재의 날개 첩자": "Ashwing Spy", "도적 두목": "Bandit Chief",
              "투기장 사회자": "Arena Announcer", "검은 손 연락책": "Black Hand Contact", "공작의 사절": "Duke's Envoy", "왕당파 장교": "Royalist Officer", "재의 날개 첩자 지휘관": "Ashwing Spymaster", "후작 부인 이네스": "Marchioness Ines",
              "검은 손 두목": "Black Hand Boss", "광신도": "Zealot", "심문관": "Inquisitor", "해족 사절": "Merfolk Envoy", "적대 씨족장": "Rival Clan Chief", "재의 선봉장": "Ash Vanguard Leader", "술탄 친위대장": "Captain of the Sultan's Guard",
              "미라 군주": "Mummy Lord", "칸 테무르": "Khan Temur", "서리 마녀": "Frost Witch", "리자드맨 신관": "Lizardfolk Priest", "뱀파이어 백작 라즐로": "Count Laszlo", "요정 여왕 티타니아": "Fae Queen Titania", "정령왕의 대리인": "Regent of the Spirit King",
              "방어 자동인형": "Defense Automaton", "고대 자동인형": "Ancient Automaton", "둥지 수호 용족": "Nest Guardian", "용의 유령": "Dragon Ghost", "재의 날개 정예": "Ashwing Elite", "재의 날개 전령": "Ashwing Herald", "재의 요새장": "Ash Fortress Warden",
              "재의 장군 셋": "The Three Ash Generals", "재의 장군": "Ash General", "재의 사제장": "Ash High Priest", "재의 잔당": "Ash Remnants", "잭 스캐빈": "Jack Scavin"}

if __name__ == "__main__":
    main()
