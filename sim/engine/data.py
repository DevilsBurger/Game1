# -*- coding: utf-8 -*-
"""데이터 로딩 및 유닛 스펙 생성 (영웅/몬스터/소환수)."""
import json, os

ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
DATA = os.path.join(ROOT, "data")


class GameData:
    def __init__(self, heroes=None, items=None, traits=None, battles=None):
        self.heroes_doc = heroes or json.load(open(os.path.join(DATA, "heroes.json"), encoding="utf-8"))
        self.items_doc = items or json.load(open(os.path.join(DATA, "items.json"), encoding="utf-8"))
        self.traits = traits or json.load(open(os.path.join(DATA, "traits.json"), encoding="utf-8"))
        self.heroes = {h["id"]: h for h in self.heroes_doc["heroes"]}
        self.player = self.heroes_doc.get("player_unit")
        self.items = {i["id"]: i for i in self.items_doc["items"]}
        self.origins = {o["key"]: o for o in self.traits["origins"]}
        self.classes = {c["key"]: c for c in self.traits["classes"]}
        self.archetypes = self.traits["archetypes"]
        self.class_base = self.traits["class_base"]
        self.tier_mult = {int(k): v for k, v in self.traits["tier_mult"].items()}
        self.tier_def_add = {int(k): v for k, v in self.traits["tier_def_add"].items()}
        self.monsters = None
        if battles is not None:
            self.monsters = {m["key"]: m for m in battles["monsters"]}

    def hero_spec(self, hero_id, star=1, items=None):
        h = self.heroes[hero_id] if hero_id in self.heroes else self.player
        b = h.get("balance", {})
        s = h["stats"]
        sm = b.get("star_mult", [1.0, 1.0, 1.0])[star - 1]
        hp_m, ad_m, sk_m = b.get("hp_mult", 1.0) * sm, b.get("ad_mult", 1.0) * sm, b.get("skill_mult", 1.0) * sm
        sh, sa = h["star_scaling"]["hp"][star - 1], h["star_scaling"]["ad"][star - 1]
        return {
            "id": h["id"], "name": h["name_ko"], "origin": h["origin"], "class": h["class"], "tier": h["tier"], "star": star,
            "hp": s["hp"] * hp_m * sh, "ad": s["ad"] * ad_m * sa, "attack_speed": s["attack_speed"], "armor": s["armor"], "mr": s["mr"],
            "range": s["range"], "mana_start": s["mana_start"], "mana_max": s["mana_max"], "crit_chance": s["crit_chance"],
            "crit_damage": s["crit_damage"], "ap": s["ap"], "skill": h["skill"], "skill_mult": sk_m,
            "items": [self.items[i] if isinstance(i, str) else i for i in (items or [])],
        }

    def monster_spec(self, key, star=1, tier_override=None, hp_mult=1.0, power_mult=1.0):
        """몬스터: 직업 템플릿 + 계층 + 기본 스킬 원형(직업별 기본)."""
        m = self.monsters[key]
        cls = m["class"]; tier = tier_override or m["tier"]
        cb = self.class_base[cls]; tm = self.tier_mult[tier]
        sh, sa = [1.0, 1.8, 3.24][star - 1], [1.0, 1.5, 2.25][star - 1]
        arche = DEFAULT_ARCHE[cls]
        params = dict(self.archetypes[arche])
        for k in ("dmg", "heal", "shield", "flat", "bonus_flat"):
            if k in params and isinstance(params[k], list):
                params[k] = [round(x * tm) for x in params[k]]
        return {
            "id": key, "name": m["name_ko"], "origin": "monster", "class": cls, "tier": tier, "star": star,
            "hp": cb["hp"] * tm * sh * hp_mult * power_mult, "ad": cb["ad"] * tm * sa * power_mult, "attack_speed": cb["attack_speed"],
            "armor": cb["armor"] + self.tier_def_add[tier], "mr": cb["mr"] + self.tier_def_add[tier], "range": cb["range"],
            "mana_start": cb["mana_start"], "mana_max": cb["mana_max"], "crit_chance": 25, "crit_damage": 140, "ap": 100 * power_mult,
            "skill": {"name": arche, "archetype": arche, "params": params}, "skill_mult": 1.0, "items": [],
        }


DEFAULT_ARCHE = {
    "knight": "taunt_shield", "warrior": "aoe_self", "assassin": "dash_strike", "ranger": "multishot", "mage": "burst_st", "priest": "heal_lowest",
    "guardian": "shield_allies", "duelist": "buff_as_self", "summoner": "summon", "artillerist": "aoe_target_ad", "shaman": "armor_shred",
    "bard": "buff_ad_allies", "dragoon": "dash_aoe", "engineer": "turret",
}
