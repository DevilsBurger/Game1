# -*- coding: utf-8 -*-
"""공용 훅 헬퍼 (아이템·특성 공용)."""


def summon_spec_from(owner, hp_pct, ad_pct, name="소환수", lifetime=12.0, is_turret=False, rng_range=None, t=0.0):
    return {
        "id": owner.hid + "_s", "name": name, "origin": "summon", "class": "summon", "tier": owner.tier, "star": owner.star,
        "hp": owner.max_hp * hp_pct / 100.0, "ad": owner.e_ad * ad_pct / 100.0, "attack_speed": 0.8 if not is_turret else 0.9,
        "armor": owner.e_armor * 0.6, "mr": owner.e_mr * 0.6, "range": (rng_range if rng_range is not None else (4 if is_turret else 1)),
        "mana_start": 0, "mana_max": 10**9, "crit_chance": 25, "crit_damage": 140, "ap": 100, "skill": None, "skill_mult": 1.0, "items": [],
        "is_summon": not is_turret, "is_turret": is_turret, "lifetime_until": t + lifetime,
    }
