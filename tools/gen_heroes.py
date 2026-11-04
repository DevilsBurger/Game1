# -*- coding: utf-8 -*-
"""
영웅 196명 + 특성(시너지) JSON 생성기.
입력: tools/roster_data.py (수작업 설계)
출력: data/heroes.json, data/traits.json

전투 파라미터는 TFT(롤토체스)와 동일한 체계:
  체력(HP), 공격력(AD), 공격속도(AS), 방어력(Armor), 마법저항력(MR), 사거리(Range, 헥스),
  마나(시작/최대), 치명타 확률/피해, 주문력(AP, 기본 100%).
성급 배율: HP ×1.8/성, AD ×1.5/성 (TFT와 동일). 스킬 수치는 성급별 3단계.
"""
import json, os, sys, hashlib
sys.path.insert(0, os.path.dirname(__file__))
from roster_data import HEROES, ORIGINS, CLASSES, PLAYER_UNIT

OUT = os.path.join(os.path.dirname(__file__), "..", "data")

# ───────── 직업별 기본 능력치 (계층1, 1성 기준) ─────────
# hp, ad, as, armor, mr, range, mana_start, mana_max
CLASS_BASE = {
    "knight":      dict(hp=760, ad=50, as_=0.60, armor=45, mr=40, range=1, mana=(40, 100)),
    "warrior":     dict(hp=720, ad=58, as_=0.65, armor=35, mr=30, range=1, mana=(30, 90)),
    "assassin":    dict(hp=560, ad=66, as_=0.75, armor=25, mr=25, range=1, mana=(20, 70)),
    "ranger":      dict(hp=520, ad=62, as_=0.75, armor=20, mr=20, range=4, mana=(20, 70)),
    "mage":        dict(hp=520, ad=40, as_=0.65, armor=20, mr=25, range=4, mana=(30, 80)),
    "priest":      dict(hp=560, ad=42, as_=0.65, armor=22, mr=30, range=3, mana=(30, 80)),
    "guardian":    dict(hp=790, ad=48, as_=0.55, armor=40, mr=45, range=1, mana=(50, 110)),
    "duelist":     dict(hp=620, ad=56, as_=0.80, armor=30, mr=25, range=1, mana=(20, 70)),
    "summoner":    dict(hp=540, ad=40, as_=0.60, armor=20, mr=25, range=4, mana=(40, 100)),
    "artillerist": dict(hp=520, ad=70, as_=0.55, armor=20, mr=20, range=5, mana=(30, 90)),
    "shaman":      dict(hp=580, ad=45, as_=0.65, armor=25, mr=35, range=3, mana=(30, 80)),
    "bard":        dict(hp=580, ad=45, as_=0.65, armor=25, mr=30, range=3, mana=(40, 100)),
    "dragoon":     dict(hp=680, ad=60, as_=0.70, armor=32, mr=30, range=1, mana=(30, 90)),
    "engineer":    dict(hp=600, ad=48, as_=0.65, armor=28, mr=28, range=3, mana=(40, 100)),
}
TIER_MULT = {1: 1.00, 2: 1.14, 3: 1.30, 4: 1.48, 5: 1.70}   # HP/AD/스킬 기본 수치
TIER_DEF_ADD = {1: 0, 2: 5, 3: 10, 4: 15, 5: 22}             # 방어력/마저 가산
STAR_HP = [1.0, 1.8, 3.24]
STAR_AD = [1.0, 1.5, 2.25]

# ───────── 스킬 원형(archetype) 기본 파라미터 (계층1 기준, 성급 3단계) ─────────
# dmg: 마법 피해 기본값(주문력 100% 기준), ad_ratio: 공격력 배율(물리), heal/shield: 수치
ARCHETYPES = {
    "burst_st":        dict(kind="damage", dmg=[260, 390, 600], target="current", radius=0),
    "burst_ad":        dict(kind="damage", ad_ratio=[2.4, 2.5, 2.7], flat=[40, 60, 90], target="current", radius=0, crit=True),
    "burst_ad_long":   dict(kind="damage", ad_ratio=[2.6, 2.7, 2.9], flat=[40, 60, 90], target="farthest", radius=0),
    "aoe_target":      dict(kind="damage", dmg=[180, 270, 420], target="current", radius=1),
    "aoe_target_ad":   dict(kind="damage", ad_ratio=[1.5, 1.6, 1.7], flat=[30, 45, 70], target="current", radius=1),
    "aoe_self":        dict(kind="damage", ad_ratio=[1.6, 1.7, 1.8], flat=[40, 60, 90], target="self", radius=1, self_ad_pct=[10, 15, 20], buff_dur=4),
    "aoe_line":        dict(kind="damage", dmg=[220, 330, 520], target="current", line=3, slow=30, slow_dur=3),
    "aoe_line_ad":     dict(kind="damage", ad_ratio=[1.9, 2.0, 2.2], flat=[40, 60, 90], target="current", line=3),
    "chain":           dict(kind="damage", dmg=[200, 300, 470], target="current", bounces=3, falloff=0.75),
    "chain_ad":        dict(kind="damage", ad_ratio=[1.8, 1.9, 2.0], flat=[30, 45, 70], target="current", bounces=2, falloff=0.7),
    "heal_lowest":     dict(kind="heal", heal=[320, 480, 760], target="lowest_ally"),
    "heal_aoe":        dict(kind="heal", heal=[160, 240, 380], target="all_allies"),
    "shield_self":     dict(kind="shield", shield=[380, 560, 880], target="self", duration=5),
    "shield_allies":   dict(kind="shield", shield=[180, 270, 420], target="adjacent_allies", duration=5),
    "taunt_shield":    dict(kind="shield", shield=[400, 600, 950], target="self", duration=5, taunt_radius=2, taunt_dur=2.5),
    "buff_as_self":    dict(kind="buff", as_pct=[60, 80, 110], duration=5, target="self"),
    "buff_as_allies":  dict(kind="buff", as_pct=[25, 35, 50], duration=5, target="all_allies"),
    "buff_ad_allies":  dict(kind="buff", ad_pct=[20, 30, 45], duration=5, target="all_allies"),
    "buff_ap_allies":  dict(kind="buff", ap_flat=[20, 30, 45], duration=5, target="all_allies"),
    "stun_st":         dict(kind="damage", dmg=[200, 300, 470], target="current", radius=0, stun=1.5),
    "stun_aoe":        dict(kind="damage", dmg=[150, 225, 350], target="current", radius=1, stun=1.25),
    "dot_target":      dict(kind="dot", dmg=[360, 540, 850], duration=6, target="current"),
    "armor_shred":     dict(kind="damage", dmg=[180, 270, 420], target="current", radius=0, shred=[30, 40, 50], shred_dur=6),
    "lifesteal_strike": dict(kind="damage", ad_ratio=[2.0, 2.1, 2.3], flat=[40, 60, 90], target="current", radius=0, heal_pct=50),
    "execute":         dict(kind="damage", ad_ratio=[1.8, 1.9, 2.1], flat=[50, 75, 120], target="lowest_enemy", dash=True, execute_scale=1.0, reset_on_kill=True),
    "execute_long":    dict(kind="damage", ad_ratio=[2.0, 2.1, 2.3], flat=[50, 75, 120], target="lowest_enemy", execute_scale=1.0),
    "multishot":       dict(kind="empower", shots=[3, 3, 4], bonus_ad_ratio=[0.6, 0.7, 0.8], bonus_flat=[20, 30, 45]),
    "dash_strike":     dict(kind="damage", ad_ratio=[2.2, 2.3, 2.5], flat=[40, 60, 90], target="lowest_enemy", dash=True, crit=True),
    "dash_aoe":        dict(kind="damage", ad_ratio=[1.3, 1.4, 1.5], dmg=[100, 150, 240], target="cluster", dash=True, radius=1, stun=0.75),
    "summon":          dict(kind="summon", count=1, hp_pct=[60, 70, 85], ad_pct=[60, 70, 85], max_active=1, lifetime=12),
    "summon_big":      dict(kind="summon", count=1, hp_pct=[120, 140, 170], ad_pct=[110, 125, 150], max_active=1, lifetime=15),
    "summon_multi":    dict(kind="summon", count=3, hp_pct=[40, 48, 60], ad_pct=[40, 48, 60], max_active=3, lifetime=12),
    "turret":          dict(kind="turret", hp_pct=[45, 55, 70], ad_pct=[70, 80, 95], range=4, max_active=1, lifetime=12),
    "turret_big":      dict(kind="turret", hp_pct=[70, 85, 110], ad_pct=[110, 125, 150], range=4, max_active=1, lifetime=15, radius=1),
}

# ───────── 원형별 전력 계수 (★1, ★2, ★3) ─────────
# 1차 밸런스 시뮬레이션에서 측정된 원형별 평균 보정 비율을 설계 상수로 접어 넣은 값.
# 체력·공격력·스킬 수치에 공통으로 곱한다 (<1: 원형 기본값이 과강 → 하향, >1: 과약 → 상향).
ARCHETYPE_POWER = {
    "aoe_line": [0.91, 0.94, 0.97],
    "aoe_line_ad": [1.12, 1.19, 1.23],
    "aoe_self": [0.96, 0.99, 1.06],
    "aoe_target": [1.18, 1.22, 1.26],
    "aoe_target_ad": [1.1, 1.14, 1.19],
    "armor_shred": [1.2, 1.21, 1.23],
    "buff_ad_allies": [1.4, 1.37, 1.2],
    "buff_ap_allies": [1.61, 1.67, 1.73],
    "buff_as_allies": [1.4, 1.37, 1.27],
    "buff_as_self": [1.07, 1.09, 1.13],
    "burst_ad": [1.01, 1.05, 1.08],
    "burst_ad_long": [1.18, 1.22, 1.25],
    "burst_st": [1.2, 1.21, 1.24],
    "chain": [1.1, 1.14, 1.19],
    "chain_ad": [0.92, 0.97, 1.05],
    "dash_aoe": [0.9, 0.92, 0.95],
    "dash_strike": [1.02, 1.02, 1.04],
    "dot_target": [1.25, 1.3, 1.38],
    "execute": [1.02, 1.07, 1.09],
    "execute_long": [1.14, 1.19, 1.18],
    "heal_aoe": [0.98, 0.92, 0.86],
    "heal_lowest": [0.99, 0.93, 0.84],
    "lifesteal_strike": [0.92, 0.95, 0.98],
    "multishot": [1.02, 1.06, 1.11],
    "shield_allies": [0.77, 0.81, 0.82],
    "shield_self": [0.74, 0.77, 0.74],
    "stun_aoe": [1.09, 1.08, 1.05],
    "stun_st": [0.96, 0.95, 0.95],
    "summon": [1.24, 1.23, 1.26],
    "summon_big": [1.09, 1.09, 1.15],
    "summon_multi": [1.13, 1.12, 1.18],
    "taunt_shield": [0.69, 0.66, 0.61],
    "turret": [1.03, 1.03, 1.06],
    "turret_big": [1.1, 1.12, 1.19],
}

# 각 출신/직업 특성 임계값
ORIGIN_THRESHOLDS = [2, 4, 6, 8]
CLASS_THRESHOLDS = [2, 4, 6]

ORIGIN_EFFECTS = {
    "astel":      dict(hook="astel",      allies_armor=[10, 20, 35, 50], start_shield_pct=[10, 15, 20, 25]),
    "valheim":    dict(hook="valheim",    low_hp_as=[25, 40, 60, 80], low_hp_omnivamp=[10, 15, 20, 25]),
    "sairam":     dict(hook="sairam",     crit=[15, 25, 35, 50], crit_dmg=[10, 20, 30, 45]),
    "karna":      dict(hook="karna",      dr=[30, 40, 50, 60], dr_dur=7, start_mana=[20, 35, 50, 70]),
    "lies":       dict(hook="lies",       mana_on_attack=[3, 5, 7, 10], gold_bonus_pct=[10, 20, 35, 50]),
    "elowen":     dict(hook="elowen",     regen_pct=[1.0, 1.5, 2.2, 3.0], range_bonus=[0, 1, 1, 2]),
    "grandur":    dict(hook="grandur",    allies_armor=[10, 20, 30, 45], allies_mr=[10, 20, 30, 45], item_mult=[1.15, 1.3, 1.5, 1.8]),
    "neos":       dict(hook="neos",       start_as=[15, 25, 40, 60], start_as_dur=8, kill_explode=[100, 150, 250, 400]),
    "nox":        dict(hook="nox",        omnivamp=[8, 12, 18, 25], wraith_from=4),
    "celestia":   dict(hook="celestia",   ap=[20, 35, 55, 80], cast_mana_allies=[5, 8, 12, 20]),
    "dragonkin":  dict(hook="dragonkin",  hp_pct=[15, 25, 40, 60], skill_dmg_pct=[10, 20, 30, 45]),
    "torga":      dict(hook="torga",      ad_pct_per_stack=[2, 3, 4, 6], max_stacks=10),
    "lumen":      dict(hook="lumen",      cheat_death_heal=[20, 30, 40, 60], invuln=2.0),
    "freelancer": dict(hook="freelancer", pct_per_origin=[3, 5, 7, 10]),
}
CLASS_EFFECTS = {
    "knight":      dict(hook="knight",      front_dr=[10, 20, 30]),
    "warrior":     dict(hook="warrior",     hp_pct=[20, 40, 70]),
    "assassin":    dict(hook="assassin",    crit=[20, 40, 60], crit_dmg=[15, 30, 50]),
    "ranger":      dict(hook="ranger",      as_pct=[25, 55, 100]),
    "mage":        dict(hook="mage",        ap=[25, 50, 85], mana_max_mult=[0.9, 0.8, 0.7]),
    "priest":      dict(hook="priest",      heal_pct=[20, 40, 70], allies_omnivamp=[5, 10, 15]),
    "guardian":    dict(hook="guardian",    shield=[150, 300, 500]),
    "duelist":     dict(hook="duelist",     as_per_attack=[4, 7, 12], max_stacks=12),
    "summoner":    dict(hook="summoner",    summon_stat_pct=[30, 60, 100]),
    "artillerist": dict(hook="artillerist", range_bonus=[1, 1, 2], third_attack_ad=[0.6, 1.2, 2.0]),
    "shaman":      dict(hook="shaman",      shred=[20, 35, 50], shred_dur=6),
    "bard":        dict(hook="bard",        start_mana=[10, 20, 30], buff_mult=[1.3, 1.6, 2.0]),
    "dragoon":     dict(hook="dragoon",     start_dr=[30, 50, 70], start_dr_dur=3, dash_dmg_pct=[20, 40, 70]),
    "engineer":    dict(hook="engineer",    turret_stat_pct=[30, 60, 100], allies_as=[5, 10, 15]),
}


def hero_id(idx):
    return f"H{idx+1:03d}"


def build_stats(cls, tier, jitter):
    b = CLASS_BASE[cls]
    m = TIER_MULT[tier]
    hp = round(b["hp"] * m * jitter["hp"])
    ad = round(b["ad"] * m * jitter["ad"])
    as_ = round(b["as_"] * jitter["as"], 3)
    armor = b["armor"] + TIER_DEF_ADD[tier]
    mr = b["mr"] + TIER_DEF_ADD[tier]
    return dict(hp=hp, ad=ad, attack_speed=as_, armor=armor, mr=mr, range=b["range"],
                mana_start=b["mana"][0], mana_max=b["mana"][1], crit_chance=25, crit_damage=140, ap=100)


def scaled_params(arche, tier):
    """스킬 원형 파라미터를 계층 배율로 스케일."""
    base = ARCHETYPES[arche]
    m = TIER_MULT[tier]
    out = {}
    for k, v in base.items():
        if k in ("dmg", "heal", "shield", "flat", "bonus_flat") and isinstance(v, list):
            out[k] = [round(x * m) for x in v]
        else:
            out[k] = v
    return out


def main():
    heroes = []
    for i, h in enumerate(HEROES):
        origin, cls, tier, name_ko, name_en, title, skill_name, arche, skill_desc, lore = h
        # 결정론적 지터(영웅마다 ±4% 개성) — 밸런스 단계에서 재조정됨
        hsh = int(hashlib.md5(name_en.encode()).hexdigest(), 16)
        jitter = {
            "hp": 1 + ((hsh % 9) - 4) / 100.0,
            "ad": 1 + (((hsh >> 8) % 9) - 4) / 100.0,
            "as": 1 + (((hsh >> 16) % 7) - 3) / 100.0,
        }
        stats = build_stats(cls, tier, jitter)
        params = scaled_params(arche, tier)
        hero = {
            "id": hero_id(i),
            "name_ko": name_ko, "name_en": name_en, "title": title,
            "origin": origin, "class": cls, "tier": tier,
            "rarity": {1: "일반", 2: "고급", 3: "희귀", 4: "영웅", 5: "전설"}[tier],
            "stats": stats,
            "star_scaling": {"hp": STAR_HP, "ad": STAR_AD},
            "skill": {"name": skill_name, "archetype": arche, "desc": skill_desc, "params": params},
            "archetype_power": ARCHETYPE_POWER.get(arche, [1.0, 1.0, 1.0]),
            "lore": lore,
            "balance": {"hp_mult": 1.0, "ad_mult": 1.0, "skill_mult": 1.0, "star_mult": [1.0, 1.0, 1.0]},
        }
        heroes.append(hero)

    traits = {
        "origins": [
            {"key": o[0], "name_ko": o[1], "name_en": o[2], "desc": o[3], "synergy_desc": o[4],
             "thresholds": ORIGIN_THRESHOLDS, "effects": ORIGIN_EFFECTS[o[0]]} for o in ORIGINS
        ],
        "classes": [
            {"key": c[0], "name_ko": c[1], "name_en": c[2], "desc": c[3], "synergy_desc": c[4],
             "thresholds": CLASS_THRESHOLDS, "effects": CLASS_EFFECTS[c[0]]} for c in CLASSES
        ],
        "archetypes": ARCHETYPES,
        "class_base": {k: dict(hp=v["hp"], ad=v["ad"], attack_speed=v["as_"], armor=v["armor"], mr=v["mr"],
                               range=v["range"], mana_start=v["mana"][0], mana_max=v["mana"][1])
                       for k, v in CLASS_BASE.items()},
        "tier_mult": TIER_MULT, "tier_def_add": TIER_DEF_ADD,
        "star_scaling": {"hp": STAR_HP, "ad": STAR_AD},
    }

    player = dict(PLAYER_UNIT)
    player["stats"] = build_stats(player["class"], player["tier"], {"hp": 1.05, "ad": 1.05, "as": 1.0})
    player["skill"] = {"name": player.pop("skill_name"), "archetype": player.pop("archetype"),
                       "desc": player.pop("skill_desc"), "params": scaled_params("burst_ad", 3)}
    player["star_scaling"] = {"hp": STAR_HP, "ad": STAR_AD}
    player["archetype_power"] = ARCHETYPE_POWER.get("burst_ad", [1.0, 1.0, 1.0])
    player["balance"] = {"hp_mult": 1.0, "ad_mult": 1.0, "skill_mult": 1.0, "star_mult": [1.0, 1.0, 1.0]}

    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, "heroes.json"), "w", encoding="utf-8") as f:
        json.dump({"version": 1, "count": len(heroes), "player_unit": player, "heroes": heroes}, f, ensure_ascii=False, indent=1)
    with open(os.path.join(OUT, "traits.json"), "w", encoding="utf-8") as f:
        json.dump(traits, f, ensure_ascii=False, indent=1)
    print(f"heroes: {len(heroes)}, origins: {len(ORIGINS)}, classes: {len(CLASSES)}")


if __name__ == "__main__":
    main()
