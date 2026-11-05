# -*- coding: utf-8 -*-
"""
전투 레코드(battles.json) → 시뮬레이션 시나리오(아군/적/규칙) 생성. validate_battles · tune_bosses · run_context_items 공용.
전투 유형별 특수 규칙을 엔진 rules로 매핑:
  siege: 적 측 구조물 '성벽'(체력 ×6, 화살비 오라) / guard: 아군 측 구조물(must_survive) / escort: 아군 호위 대상(must_survive, 비공격)
  defense·survival·expedition·arena: 웨이브 / assassination: 지휘관 처치 시 승리 / escape: 30초 생존 / rescue: 아군 1명 속박(간수 처치 시 해방)
  invasion·suppression: 유닛 수 조정은 생성 단계에서 반영됨 / raid·hunt·decisive·bounty: 보스 체력 배수
"""
import random

STAR_GAIN = {1: 1.0, 2: 1.8 * 1.5, 3: 3.24 * 2.25}


def expected_team(d, level, size, rng, star_override=None):
    """레벨에 맞는 기대 팀: 계층 = 1 + level//22, 성급 = 1(<35) / 2(<75) / 3(≥75, 절반은 2). 역할 혼합."""
    tier = max(1, min(5, 1 + level // 22))
    pool = [h for h in d.heroes.values() if h["tier"] in (tier, max(1, tier - 1))]
    roles = ["knight", "guardian", "warrior", "duelist", "ranger", "mage", "priest", "assassin", "artillerist", "bard"]
    team = []
    for i, r in enumerate(roles[:size]):
        cands = [h for h in pool if h["class"] == r and h["id"] not in team]
        team.append(rng.choice(cands)["id"])
    specs = []
    for i, h in enumerate(team):
        if star_override: star = star_override
        elif level < 35: star = 1
        elif level < 75: star = 2
        else: star = 3 if i % 2 == 0 else 2
        specs.append(d.hero_spec(h, star))
    return specs


def enemy_power(level, diff, curve):
    bands = curve.get("bands", {}) if curve else {}
    lo = (level - 1) // 10 * 10 + 1
    band = f"{lo}-{lo+9}"
    if isinstance(bands.get(diff), dict):
        return bands[diff].get(band, 1.0)
    return 1.0


def structure_spec(name, hp, armor=30, mr=30, state=None):
    return {"id": "STRUCT", "name": name, "origin": "structure", "class": "structure", "tier": 1, "star": 1, "hp": hp, "ad": 0, "attack_speed": 0.1,
            "armor": armor, "mr": mr, "range": 1, "mana_start": 0, "mana_max": 10**9, "crit_chance": 0, "crit_damage": 100, "ap": 100,
            "skill": None, "skill_mult": 1.0, "items": [], "is_structure": True, "no_attack": True, "state": state or {}}


def build_enemies(d, b, diff, curve=None, boss_hp_override=None):
    dd = b["difficulties"][diff]
    star = dd["enemy_star"]; pm = dd["enemy_power_mult"]
    residual = max(0.75, min(1.6, (pm / (STAR_GAIN[star] / STAR_GAIN[b["difficulties"]["normal"]["enemy_star"]])) ** 0.5))
    residual *= enemy_power(b["level"], diff, curve)
    residual *= dd.get("tuned_power_mult", 1.0)
    units = []
    for u in b["enemy"]["units"]:
        units.append(d.monster_spec(u["unit"], star=star, tier_override=u["tier"], power_mult=residual))
    boss = None
    if b["enemy"]["boss"]:
        bs = b["enemy"]["boss"]
        boss = d.monster_spec(bs["unit"], star=star, tier_override=bs["tier"], hp_mult=(boss_hp_override or bs["hp_mult"]), power_mult=residual)
        boss["name"] = bs["name_ko"]
        if b["type"] == "assassination": boss["state"] = {"commander": True}
        if b["type"] == "rescue": boss["state"] = {"jailer": True}
        units.append(boss)
    return units[:12]


def build_scenario(d, b, diff, rng, curve=None, allies=None, boss_hp_override=None):
    """반환: allies, enemies, rules"""
    btype = b["type"]
    mode = b["participation"]["mode"]
    want = {"solo": 1, "squad": 4, "team": 6, "free": 6, "army": (10 if b["level"] >= 70 else 8)}[mode]
    size = max(b["participation"]["min"], min(b["participation"]["max"], want))
    if allies is None:
        if b["participation"]["mode"] == "solo":
            tier = max(1, min(5, 1 + b["level"] // 22))
            cands = [h["id"] for h in d.heroes.values() if h["tier"] == tier and h["class"] in ("duelist", "warrior", "knight")]
            allies = [d.hero_spec(rng.choice(cands), 1 if b["level"] < 35 else (2 if b["level"] < 75 else 3))]
        else:
            allies = expected_team(d, b["level"], size, rng)
    enemies = build_enemies(d, b, diff, curve, boss_hp_override)
    rules = {}
    waves = b["enemy"].get("waves", 1)
    if waves > 1:
        # 웨이브 2..N: 같은 편성을 성급/전력 그대로 재생성 (생존 웨이브는 점증)
        extra = []
        for w in range(2, waves + 1):
            grow = 1.0 + (0.12 * (w - 1) if btype == "survival" else 0.0)
            ws = build_enemies(d, b, diff, curve, boss_hp_override)
            for u in ws:
                u = dict(u); u["hp"] *= grow; u["ad"] *= grow
                extra.append(u)
            rules.setdefault("waves", []).append(extra); extra = []
    ally_hp = sum(a["hp"] for a in allies) / max(1, len(allies))
    for st in b["enemy"].get("structures", []):
        if st["side"] == "enemy":
            enemies.append(structure_spec(st["name_ko"], ally_hp * st["hp_mult"] * 1.5, state={"priority": True, "arrow_aura_pct": 0.8}))
        else:
            spec = structure_spec(st["name_ko"], ally_hp * st["hp_mult"], state={"must_survive": True, "escort_priority": bool(st.get("mobile"))})
            allies = list(allies) + [spec]
    if btype == "assassination": rules["assassination"] = True
    if btype == "escape": rules["escape"] = True
    if btype == "rescue" and allies:
        allies = [dict(a) for a in allies]
        allies[-1]["state"] = dict(allies[-1].get("state", {}), captive=True)
        if not any(e.get("state", {}).get("jailer") for e in enemies):
            # 보스가 없는 구출 전투: 가장 강한(계층 높은) 적 유닛이 간수. 간수 처치 시 속박 해제 (없으면 포로가 영원히 묶여 사실상 1인 결손이 된다)
            enemies = [dict(e) for e in enemies]
            j = max(range(len(enemies)), key=lambda i: (enemies[i]["tier"], enemies[i]["hp"]))
            enemies[j]["state"] = dict(enemies[j].get("state", {}), jailer=True)
    return allies, enemies, rules
