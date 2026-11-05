# -*- coding: utf-8 -*-
"""
세계/전투/퀘스트/경제 JSON 생성기.
출력: data/nations.json, data/battles.json, data/quests.json, data/economy.json

전투 구성:
  S###   메인 스토리 전투 76 (5막)
  B####  지역 전투 1080 (국가 24 × 지역 5 × 9)
  E###   영웅 조우 전투 196 (영웅당 1, 확률 영입)
  Q###-# 영웅 퀘스트 체인 전투 (계층 4·5 영웅 70명 × 3) + 직업 시련 (14 × 3)
각 전투는 난이도 3단계(보통/어려움/악몽)와 난이도별 보상을 가진다.
"""
import json, os, sys, random, math
sys.path.insert(0, os.path.dirname(__file__))
from world_data import NATIONS, MONSTERS, FACTION_POOL, BATTLE_TYPES, PARTICIPATION, DIFFICULTIES
from story_data import STORY_BATTLES
from roster_data import ORIGINS, CLASSES

OUT = os.path.join(os.path.dirname(__file__), "..", "data")
rng = random.Random(20261104)

HEROES = json.load(open(os.path.join(OUT, "heroes.json"), encoding="utf-8"))["heroes"]
ITEMS = json.load(open(os.path.join(OUT, "items.json"), encoding="utf-8"))["items"]
NAT = {n[0]: n for n in NATIONS}
MON = {m[0]: m for m in MONSTERS}
BT = {b[0]: b for b in BATTLE_TYPES}
ONAME = {o[0]: o[1] for o in ORIGINS}
CNAME = {c[0]: c[1] for c in CLASSES}
HERO_BY_NAME = {h["name_ko"]: h for h in HEROES}

# 출신 → 국가 후보 (조우/퀘스트 전투 배치)
ORIGIN_NATIONS = {
    "astel": ["astel", "mir"], "valheim": ["valheim", "frost_isles"], "sairam": ["sairam"], "karna": ["karna", "makab"],
    "lies": ["lies", "tiama"], "elowen": ["elowen", "veil"], "grandur": ["grandur"], "neos": ["neos"], "nox": ["nox", "twilight"],
    "celestia": ["celestia"], "dragonkin": ["drakestan", "ashfell"], "torga": ["torga", "kurgan", "zyros"], "lumen": ["lumen"], "freelancer": ["bromel", "harben"],
}
ACT_BY_DANGER = lambda d: 1 if d <= 2 else 2 if d <= 5 else 3 if d <= 8 else 4 if d == 9 else 5

# ───────── 경제 상수 ─────────
ECON = {
    "gold_base": {"const": 100, "per_level": 28, "desc": "전투 기본 골드 = 100 + 28 × 전투 레벨(1~100), × 유형 배수 × 난이도 배수"},
    "exp_per_level": 10,
    "stamina": {"hero_max": 100, "regen_minutes_per_point": 6, "player_max": 150,
                "cost_per_hero": {"normal": 10, "hard": 14, "nightmare": 18},
                "multi_wave_mult": 1.5, "multi_wave_types": ["defense", "survival", "expedition", "arena", "raid", "decisive"]},
    # 팀 슬롯: 1막 스토리의 참전 모드(소대 4 → 부대 6 → 대군 8)를 용병 레벨이 따라가도록 초반을 빠르게(Lv4 4명, Lv8 6명, Lv12 8명, Lv20 10명). 20 문서 §4.
    "team_size_by_player_level": {str(lv): (1 if lv < 2 else 2 if lv < 3 else 3 if lv < 4 else 4 if lv < 6 else 5 if lv < 8 else 6 if lv < 10 else 7 if lv < 12 else 8 if lv < 16 else 9 if lv < 20 else 10) for lv in range(1, 61)},
    # 레벨업 필요 EXP(해당 레벨에서 다음 레벨까지): 120 + 60×Lv. 누적 Lv8 ≈ 2,520(약 25전투), Lv12 ≈ 5,280, Lv20 ≈ 13,680(1막 완주), Lv36 ≈ 42,000.
    "player_level_exp": {str(lv): 120 + 60 * lv for lv in range(1, 61)},
    "star_up_cost": {
        "1_to_2": {str(t): {"M001": [30, 50, 80, 120, 180][t - 1], "M002": [0, 2, 4, 8, 12][t - 1], "M003": 0, "gold": [500, 1000, 2000, 4000, 8000][t - 1]} for t in range(1, 6)},
        "2_to_3": {str(t): {"M001": [80, 130, 200, 300, 450][t - 1], "M002": [5, 10, 16, 25, 40][t - 1], "M003": [1, 2, 3, 5, 8][t - 1], "gold": [2000, 4000, 8000, 16000, 32000][t - 1]} for t in range(1, 6)},
        "note": "모든 영웅은 동일한 재료 구성(영혼의 파편 M001, 용의 정수 M002, 별의 결정 M003 + 골드)으로 승급. 수량은 계층별로만 다르다.",
    },
    "hero_value_gold_equiv": {"1": 1500, "2": 3500, "3": 8000, "4": 18000, "5": 40000},
    "hero_drop_base_pct": {"1": 35, "2": 25, "3": 15, "4": 8, "5": 4},
    "hero_drop_difficulty_mult": {d[0]: d[4] for d in DIFFICULTIES},
    "hero_drop_cap_pct": 90,
    "duplicate_hero_conversion": {"M001_by_tier": {"1": 10, "2": 20, "3": 40, "4": 80, "5": 150}, "affinity": 5},
    "affinity_pity": {"max": 100, "per_failed_encounter": {"1": 10, "2": 8, "3": 6, "4": 4, "5": 3}, "desc": "조우 전투 실패(미획득) 시 해당 영웅 호감도 누적. 100 도달 시 다음 조우 승리에서 확정 영입."},
    "regional_native_hero_drop_pct": {"normal": 2, "hard": 3, "nightmare": 5, "desc": "지역 전투에서 국가 토착 출신 계층 1~3 영웅 무작위 드랍"},
    "item_drop": {"component_pct": {"normal": 30, "hard": 40, "nightmare": 50}, "completed_pct_from_level20": {"normal": 8, "hard": 12, "nightmare": 18},
                  "artifact_pct_from_level50": {"normal": 2, "hard": 4, "nightmare": 7}, "national_pct": {"normal": 1, "hard": 2, "nightmare": 4},
                  "radiant_pct_nightmare_from_level70": 2, "support_pct_from_level30": {"normal": 2, "hard": 3, "nightmare": 5}},
    "material_drop": {"M001_formula": "round(3 + level×0.12) × 난이도 보상 배수 (사냥/정찰 ×1.5)",
                      "M002": {"guaranteed_types": ["hunt", "raid", "decisive"], "chance_pct_hard": 25, "chance_pct_nightmare": 50},
                      "M003": {"nightmare_only": True, "chance_pct": 15, "guaranteed_types": ["raid", "decisive"]}},
    "premium_currency": {"name": "용의 보석", "en": "Dragon Gem", "sources": ["첫 클리어 보상", "업적", "구매"], "gold_exchange": "1 보석 = 100 골드(일방향)"},
}


def gold_for(level, type_mult, diff_mult):
    return int(round((ECON["gold_base"]["const"] + ECON["gold_base"]["per_level"] * level) * type_mult * diff_mult / 10.0) * 10)


def stamina_cost(btype, diff):
    c = ECON["stamina"]["cost_per_hero"][diff]
    if btype in ECON["stamina"]["multi_wave_types"]:
        c = int(round(c * ECON["stamina"]["multi_wave_mult"]))
    return c


def unit_count(mode, level, btype):
    base = {"solo": 1, "squad": rng.randint(3, 4), "team": rng.randint(5, 7), "army": rng.randint(7, 9), "free": rng.randint(4, 7)}[mode]
    if btype == "invasion": base += 3
    if btype == "suppression": base += 4
    if btype in ("hunt", "raid", "decisive", "duel", "bounty"): pass
    return max(1, min(12, base))


def enemy_star(level, diff):
    # 보통: 저레벨 1성, 고레벨 2성 섞임 / 어려움 +1 / 악몽 +2 (최대 3)
    base = 1 if level < 35 else (2 if rng.random() < min(0.9, (level - 35) / 60) else 1)
    add = {"normal": 0, "hard": 1, "nightmare": 2}[diff]
    return min(3, base + add)


def build_composition(nation_key, level, mode, btype, boss_key=None, hero_enemy=None):
    """적 편성: 세력 풀에서 몬스터 선택. 반환 dict(units=[{unit,tier,star_by_diff}], boss=..)"""
    nation = NAT[nation_key]
    factions = rng.sample(nation[12], k=min(len(nation[12]), rng.choice([1, 1, 2])))
    pool = []
    for f in factions:
        pool += FACTION_POOL[f]
    pool = list(dict.fromkeys(pool))
    cnt = unit_count(mode, level, btype)
    if btype == "suppression":
        pool = [p for p in pool if MON[p][3] <= 3] or pool
    units = []
    target_tier = max(1, min(5, 1 + level // 22))
    for _ in range(cnt):
        # 레벨에 맞는 계층 선호
        cands = sorted(pool, key=lambda k: abs(MON[k][3] - target_tier) + rng.random())
        k = cands[0] if rng.random() < 0.6 else rng.choice(pool)
        units.append(k)
    if btype == "duel":
        units = [boss_key or max(pool, key=lambda k: MON[k][3])]
    if btype == "strike":
        ranged = [p for p in pool if MON[p][2] in ("ranger", "mage", "artillerist", "summoner", "shaman")]
        if ranged: units = [rng.choice(ranged) for _ in units]
    comp = [{"unit": k, "name_ko": MON[k][1], "class": MON[k][2], "tier": MON[k][3]} for k in units]
    boss = None
    if btype in ("hunt", "raid", "decisive", "bounty", "assassination", "monster_hunt") or boss_key:
        bk = boss_key or max(pool, key=lambda k: MON[k][3] + rng.random())
        boss = {"unit": bk, "name_ko": MON[bk][1], "class": MON[bk][2], "tier": min(5, MON[bk][3] + (1 if btype in ("hunt", "raid", "decisive") else 0)),
                "hp_mult": {"hunt": 2.0, "raid": 4.0, "decisive": 3.0, "bounty": 1.5, "assassination": 1.5, "monster_hunt": 1.5}.get(btype, 1.5),
                "role": {"bounty": "현상금 대상", "assassination": "지휘관", "monster_hunt": "우두머리"}.get(btype, "보스")}
        if btype == "duel":
            comp = []
    waves = {"defense": 3, "survival": 5, "expedition": rng.choice([2, 3]), "arena": 3}.get(btype, 1)
    structures = []
    if btype == "siege": structures.append({"side": "enemy", "name_ko": "성벽", "hp_mult": 6.0, "aura": "화살비: 아군 전체 매초 최대 체력 0.8% 피해"})
    if btype == "guard": structures.append({"side": "ally", "name_ko": rng.choice(["제단", "성문", "세계수 뿌리", "봉인석", "보급고"]), "hp_mult": 3.0, "must_survive": True})
    if btype == "escort": structures.append({"side": "ally", "name_ko": rng.choice(["사절", "상인 마차", "부상병", "학자", "사제"]), "hp_mult": 1.2, "must_survive": True, "mobile": True})
    out = {"units": comp, "boss": boss, "waves": waves, "structures": structures, "factions": factions}
    if hero_enemy:
        out["hero_enemy"] = hero_enemy
    return out


def item_drops(level, diff, nation_key):
    d = ECON["item_drop"]
    drops = [{"pool": "component", "chance_pct": d["component_pct"][diff], "qty": 1}]
    if level >= 20: drops.append({"pool": "completed", "chance_pct": d["completed_pct_from_level20"][diff], "qty": 1})
    if level >= 30: drops.append({"pool": "support", "chance_pct": d["support_pct_from_level30"][diff], "qty": 1})
    if level >= 50: drops.append({"pool": "artifact", "chance_pct": d["artifact_pct_from_level50"][diff], "qty": 1})
    drops.append({"pool": "national", "nation": nation_key, "chance_pct": d["national_pct"][diff], "qty": 1})
    if diff == "nightmare" and level >= 70: drops.append({"pool": "radiant", "chance_pct": d["radiant_pct_nightmare_from_level70"], "qty": 1})
    return drops


def material_drops(level, diff, btype):
    rew_mult = {"normal": 1.0, "hard": 1.7, "nightmare": 3.0}[diff]
    m1 = int(round((3 + level * 0.12) * rew_mult * (1.5 if btype in ("monster_hunt", "recon") else 1.0)))
    mats = {"M001": m1}
    if btype in ECON["material_drop"]["M002"]["guaranteed_types"]:
        mats["M002"] = {"normal": 1, "hard": 2, "nightmare": 4}[diff] + (1 if level > 60 else 0)
    elif diff == "hard": mats["M002_chance"] = {"pct": 25, "qty": 1}
    elif diff == "nightmare": mats["M002_chance"] = {"pct": 50, "qty": 2}
    if diff == "nightmare":
        if btype in ECON["material_drop"]["M003"]["guaranteed_types"]: mats["M003"] = 1 + (1 if level > 80 else 0)
        else: mats["M003_chance"] = {"pct": 15, "qty": 1}
    return mats


def hero_drop_for(hero, diff):
    base = ECON["hero_drop_base_pct"][str(hero["tier"])]
    pct = min(ECON["hero_drop_cap_pct"], round(base * ECON["hero_drop_difficulty_mult"][diff], 1))
    return {"hero_id": hero["id"], "name_ko": hero["name_ko"], "tier": hero["tier"], "chance_pct": pct}


def native_hero_drop(nation_key, diff):
    origin = NAT[nation_key][10]
    cands = [h["id"] for h in HEROES if h["origin"] == origin and h["tier"] <= 3]
    return {"pool": "native_random", "origin": origin, "hero_ids": cands, "chance_pct": ECON["regional_native_hero_drop_pct"][diff]}


def make_difficulties(level, btype, nation_key, hero=None, first_clear=None):
    type_mult = BT[btype][4]
    diffs = {}
    for key, name, enemy_mult, rew_mult, _ in DIFFICULTIES:
        d = {
            "name_ko": name, "enemy_power_mult": enemy_mult, "enemy_star": enemy_star(level, key),
            "stamina_per_hero": stamina_cost(btype, key),
            "rewards": {
                "gold": gold_for(level, type_mult, rew_mult),
                "exp": int(level * ECON["exp_per_level"] * rew_mult),
                "items": item_drops(level, key, nation_key),
                "materials": material_drops(level, key, btype),
                "hero_drop": hero_drop_for(hero, key) if hero else native_hero_drop(nation_key, key),
            },
        }
        diffs[key] = d
    if first_clear:
        diffs["first_clear_bonus"] = first_clear
    return diffs


BATTLES = []
QUESTS = []


def participation(mode, constraints=None):
    p = dict(PARTICIPATION[mode]); p["mode"] = mode; p["constraints"] = constraints or []
    return p


def add_battle(bid, name, nation_key, region, btype, level, act, mode, comp, diffs, flavor, kind, extra=None, constraints=None):
    b = {"id": bid, "name_ko": name, "kind": kind, "nation": nation_key, "nation_ko": NAT[nation_key][1], "region": region,
         "type": btype, "type_ko": BT[btype][1], "level": level, "act": act, "participation": participation(mode, constraints),
         "enemy": comp, "difficulties": diffs, "flavor": flavor, "special_rule": BT[btype][5]}
    if extra: b.update(extra)
    BATTLES.append(b)
    return b


# ───────── 1. 스토리 전투 ─────────
ACT_LEVEL = {1: (3, 18), 2: (18, 48), 3: (48, 78), 4: (78, 90), 5: (90, 100)}
STORY_COMP_OVERRIDES = {"S020": {"units": 5}, "S046": {"units": 4, "waves": 4}, "S059": {"units": 4, "waves": 4}, "S063": {"units": 5, "waves": 2}}
story_ids = []
for idx, (act, nk, region, name, btype, mode, syn, boss, reward_hero) in enumerate(STORY_BATTLES):
    lo, hi = ACT_LEVEL[act]
    same_act = [s for s in STORY_BATTLES if s[0] == act]
    pos = same_act.index((act, nk, region, name, btype, mode, syn, boss, reward_hero))
    level = int(round(lo + (hi - lo) * pos / max(1, len(same_act) - 1)))
    mode = mode or BT[btype][3]
    comp = build_composition(nk, level, mode, btype, boss_key=boss)
    bid = f"S{idx+1:03d}"
    if bid in STORY_COMP_OVERRIDES:   # B9 콘텐츠 재설계: 기대 팀 대비 2배 이상 강했던 전투의 적 수·웨이브 축소 (rng 소비 없음 → 다른 전투 불변)
        ov = STORY_COMP_OVERRIDES[bid]
        comp["units"] = comp["units"][:ov.get("units", len(comp["units"]))]
        comp["waves"] = ov.get("waves", comp["waves"])
    first = {"gold": gold_for(level, 2.0, 1.0), "gems": 20 + act * 10, "items": [{"pool": "completed", "qty": 1}] if act >= 2 else [{"pool": "component", "qty": 2}]}
    if reward_hero:
        h = HERO_BY_NAME[reward_hero]
        first["hero_guaranteed"] = {"hero_id": h["id"], "name_ko": h["name_ko"], "tier": h["tier"]}
    diffs = make_difficulties(level, btype, nk, first_clear=first)
    add_battle(bid, name, nk, region, btype, level, act, mode, comp, diffs, syn, "story",
               extra={"story_order": idx + 1, "unlock_after": story_ids[-1] if story_ids else None})
    story_ids.append(bid)

# ───────── 2. 지역 전투 1080 ─────────
TYPE_POOL = ["skirmish", "skirmish", "monster_hunt", "monster_hunt", "defense", "escort", "hunt", "duel", "ambush", "expedition", "bounty",
             "invasion", "survival", "trial", "rescue", "assassination", "strike", "suppression", "escape", "recon", "guard", "siege", "raid"]
NAME_TPL = {
    "skirmish": "{region} 접전: {faction}", "siege": "{region} 공성: {faction} 요새", "defense": "{region} 방어전: {faction}의 공세",
    "escort": "{region} 호위 임무", "hunt": "{boss} 토벌", "duel": "{region}의 결투: {boss}", "ambush": "{region} 매복: {faction}",
    "expedition": "{region} 탐험", "bounty": "현상금: {boss}", "invasion": "{region} 침공: {faction} 대군", "survival": "{region} 생존전",
    "trial": "{region}의 시련", "raid": "레이드: {boss}", "rescue": "{region} 구출 작전", "assassination": "암살: {faction} 지휘관",
    "strike": "{region} 기습: {faction} 후방", "suppression": "{region} 진압: {faction}", "monster_hunt": "{region} 사냥: {boss}",
    "arena": "브로멜 투기장 토너먼트 {n}회전", "escape": "{region} 탈출", "recon": "{region} 정찰", "guard": "{region} 수호: {structure}",
}
FLAVOR_TPL = {
    "skirmish": "{nation}의 {region}에서 {faction}과(와) 소규모 교전이 벌어진다.", "siege": "{faction}이(가) 점거한 {region}의 요새를 공략한다.",
    "defense": "{faction}이(가) 세 차례에 걸쳐 {region}을(를) 공격한다. 끝까지 버텨라.", "escort": "{region}을(를) 지나는 {structure}을(를) 목적지까지 호위한다.",
    "hunt": "{region}에 나타난 {boss}을(를) 토벌한다.", "duel": "{region}에서 {boss}이(가) 1대1 결투를 청한다.", "ambush": "{region}에서 {faction}의 매복에 걸렸다. 양쪽에서 적이 온다.",
    "expedition": "{region} 깊숙이 들어가 연속 전투를 치른다. 중간 회복은 없다.", "bounty": "{boss}에게 현상금이 걸렸다. 처치하면 골드 2배.",
    "invasion": "{faction}의 대군이 {region}으로 밀려온다.", "survival": "{region}에서 다섯 차례의 파상 공세를 견뎌라.",
    "trial": "{region}의 시련. 조건을 만족하는 영웅만 참전할 수 있다.", "raid": "{region}의 거대한 {boss}. 대군으로만 도전할 수 있다.",
    "rescue": "{faction}에게 잡힌 포로를 구한다. 간수를 먼저 처치하라.", "assassination": "{faction}의 지휘관을 처치하면 즉시 승리한다.",
    "strike": "{faction}의 후방 보급선을 기습한다.", "suppression": "{region}의 {faction} 폭동을 진압한다. 적은 많지만 약하다.",
    "monster_hunt": "{region}의 {boss} 무리를 사냥한다. 승급 재료 드랍이 많다.", "arena": "브로멜 투기장의 토너먼트. 세 번 연속 이겨야 한다.",
    "escape": "{region}에서 30초 동안 살아남아 탈출한다.", "recon": "{region}을(를) 정찰한다. 보상은 적지만 재료가 잘 나온다.",
    "guard": "{region}의 {structure}을(를) {faction}으로부터 지켜라.",
}
TRIAL_CONSTRAINTS = lambda nk: rng.choice([
    [f"origin_only:{NAT[nk][10]}"], ["max_tier:3"], ["max_star:2"], ["team_size<=4"], [f"class_count:{rng.choice([c[0] for c in CLASSES])}:2"], ["no_duplicate_class"],
])
bno = 0
for ni, n in enumerate(NATIONS):
    nk, nname, _, _, _, _, danger, *_ = n
    act = ACT_BY_DANGER(danger)
    regions = n[11]
    prev = None
    for ri, region in enumerate(regions):
        types = ["skirmish", "monster_hunt"] + rng.sample([t for t in TYPE_POOL if t not in ("skirmish", "monster_hunt")], 7)
        if nk == "bromel" and ri == 1:
            types[2] = "arena"
        rng.shuffle(types)
        for k, btype in enumerate(types):
            bno += 1
            level = max(1, min(100, int(round((danger - 1) * 9 + 2 + ri * 1.8 + k * 0.4 + rng.uniform(-1, 1)))))
            mode = BT[btype][3]
            comp = build_composition(nk, level, mode, btype)
            faction = comp["factions"][0]
            boss = comp["boss"]["name_ko"] if comp["boss"] else MON[comp["units"][0]["unit"]][1] if comp["units"] else "적"
            structure = comp["structures"][0]["name_ko"] if comp["structures"] else "보급고"
            name = NAME_TPL[btype].format(region=region, faction=faction, boss=boss, structure=structure, n=k + 1)
            flavor = FLAVOR_TPL[btype].format(nation=nname, region=region, faction=faction, boss=boss, structure=structure)
            constraints = TRIAL_CONSTRAINTS(nk) if btype == "trial" else None
            first = {"gold": gold_for(level, 1.0, 1.0), "gems": 5 + act * 2, "materials": {"M001": 5 + level // 10}}
            diffs = make_difficulties(level, btype, nk, first_clear=first)
            bid = f"B{bno:04d}"
            add_battle(bid, name, nk, region, btype, level, act, mode, comp, diffs, flavor, "regional",
                       extra={"region_index": ri, "unlock_act": act, "unlock_after": prev}, constraints=constraints)
            prev = bid

# ───────── 3. 영웅 조우 전투 196 ─────────
origin_rot = {}
for i, h in enumerate(HEROES):
    nats = ORIGIN_NATIONS[h["origin"]]
    r = origin_rot.get(h["origin"], 0); origin_rot[h["origin"]] = r + 1
    nk = nats[r % len(nats)]
    if h["name_ko"] == "이그니스": nk = "ashfell"
    if h["name_ko"] == "아젤리아": nk = "drakestan"
    n = NAT[nk]
    region = n[11][(h["tier"] - 1) % 5]
    danger = n[6]
    level = max(1, min(100, int(round((danger - 1) * 9 + 2 + (h["tier"] - 1) * 3 + rng.uniform(-2, 2)))))
    act = ACT_BY_DANGER(danger)
    mode = "free"
    hero_enemy = {"hero_id": h["id"], "name_ko": h["name_ko"], "tier": h["tier"], "star_by_difficulty": {"normal": 1, "hard": 2, "nightmare": 3}}
    comp = build_composition(nk, level, "squad", "encounter", hero_enemy=hero_enemy)
    name = f"영웅 조우: {h['title']} {h['name_ko']}"
    flavor = f"{n[1]}의 {region}에서 {h['name_ko']}이(가) 레온 일행 앞을 막아선다. 승리하면 {h['name_ko']}을(를) 확률적으로 영입한다(계층 {h['tier']}: 기본 {ECON['hero_drop_base_pct'][str(h['tier'])]}%)."
    first = {"gold": gold_for(level, 1.2, 1.0), "gems": 10, "materials": {"M001": 10 + h["tier"] * 5}, "affinity": {"hero_id": h["id"], "value": 10}}
    diffs = make_difficulties(level, "encounter", nk, hero=h, first_clear=first)
    add_battle(f"E{i+1:03d}", name, nk, region, "encounter", level, act, mode, comp, diffs, flavor, "encounter",
               extra={"hero_id": h["id"], "repeatable": True, "affinity_on_fail": ECON["affinity_pity"]["per_failed_encounter"][str(h["tier"])]})

# ───────── 4. 영웅 퀘스트 체인 (계층 4·5 영웅 70명 × 3전투) ─────────
COND_POOL = [
    ("difficulty>=hard", "어려움 이상 난이도로 클리어"), ("no_death", "아군 전원 생존"), ("time<=25", "25초 이내 승리"),
    ("team_size<=4", "4명 이하로 참전"), ("max_star:2", "2성 이하 영웅만 참전"), ("max_tier:3", "계층 3 이하 영웅만 참전"),
]
CHAIN_TYPES = ["trial", "hunt", "rescue", "escort", "duel", "defense", "ambush", "expedition", "assassination", "guard"]
qno = 0
for h in [x for x in HEROES if x["tier"] >= 4]:
    qno += 1
    nats = ORIGIN_NATIONS[h["origin"]]
    nk = nats[0] if h["name_ko"] != "이그니스" else "ashfell"
    n = NAT[nk]; danger = n[6]; act = ACT_BY_DANGER(danger)
    chain = []
    conds_used = rng.sample(COND_POOL, 2)
    chain_conds = [None, conds_used[0], conds_used[1]]
    if h["tier"] == 5:
        chain_conds[0] = (f"origin_count:{h['origin']}:2", f"{ONAME[h['origin']]} 출신 영웅 2명 이상 포함")
    else:
        chain_conds[0] = (f"class_count:{h['class']}:1", f"{CNAME[h['class']]} 영웅 1명 이상 포함")
    for step in range(3):
        btype = rng.choice(CHAIN_TYPES)
        region = n[11][(step * 2 + h["tier"]) % 5]
        level = max(1, min(100, (danger - 1) * 9 + 6 + step * 3 + (h["tier"] - 4) * 4))
        mode = BT[btype][3]
        comp = build_composition(nk, level, mode, btype)
        cond = chain_conds[step]
        name = f"[{h['name_ko']}의 서사 {step+1}/3] " + {0: "첫 만남", 1: "신뢰의 증명", 2: "맹약"}[step] + f": {region}"
        flavor = {0: f"{h['name_ko']}({h['title']})이(가) 레온에게 첫 번째 부탁을 한다. {BT[btype][2]}",
                  1: f"{h['name_ko']}은(는) 레온의 실력을 더 확인하고 싶어 한다. 조건: {cond[1]}.",
                  2: f"마지막 시험. 이 전투를 조건대로 끝내면 {h['name_ko']}이(가) 정식으로 동료가 된다. 조건: {cond[1]}."}[step]
        diffs = make_difficulties(level, btype, nk)
        bid = f"Q{qno:03d}-{step+1}"
        add_battle(bid, name, nk, region, btype, level, act, mode, comp, diffs, flavor, "quest",
                   extra={"quest_id": f"HQ{qno:03d}", "step": step + 1, "clear_condition": {"key": cond[0], "desc": cond[1]}}, constraints=[cond[0]] if cond[0].startswith(("origin", "class", "max", "team")) else None)
        chain.append({"battle_id": bid, "condition": {"key": cond[0], "desc": cond[1]}})
    QUESTS.append({"id": f"HQ{qno:03d}", "kind": "hero_chain", "name_ko": f"{h['name_ko']}의 서사", "hero_id": h["id"], "hero_name": h["name_ko"], "tier": h["tier"],
                   "nation": nk, "unlock": {"act": act, "requires_encounter_clear": f"E{HEROES.index(h)+1:03d}"},
                   "steps": chain, "reward": {"hero_guaranteed": h["id"], "gold": 2000 * h["tier"], "gems": 30 * h["tier"], "items": [{"pool": "emblem_of_origin", "origin": h["origin"], "qty": 1}]},
                   "desc": f"{h['name_ko']}의 조우 전투를 한 번 클리어하면 열리는 3단계 서사 퀘스트. 모두 조건대로 클리어하면 {h['name_ko']}을(를) 확정 영입한다."})

# ───────── 5. 직업 시련 (14직업 × 3전투) ─────────
for ci, c in enumerate(CLASSES):
    qno += 1
    chain = []
    for step in range(3):
        nk = rng.choice([n[0] for n in NATIONS if n[6] <= 5])
        n = NAT[nk]; danger = n[6]; act = ACT_BY_DANGER(danger)
        region = n[11][step]
        level = max(1, min(100, (danger - 1) * 9 + 2 + step * 4))
        comp = build_composition(nk, level, "team", "trial")
        name = f"[{c[1]}의 시련 {step+1}/3] {n[1]} {region}"
        cond = (f"class_only:{c[0]}", f"{c[1]} 영웅만 참전")
        diffs = make_difficulties(level, "trial", nk)
        bid = f"Q{qno:03d}-{step+1}"
        add_battle(bid, name, nk, region, "trial", level, act, "team", comp, diffs, f"{c[1]} 영웅만으로 치르는 시련. {c[3]}", "quest",
                   extra={"quest_id": f"CQ{ci+1:02d}", "step": step + 1, "clear_condition": {"key": cond[0], "desc": cond[1]}}, constraints=[cond[0]])
        chain.append({"battle_id": bid, "condition": {"key": cond[0], "desc": cond[1]}})
    reward_hero = rng.choice([h for h in HEROES if h["class"] == c[0] and h["tier"] == 2])
    QUESTS.append({"id": f"CQ{ci+1:02d}", "kind": "class_trial", "name_ko": f"{c[1]}의 시련", "class": c[0], "steps": chain,
                   "unlock": {"act": 2, "requires_owned_class_count": 2},
                   "reward": {"hero_guaranteed": reward_hero["id"], "hero_name": reward_hero["name_ko"], "items": [{"pool": "emblem_of_class", "class": c[0], "qty": 1}], "gold": 3000},
                   "desc": f"{c[1]} 영웅만으로 세 전투를 클리어하면 {reward_hero['name_ko']}(계층 2)와 {c[1]}의 상징을 얻는다."})

# ───────── 6. 출신 맹약 퀘스트 (14) ─────────
for oi, o in enumerate(ORIGINS):
    enc = [b["id"] for b in BATTLES if b["kind"] == "encounter" and HERO_BY_NAME[b["enemy"]["hero_enemy"]["name_ko"]]["origin"] == o[0] and HERO_BY_NAME[b["enemy"]["hero_enemy"]["name_ko"]]["tier"] <= 3]
    reward_hero = rng.choice([h for h in HEROES if h["origin"] == o[0] and h["tier"] == 3])
    QUESTS.append({"id": f"OQ{oi+1:02d}", "kind": "origin_pact", "name_ko": f"{o[1]}의 맹약", "origin": o[0],
                   "steps": [{"battle_id": b, "condition": {"key": "difficulty>=hard", "desc": "어려움 이상"}} for b in enc],
                   "unlock": {"act": ACT_BY_DANGER(NAT[ORIGIN_NATIONS[o[0]][0]][6])},
                   "reward": {"hero_guaranteed": reward_hero["id"], "hero_name": reward_hero["name_ko"], "items": [{"pool": "emblem_of_origin", "origin": o[0], "qty": 1}], "gold": 5000, "gems": 50},
                   "desc": f"{o[1]} 출신 계층 1~3 영웅 9명의 조우 전투를 모두 어려움 이상으로 클리어하면 {reward_hero['name_ko']}(계층 3)과 {o[1]}의 상징을 얻는다."})

# ───────── 7. 스토리 퀘스트 (5막) ─────────
ACT_NAMES = {1: "불타는 마을", 2: "일곱 왕국", 3: "숨겨진 나라들", 4: "용의 둥지", 5: "재의 산맥"}
for act in range(1, 6):
    ids = [b["id"] for b in BATTLES if b["kind"] == "story" and b["act"] == act]
    rewards = [b["difficulties"]["first_clear_bonus"].get("hero_guaranteed") for b in BATTLES if b["kind"] == "story" and b["act"] == act]
    rewards = [r for r in rewards if r]
    QUESTS.append({"id": f"SQ{act}", "kind": "story", "name_ko": f"{act}막: {ACT_NAMES[act]}", "act": act,
                   "steps": [{"battle_id": b, "condition": None} for b in ids],
                   "reward": {"gems": 100 * act, "gold": 5000 * act, "items": [{"pool": "artifact", "qty": 1}], "player_star_up": act >= 2, "story_heroes": rewards},
                   "desc": f"{act}막의 모든 스토리 전투를 클리어. 막 완료 시 레온의 성급 승급 재료와 유물을 얻는다."})

# ───────── 출력 ─────────
nations_out = []
for n in NATIONS:
    nk = n[0]
    nations_out.append({"key": nk, "name_ko": n[1], "name_en": n[2], "region_group": n[3], "category": n[4], "civilization": n[5], "danger": n[6],
                        "capital": n[7], "ruler": n[8], "desc": n[9], "native_origin": n[10], "native_origin_ko": ONAME[n[10]], "act": ACT_BY_DANGER(n[6]),
                        "regions": n[11], "enemy_factions": n[12],
                        "battle_count": sum(1 for b in BATTLES if b["nation"] == nk),
                        "national_item": next((it["id"] for it in ITEMS if it.get("nation") == nk), None)})
os.makedirs(OUT, exist_ok=True)
json.dump({"version": 1, "count": len(nations_out), "nations": nations_out}, open(os.path.join(OUT, "nations.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
from collections import Counter
# ── 튜닝 결과 보존: 기존 battles.json의 보스 체력 배수·tuned_power_mult·power_cliff, economy.json의 enemy_power_curve(난이도 보정 곡선)는 재생성 시 유지한다.
_bp = os.path.join(OUT, "battles.json")
if os.path.exists(_bp):
    _prev = {b["id"]: b for b in json.load(open(_bp, encoding="utf-8"))["battles"]}
    _kept = 0
    for b in BATTLES:
        pb = _prev.get(b["id"])
        if not pb: continue
        if b["enemy"]["boss"] and pb["enemy"]["boss"] and pb["enemy"]["boss"].get("tuned"):
            b["enemy"]["boss"]["hp_mult"] = pb["enemy"]["boss"]["hp_mult"]; b["enemy"]["boss"]["tuned"] = True
        for d, dd in b["difficulties"].items():
            pd = pb["difficulties"].get(d, {})
            for k in ("tuned_power_mult", "power_cliff"):
                if k in pd: dd[k] = pd[k]; _kept += 1
    print("preserved tuning fields:", _kept)
_ep = os.path.join(OUT, "economy.json")
if os.path.exists(_ep):
    _pe = json.load(open(_ep, encoding="utf-8"))
    if "enemy_power_curve" in _pe: ECON["enemy_power_curve"] = _pe["enemy_power_curve"]
json.dump({"version": 1, "count": len(BATTLES), "by_kind": dict(Counter(b["kind"] for b in BATTLES)), "by_type": dict(Counter(b["type"] for b in BATTLES)),
           "battle_types": [{"key": b[0], "name_ko": b[1], "desc": b[2], "participation": b[3], "reward_mult": b[4], "rule": b[5]} for b in BATTLE_TYPES],
           "participation": PARTICIPATION, "difficulties": [{"key": d[0], "name_ko": d[1], "enemy_mult": d[2], "reward_mult": d[3], "hero_drop_mult": d[4]} for d in DIFFICULTIES],
           "monsters": [{"key": m[0], "name_ko": m[1], "class": m[2], "tier": m[3], "tag": m[4]} for m in MONSTERS],
           "battles": BATTLES}, open(os.path.join(OUT, "battles.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
json.dump({"version": 1, "count": len(QUESTS), "by_kind": dict(Counter(q["kind"] for q in QUESTS)), "quests": QUESTS}, open(os.path.join(OUT, "quests.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
json.dump(ECON, open(os.path.join(OUT, "economy.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("nations", len(nations_out), "battles", len(BATTLES), dict(Counter(b["kind"] for b in BATTLES)), "quests", len(QUESTS))
