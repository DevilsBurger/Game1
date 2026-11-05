# -*- coding: utf-8 -*-
"""
JSON Schema(draft 2020-12) 생성 + 데이터 검증.
출력: schemas/{heroes,items,traits,nations,battles,quests,economy,prompts}.schema.json
검증: python tools/gen_schemas.py --validate  (jsonschema 패키지가 있으면 전체 검증, 없으면 내장 간이 검증)
C# DTO 생성기(gen_csharp.py)는 이 스키마를 입력으로 쓴다.
"""
import json, os, sys

ROOT = os.path.join(os.path.dirname(__file__), "..")
DATA = os.path.join(ROOT, "data")
OUT = os.path.join(ROOT, "schemas")
os.makedirs(OUT, exist_ok=True)

ORIGINS = ["astel", "valheim", "sairam", "karna", "lies", "elowen", "grandur", "neos", "nox", "celestia", "dragonkin", "torga", "lumen", "freelancer"]
CLASSES = ["knight", "warrior", "assassin", "ranger", "mage", "priest", "guardian", "duelist", "summoner", "artillerist", "shaman", "bard", "dragoon", "engineer"]
ARCHETYPES = ["burst_st", "burst_ad", "burst_ad_long", "aoe_target", "aoe_target_ad", "aoe_self", "aoe_line", "aoe_line_ad", "chain", "chain_ad", "heal_lowest", "heal_aoe",
              "shield_self", "shield_allies", "taunt_shield", "buff_as_self", "buff_as_allies", "buff_ad_allies", "buff_ap_allies", "stun_st", "stun_aoe", "dot_target", "armor_shred",
              "lifesteal_strike", "execute", "execute_long", "multishot", "dash_strike", "dash_aoe", "summon", "summon_big", "summon_multi", "turret", "turret_big"]
ITEM_CATEGORIES = ["component", "completed", "emblem", "radiant", "artifact", "support", "national", "consumable", "material"]
STAT_KEYS = ["ad_pct", "ap", "hp", "armor", "mr", "as_pct", "mana", "crit", "omnivamp", "durability"]
HOOK_TYPES = ["stack_ad_on_kill", "giant_slayer", "low_hp_shield", "shred_on_hit", "omnivamp_bonus", "aoe_on_attack", "mana_on_attack", "crit_dmg_bonus", "heal_on_kill", "start_shield",
              "burn_on_hit", "shield_on_cast", "as_stack_on_attack", "mana_refund_on_cast", "spell_crit", "burn_aura", "as_slow_aura", "stack_on_hit", "heal_allies_timer", "thorns", "gargoyle",
              "shred_on_crit", "magic_dr", "shock_every_n", "cast_mana_allies", "cc_immune", "extra_range", "ap_stack_timer", "hand_of_justice", "mana_on_kill", "mana_regen", "random_items",
              "shield_on_crit", "overheal_shield", "revive", "heal_on_revive_allies", "aura_allies", "aura_enemies", "regen", "kill_explode", "execute_low", "dodge", "true_dmg_on_cast",
              "heal_on_cast_allies", "summon_on_kill", "summon_on_cast", "first_cast_bonus", "slow_on_cast", "stasis_low_hp", "backline_jump", "dash_dmg_bonus", "turret_stat_bonus",
              "as_pct_penalty", "grant_trait", "double_trait_count", "team_slot", "gold_bonus", "drop_bonus", "hero_drop_bonus"]
BATTLE_TYPES = ["skirmish", "siege", "defense", "escort", "hunt", "duel", "ambush", "expedition", "bounty", "invasion", "survival", "encounter", "trial", "raid", "rescue", "assassination",
                "strike", "suppression", "monster_hunt", "decisive", "arena", "escape", "recon", "guard"]
BATTLE_KINDS = ["story", "regional", "encounter", "quest"]
PARTICIPATION = ["solo", "squad", "team", "army", "free"]
DIFFS = ["normal", "hard", "nightmare"]
QUEST_KINDS = ["story", "hero_chain", "origin_pact", "class_trial"]

S = "https://json-schema.org/draft/2020-12/schema"
num = {"type": "number"}; integer = {"type": "integer"}; string = {"type": "string"}; boolean = {"type": "boolean"}
def arr(items, **kw): return {"type": "array", "items": items, **kw}
def obj(props, required=None, additional=True): return {"type": "object", "properties": props, "required": required or [], "additionalProperties": additional}
def enum(vals): return {"type": "string", "enum": vals}
def num3(): return arr(num, minItems=3, maxItems=3)

balance = obj({"hp_mult": num, "ad_mult": num, "skill_mult": num, "star_mult": num3()}, ["hp_mult", "ad_mult", "skill_mult"])
stats = obj({"hp": num, "ad": num, "attack_speed": num, "armor": num, "mr": num, "range": integer, "mana_start": num, "mana_max": num, "crit_chance": num, "crit_damage": num, "ap": num},
            ["hp", "ad", "attack_speed", "armor", "mr", "range", "mana_start", "mana_max", "crit_chance", "crit_damage", "ap"], additional=False)
skill = obj({"name": string, "archetype": enum(ARCHETYPES), "desc": string, "params": obj({"kind": enum(["damage", "heal", "shield", "buff", "dot", "empower", "summon", "turret"])}, ["kind"])},
            ["name", "archetype", "params"])
hero = obj({"id": {"type": "string", "pattern": "^(H[0-9]{3}|P000)$"}, "name_ko": string, "name_en": string, "title": string, "origin": enum(ORIGINS), "class": enum(CLASSES),
            "tier": {"type": "integer", "minimum": 1, "maximum": 5}, "rarity": string, "stats": stats, "star_scaling": obj({"hp": num3(), "ad": num3()}, ["hp", "ad"]),
            "skill": skill, "archetype_power": num3(), "lore": string, "balance": balance},
           ["id", "name_ko", "origin", "class", "tier", "stats", "star_scaling", "skill", "balance"])
SCHEMAS = {
    "heroes": {"$schema": S, "$id": "arken/heroes", "title": "Heroes", **obj({"version": integer, "count": integer, "player_unit": hero, "heroes": arr(hero, minItems=196, maxItems=196)}, ["version", "count", "heroes"])},
    "items": {"$schema": S, "$id": "arken/items", "title": "Items", **obj({"version": integer, "count": integer, "by_category": obj({}), "prices": obj({}), "items": arr(obj({
        "id": {"type": "string", "pattern": "^[CIERASNXM][0-9]{2,3}$"}, "name_ko": string, "name_en": string, "category": enum(ITEM_CATEGORIES),
        "stats": obj({k: num for k in STAT_KEYS}, additional=False), "hooks": arr(obj({"type": enum(HOOK_TYPES), "params": obj({})}, ["type", "params"])),
        "desc": string, "price_gold": {"type": ["integer", "null"]}, "price_gem": integer, "recipe": {"type": ["array", "null"], "items": string}, "base_item": string, "nation": string,
        "kind": string, "effect": obj({}), "grade": string, "balance": obj({"mult": num, "flag": string}, ["mult"])},
        ["id", "name_ko", "name_en", "category", "stats", "hooks", "desc"]))}, ["version", "count", "items"])},
    "traits": {"$schema": S, "$id": "arken/traits", "title": "Traits", **obj({
        "origins": arr(obj({"key": enum(ORIGINS), "name_ko": string, "name_en": string, "desc": string, "synergy_desc": string, "thresholds": arr(integer), "effects": obj({"hook": string}, ["hook"]), "balance": obj({"mult": arr(num)})}, ["key", "name_ko", "thresholds", "effects"]), minItems=14, maxItems=14),
        "classes": arr(obj({"key": enum(CLASSES), "name_ko": string, "name_en": string, "desc": string, "synergy_desc": string, "thresholds": arr(integer), "effects": obj({"hook": string}, ["hook"]), "balance": obj({"mult": arr(num)})}, ["key", "name_ko", "thresholds", "effects"]), minItems=14, maxItems=14),
        "archetypes": obj({}), "class_base": obj({}), "tier_mult": obj({}), "tier_def_add": obj({}), "star_scaling": obj({})}, ["origins", "classes", "archetypes", "class_base", "tier_mult"])},
    "nations": {"$schema": S, "$id": "arken/nations", "title": "Nations", **obj({"version": integer, "count": integer, "nations": arr(obj({
        "key": string, "name_ko": string, "name_en": string, "region_group": string, "category": string, "civilization": string, "danger": {"type": "integer", "minimum": 1, "maximum": 10},
        "capital": string, "ruler": string, "desc": string, "native_origin": enum(ORIGINS), "native_origin_ko": string, "act": {"type": "integer", "minimum": 1, "maximum": 5},
        "regions": arr(string, minItems=5, maxItems=5), "enemy_factions": arr(string), "battle_count": integer, "national_item": {"type": ["string", "null"]}},
        ["key", "name_ko", "danger", "native_origin", "act", "regions", "enemy_factions"]), minItems=24, maxItems=24)}, ["nations"])},
    "battles": {"$schema": S, "$id": "arken/battles", "title": "Battles", **obj({"version": integer, "count": integer, "by_kind": obj({}), "by_type": obj({}), "battle_types": arr(obj({})), "participation": obj({}),
        "difficulties": arr(obj({})), "monsters": arr(obj({"key": string, "name_ko": string, "class": enum(CLASSES), "tier": integer, "tag": string}, ["key", "name_ko", "class", "tier"])),
        "battles": arr(obj({
            "id": string, "name_ko": string, "kind": enum(BATTLE_KINDS), "nation": string, "nation_ko": string, "region": string, "type": enum(BATTLE_TYPES), "type_ko": string,
            "level": {"type": "integer", "minimum": 1, "maximum": 100}, "act": integer,
            "participation": obj({"name": string, "min": integer, "max": integer, "mode": enum(PARTICIPATION), "constraints": arr(string)}, ["min", "max", "mode"]),
            "enemy": obj({"units": arr(obj({"unit": string, "name_ko": string, "class": enum(CLASSES), "tier": integer}, ["unit", "tier"])), "boss": {"type": ["object", "null"]}, "waves": integer, "structures": arr(obj({})), "factions": arr(string), "hero_enemy": obj({})}, ["units", "waves"]),
            "difficulties": obj({d: obj({"name_ko": string, "enemy_power_mult": num, "enemy_star": integer, "stamina_per_hero": integer, "tuned_power_mult": num, "power_cliff": num,
                                         "rewards": obj({"gold": integer, "exp": integer, "items": arr(obj({})), "materials": obj({}), "hero_drop": obj({})}, ["gold", "exp", "items", "materials"])},
                                        ["enemy_power_mult", "enemy_star", "stamina_per_hero", "rewards"]) for d in DIFFS} | {"first_clear_bonus": obj({})}, DIFFS),
            "flavor": string, "special_rule": string, "unlock_after": {"type": ["string", "null"]}, "hero_id": string, "quest_id": string, "step": integer, "clear_condition": obj({})},
            ["id", "name_ko", "kind", "nation", "type", "level", "act", "participation", "enemy", "difficulties"]), minItems=1000)}, ["count", "monsters", "battles"])},
    "quests": {"$schema": S, "$id": "arken/quests", "title": "Quests", **obj({"version": integer, "count": integer, "by_kind": obj({}), "quests": arr(obj({
        "id": string, "kind": enum(QUEST_KINDS), "name_ko": string, "hero_id": string, "steps": arr(obj({"battle_id": string, "condition": {"type": ["object", "null"]}}, ["battle_id"])),
        "unlock": obj({}), "reward": obj({"hero_guaranteed": string, "gold": integer, "gems": integer, "items": arr(obj({}))}), "desc": string}, ["id", "kind", "name_ko", "steps", "reward"]))}, ["count", "quests"])},
    "economy": {"$schema": S, "$id": "arken/economy", "title": "Economy", **obj({
        "gold_base": obj({"const": num, "per_level": num}, ["const", "per_level"]), "exp_per_level": num,
        "stamina": obj({"hero_max": integer, "regen_minutes_per_point": num, "player_max": integer, "cost_per_hero": obj({d: integer for d in DIFFS}, DIFFS), "multi_wave_mult": num, "multi_wave_types": arr(string)}, ["hero_max", "cost_per_hero"]),
        "team_size_by_player_level": obj({}), "player_level_exp": obj({}), "star_up_cost": obj({"1_to_2": obj({}), "2_to_3": obj({})}, ["1_to_2", "2_to_3"]),
        "hero_value_gold_equiv": obj({}), "hero_drop_base_pct": obj({}), "hero_drop_difficulty_mult": obj({}), "hero_drop_cap_pct": num, "duplicate_hero_conversion": obj({}),
        "affinity_pity": obj({}), "regional_native_hero_drop_pct": obj({}), "item_drop": obj({}), "material_drop": obj({}), "premium_currency": obj({}),
        "enemy_power_curve": obj({"bands": obj({d: obj({}) for d in DIFFS}, DIFFS)}, ["bands"])},
        ["gold_base", "stamina", "team_size_by_player_level", "star_up_cost", "hero_drop_base_pct", "item_drop", "material_drop"])},
}


def write():
    for name, sc in SCHEMAS.items():
        json.dump(sc, open(os.path.join(OUT, f"{name}.schema.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    enums = {"origins": ORIGINS, "classes": CLASSES, "archetypes": ARCHETYPES, "item_categories": ITEM_CATEGORIES, "stat_keys": STAT_KEYS, "hook_types": HOOK_TYPES,
             "battle_types": BATTLE_TYPES, "battle_kinds": BATTLE_KINDS, "participation": PARTICIPATION, "difficulties": DIFFS, "quest_kinds": QUEST_KINDS,
             "battle_events": ["spawn", "move", "attack", "cast", "damage", "heal", "death", "revive", "stun", "wave", "end"],
             "quest_conditions": ["difficulty>=hard", "no_death", "time<=25", "team_size<=4", "max_star:2", "max_tier:3", "origin_count:{origin}:N", "class_count:{class}:N", "class_only:{class}", "origin_only:{origin}", "no_duplicate_class"]}
    json.dump(enums, open(os.path.join(OUT, "enums.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("schemas written:", ", ".join(SCHEMAS))


def validate():
    try:
        import jsonschema
    except ImportError:
        jsonschema = None
    ok = True
    for name, sc in SCHEMAS.items():
        doc = json.load(open(os.path.join(DATA, f"{name}.json"), encoding="utf-8"))
        if jsonschema:
            v = jsonschema.Draft202012Validator(sc)
            errs = sorted(v.iter_errors(doc), key=lambda e: list(e.path))
            if errs:
                ok = False
                print(f"[{name}] {len(errs)} errors; first: {list(errs[0].path)} {errs[0].message[:160]}")
            else:
                print(f"[{name}] ok")
        else:
            print(f"[{name}] loaded (jsonschema 미설치: 구조 검증 생략)")
    # 참조 무결성 (스키마 외)
    heroes = {h["id"] for h in json.load(open(os.path.join(DATA, "heroes.json"), encoding="utf-8"))["heroes"]}
    items = {i["id"] for i in json.load(open(os.path.join(DATA, "items.json"), encoding="utf-8"))["items"]}
    bdoc = json.load(open(os.path.join(DATA, "battles.json"), encoding="utf-8"))
    mons = {m["key"] for m in bdoc["monsters"]}; bids = {b["id"] for b in bdoc["battles"]}
    nations = {n["key"] for n in json.load(open(os.path.join(DATA, "nations.json"), encoding="utf-8"))["nations"]}
    bad = 0
    for b in bdoc["battles"]:
        if b["nation"] not in nations: bad += 1
        for u in b["enemy"]["units"]:
            if u["unit"] not in mons: bad += 1
        if b.get("hero_id") and b["hero_id"] not in heroes: bad += 1
        if b.get("unlock_after") and b["unlock_after"] not in bids: bad += 1
    for q in json.load(open(os.path.join(DATA, "quests.json"), encoding="utf-8"))["quests"]:
        for s in q["steps"]:
            if s["battle_id"] not in bids: bad += 1
        if q["reward"].get("hero_guaranteed") and q["reward"]["hero_guaranteed"] not in heroes: bad += 1
    for i in json.load(open(os.path.join(DATA, "items.json"), encoding="utf-8"))["items"]:
        for r in (i.get("recipe") or []):
            if r not in items: bad += 1
    print("reference integrity errors:", bad)
    return ok and bad == 0


if __name__ == "__main__":
    write()
    if "--validate" in sys.argv:
        sys.exit(0 if validate() else 1)
