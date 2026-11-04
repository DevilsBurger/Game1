# -*- coding: utf-8 -*-
"""
아이템 JSON 생성기 (TFT 방식: 기본 재료 2개 조합 → 완성 아이템).
출력: data/items.json

분류:
  component   기본 재료 12 (능력치 10 + 용의 비늘 + 영웅의 문장)
  completed   조합 아이템 55 (능력치 재료 10C2 + 동일 재료 10)
  emblem      상징 20 (용의 비늘/영웅의 문장 + 능력치 재료) + 특수 3 + 비조합 상징 8
  radiant     빛나는 아이템 55 (조합 아이템의 강화판)
  artifact    유물 60 (고유 효과, 조합 불가, 로비 구매/전투 보상)
  support     지원 아이템 30 (아군 전체/인접 오라 효과)
  national    국가 특산품 24 (국가별 1개)
  consumable  소모품 (스태미너·드랍률·호감도 등, BM 연계)
  material    승급 재료 3 (모든 영웅 공통)
모든 아이템은 로비에서 골드로 구매 가능(소모품 일부는 보석).
"""
import json, os, sys, itertools
sys.path.insert(0, os.path.dirname(__file__))
from world_data import NATIONS
from roster_data import ORIGINS, CLASSES

OUT = os.path.join(os.path.dirname(__file__), "..", "data")

# ── 능력치 재료 (id, 한글, 영문, stat, value, 설명)
COMPONENTS = [
    ("C01", "강철검", "Steel Sword", "ad_pct", 10, "공격력 +10%"),
    ("C02", "마력의 지팡이", "Arcane Rod", "ap", 10, "주문력 +10"),
    ("C03", "거인의 허리띠", "Giant's Belt", "hp", 150, "체력 +150"),
    ("C04", "쇠사슬 갑옷", "Chain Vest", "armor", 20, "방어력 +20"),
    ("C05", "정령의 망토", "Spirit Cloak", "mr", 20, "마법 저항력 +20"),
    ("C06", "질풍의 활", "Gale Bow", "as_pct", 10, "공격 속도 +10%"),
    ("C07", "수정 눈물", "Crystal Tear", "mana", 15, "마나 +15"),
    ("C08", "행운의 장갑", "Lucky Gloves", "crit", 20, "치명타 확률 +20%"),
    ("C09", "흡혈 송곳니", "Vampire Fang", "omnivamp", 8, "피해 흡혈 +8%"),
    ("C10", "별의 파편", "Star Fragment", "durability", 6, "내구력(받는 피해 감소) +6%"),
]
SPECIAL_COMPONENTS = [
    ("C11", "용의 비늘", "Dragon Scale", "none", 0, "능력치 재료와 조합하면 출신 상징이 된다."),
    ("C12", "영웅의 문장", "Hero Crest", "none", 0, "능력치 재료와 조합하면 직업 상징이 된다."),
]

# ── 조합표: (i, j) → (한글명, 영문명, 추가 능력치 dict, 훅 리스트, 설명)
# 훅: (type, params) — 시뮬레이터가 구현. 이해를 돕기 위해 설명에 수치 포함.
COMBOS = {
    (1, 1): ("피의 쌍검", "Twin Bloodblades", {"ad_pct": 10}, [("stack_ad_on_kill", {"pct": 6, "max": 5})], "공격력 +20%. 적 처치 시 공격력 +6% (최대 5중첩)."),
    (1, 2): ("용살자의 장검", "Dragonslayer Sword", {}, [("giant_slayer", {"hp_threshold": 1800, "bonus_pct": 25})], "최대 체력 1800 이상의 적에게 주는 피해 +25%."),
    (1, 3): ("용맹의 맹세", "Oath of Valor", {}, [("low_hp_shield", {"threshold": 60, "shield_pct": 30, "ad_pct": 25, "duration": 6})], "체력이 60% 이하가 되면 최대 체력 30%의 방어막과 공격력 +25%를 6초간 얻는다."),
    (1, 4): ("약탈자의 발톱", "Raider's Claw", {}, [("shred_on_hit", {"pct": 30, "duration": 3})], "공격 적중 시 대상 방어력 30% 감소(3초)."),
    (1, 5): ("흡혈의 장검", "Bloodthirster", {}, [("omnivamp_bonus", {"pct": 18})], "피해 흡혈 +18%."),
    (1, 6): ("쌍둥이 폭풍", "Twin Tempest", {}, [("aoe_on_attack", {"targets": 1, "ad_ratio": 0.45})], "공격 시 가장 가까운 다른 적 1명에게 공격력 45%의 추가 피해."),
    (1, 7): ("창술사의 창", "Spear of Shojin", {}, [("mana_on_attack", {"mana": 5})], "공격 시 마나 +5."),
    (1, 8): ("무한의 대검", "Infinity Edge", {}, [("crit_dmg_bonus", {"pct": 30})], "치명타 피해 +30%."),
    (1, 9): ("핏빛 사냥칼", "Crimson Hunter", {}, [("heal_on_kill", {"pct": 15})], "적 처치 시 최대 체력의 15% 회복."),
    (1, 10): ("맹세의 검", "Sworn Blade", {}, [("start_shield", {"pct": 20, "duration": 8})], "전투 시작 시 최대 체력 20%의 방어막(8초)."),
    (2, 2): ("대마법사의 모자", "Archmage's Hat", {"ap": 30}, [], "주문력 +50."),
    (2, 3): ("역병의 서", "Tome of Plague", {}, [("burn_on_hit", {"pct_per_sec": 1.0, "duration": 6, "grievous": 33})], "피해를 준 적에게 6초간 매초 최대 체력 1% 화상 + 치유 감소 33%."),
    (2, 4): ("수정 갑옷", "Crystal Armor", {}, [("shield_on_cast", {"pct": 12, "duration": 4})], "스킬 사용 시 최대 체력 12%의 방어막(4초)."),
    (2, 5): ("지식의 서", "Tome of Knowledge", {}, [("omnivamp_bonus", {"pct": 12})], "피해 흡혈 +12%."),
    (2, 6): ("격노의 지팡이", "Rageblade Staff", {}, [("as_stack_on_attack", {"pct": 5, "max": 12})], "공격마다 공격 속도 +5% (최대 12중첩)."),
    (2, 7): ("푸른 축복", "Blue Blessing", {}, [("mana_refund_on_cast", {"mana": 20})], "스킬 사용 후 마나 +20."),
    (2, 8): ("보석 장갑", "Jeweled Gauntlet", {}, [("spell_crit", {})], "스킬이 치명타를 입힐 수 있다."),
    (2, 9): ("핏빛 마도서", "Crimson Grimoire", {}, [("omnivamp_bonus", {"pct": 12})], "피해 흡혈 +12%(스킬 포함)."),
    (2, 10): ("별의 지팡이", "Star Staff", {}, [("shield_on_cast", {"pct": 10, "duration": 4})], "스킬 사용 시 최대 체력 10%의 방어막."),
    (3, 3): ("전사의 흉갑", "Warmog's Plate", {"hp": 400}, [], "체력 +700."),
    (3, 4): ("태양불꽃 망토", "Sunfire Cape", {}, [("burn_aura", {"radius": 2, "pct_per_sec": 1.0, "grievous": 33})], "주변 2칸 적에게 매초 최대 체력 1% 화상 + 치유 감소."),
    (3, 5): ("서리 망토", "Frost Cloak", {}, [("as_slow_aura", {"radius": 1, "pct": 25})], "인접 적의 공격 속도 -25%."),
    (3, 6): ("거인의 결의", "Titan's Resolve", {}, [("stack_on_hit", {"ad_pct": 1.5, "ap": 1.5, "max": 25, "max_bonus_def": 25})], "공격/피격마다 공격력·주문력 +1.5% (최대 25). 최대 중첩 시 방어력·마저 +25."),
    (3, 7): ("구원", "Redemption", {}, [("heal_allies_timer", {"delay": 3, "radius": 1, "missing_pct": 18, "interval": 5})], "3초 후부터 5초마다 주변 1칸 아군의 잃은 체력 18% 회복."),
    (3, 8): ("용맹의 흉갑", "Valiant Plate", {}, [("crit_dmg_bonus", {"pct": 20})], "치명타 피해 +20%."),
    (3, 9): ("흡혈귀의 흉갑", "Vampiric Plate", {}, [("omnivamp_bonus", {"pct": 15})], "피해 흡혈 +15%."),
    (3, 10): ("불굴의 심장", "Unyielding Heart", {"durability": 4}, [], "내구력 +10%, 체력 +150."),
    (4, 4): ("가시 갑옷", "Bramble Vest", {"armor": 20}, [("thorns", {"pct": 10})], "방어력 +60. 받은 물리 피해의 10%를 반사."),
    (4, 5): ("가고일 돌갑옷", "Gargoyle Stoneplate", {}, [("gargoyle", {"per_enemy": 12})], "자신을 노리는 적 1명당 방어력·마저 +12."),
    (4, 6): ("질풍 갑옷", "Gale Armor", {}, [("stack_on_hit", {"armor": 2, "max": 20})], "공격마다 방어력 +2 (최대 20중첩)."),
    (4, 7): ("수호자의 맹세", "Protector's Vow", {}, [("low_hp_shield", {"threshold": 40, "shield_pct": 25, "def": 20, "duration": 5})], "체력 40% 이하 시 최대 체력 25% 방어막 + 방어력·마저 +20."),
    (4, 8): ("파쇄 장갑", "Shatter Gauntlet", {}, [("shred_on_crit", {"pct": 30, "duration": 3})], "치명타 시 대상 방어력 30% 감소."),
    (4, 9): ("피의 갑옷", "Blood Armor", {}, [("omnivamp_bonus", {"pct": 12})], "피해 흡혈 +12%."),
    (4, 10): ("강철 요새", "Iron Fortress", {"durability": 4}, [], "내구력 +10%, 방어력 +20."),
    (5, 5): ("용의 발톱", "Dragon's Claw", {"mr": 20}, [("magic_dr", {"pct": 20})], "마법 저항력 +60. 받는 마법 피해 -20%."),
    (5, 6): ("정전기 망토", "Static Cloak", {}, [("shock_every_n", {"n": 3, "targets": 3, "dmg": 60, "mr_shred": 30, "duration": 4})], "3번째 공격마다 적 3명에게 60 마법 피해 + 마저 30% 감소."),
    (5, 7): ("은총의 성배", "Chalice of Grace", {}, [("cast_mana_allies", {"radius": 1, "mana": 8})], "스킬 사용 시 인접 아군 마나 +8."),
    (5, 8): ("수은 망토", "Quicksilver Cloak", {"as_pct": 10}, [("cc_immune", {"duration": 15})], "전투 시작 후 15초간 군중 제어 면역. 공격 속도 +10%."),
    (5, 9): ("정령의 송곳니", "Spirit Fang", {}, [("omnivamp_bonus", {"pct": 12})], "피해 흡혈 +12%."),
    (5, 10): ("성역의 망토", "Sanctuary Cloak", {}, [("start_shield", {"pct": 18, "duration": 8})], "전투 시작 시 최대 체력 18% 방어막."),
    (6, 6): ("고속 연사포", "Rapid Firecannon", {"as_pct": 10}, [("extra_range", {"range": 1})], "공격 속도 +30%, 사거리 +1."),
    (6, 7): ("마나의 활", "Mana Bow", {}, [("mana_on_attack", {"mana": 3})], "공격 시 마나 +3."),
    (6, 8): ("최후의 속삭임", "Last Whisper", {}, [("shred_on_crit", {"pct": 30, "duration": 3})], "치명타 시 대상 방어력 30% 감소."),
    (6, 9): ("핏빛 활", "Crimson Bow", {}, [("omnivamp_bonus", {"pct": 12})], "피해 흡혈 +12%."),
    (6, 10): ("불굴의 활", "Unyielding Bow", {"durability": 4}, [], "내구력 +10%, 공격 속도 +10%."),
    (7, 7): ("대천사의 눈물", "Archangel's Tear", {}, [("ap_stack_timer", {"ap": 20, "interval": 5})], "5초마다 주문력 +20."),
    (7, 8): ("정의의 손길", "Hand of Justice", {}, [("hand_of_justice", {"dmg_pct": 15, "omnivamp": 15})], "주는 피해 +15%, 피해 흡혈 +15%."),
    (7, 9): ("영혼 수확자", "Soul Harvester", {}, [("mana_on_kill", {"mana": 20})], "적 처치 시 마나 +20."),
    (7, 10): ("명상의 보주", "Orb of Meditation", {}, [("mana_regen", {"per_sec": 2})], "매초 마나 +2."),
    (8, 8): ("도둑의 장갑", "Thief's Gloves", {"crit": 20}, [("random_items", {"count": 2})], "치명타 +40%. 전투마다 무작위 조합 아이템 2개의 능력치를 얻는다."),
    (8, 9): ("암살자의 송곳니", "Assassin's Fang", {}, [("crit_dmg_bonus", {"pct": 25})], "치명타 피해 +25%."),
    (8, 10): ("행운의 부적", "Lucky Charm", {}, [("shield_on_crit", {"pct": 4, "duration": 3})], "치명타 시 최대 체력 4%의 방어막."),
    (9, 9): ("뱀파이어 군주의 송곳니", "Vampire Lord's Fang", {"omnivamp": 9}, [("overheal_shield", {"max_pct": 30})], "피해 흡혈 +25%. 초과 치유량은 방어막이 된다(최대 체력 30%)."),
    (9, 10): ("불사의 심장", "Immortal Heart", {}, [("revive", {"hp_pct": 30})], "전투 중 1회 사망 시 체력 30%로 부활."),
    (10, 10): ("별의 갑주", "Star Plate", {"durability": 8}, [], "내구력 +20%."),
}

# 상징 조합: 비늘(C11)+재료 i → 출신, 문장(C12)+재료 i → 직업
SCALE_EMBLEM = {1: "astel", 2: "celestia", 3: "torga", 4: "grandur", 5: "lumen", 6: "elowen", 7: "lies", 8: "sairam", 9: "nox", 10: "dragonkin"}
CREST_EMBLEM = {1: "warrior", 2: "mage", 3: "knight", 4: "guardian", 5: "priest", 6: "ranger", 7: "summoner", 8: "assassin", 9: "duelist", 10: "dragoon"}
UNCRAFTABLE_ORIGIN = ["valheim", "karna", "neos", "freelancer"]
UNCRAFTABLE_CLASS = ["artillerist", "shaman", "bard", "engineer"]

# 유물 60: (한글, 영문, stats, hooks, 설명)
ARTIFACTS = [
    ("재의 왕관", "Crown of Ash", {"ap": 30, "hp": 200}, [("kill_explode", {"dmg": 250, "radius": 1})], "적 처치 시 주변 1칸에 250 마법 피해."),
    ("이셀라의 반지", "Isela's Ring", {"mana": 20, "ap": 20}, [("heal_on_cast_allies", {"pct": 6})], "스킬 사용 시 아군 전체 최대 체력 6% 회복."),
    ("용의 심장석", "Dragonheart Stone", {"hp": 500}, [("regen", {"pct_per_sec": 1.5})], "매초 최대 체력 1.5% 회복."),
    ("쐐기의 파편", "Spire Shard", {"ap": 40}, [("true_dmg_on_cast", {"pct": 10})], "스킬 피해의 10%만큼 고정 피해 추가."),
    ("고대 문명의 코어", "Ancient Core", {"as_pct": 20, "ad_pct": 10}, [("as_stack_on_attack", {"pct": 3, "max": 20})], "공격마다 공격 속도 +3% (최대 20중첩)."),
    ("세계수의 가지", "Worldtree Branch", {"hp": 300, "mr": 20}, [("regen", {"pct_per_sec": 1.0}), ("heal_allies_timer", {"delay": 4, "radius": 1, "missing_pct": 10, "interval": 5})], "자신 재생 + 5초마다 인접 아군 잃은 체력 10% 회복."),
    ("검성의 유품", "Sword Saint's Relic", {"ad_pct": 25, "crit": 20}, [("crit_dmg_bonus", {"pct": 40})], "치명타 피해 +40%."),
    ("심해의 진주", "Deep Pearl", {"mana": 30, "mr": 30}, [("mana_regen", {"per_sec": 3})], "매초 마나 +3."),
    ("네오스 반응로", "Neos Reactor", {"ap": 25, "as_pct": 15}, [("mana_refund_on_cast", {"mana": 30})], "스킬 사용 후 마나 +30."),
    ("사령왕의 두개골", "Necrolord Skull", {"ap": 30}, [("summon_on_kill", {"hp_pct": 30, "ad_pct": 30, "max": 2})], "적 처치 시 망령 소환(최대 2)."),
    ("노른의 실", "Norn's Thread", {"hp": 250, "durability": 8}, [("revive", {"hp_pct": 50})], "1회 부활(체력 50%)."),
    ("마신의 램프", "Djinn's Lamp", {"ap": 35, "mana": 15}, [("first_cast_bonus", {"pct": 60})], "첫 스킬의 피해/치유 +60%."),
    ("세이렌의 조개", "Siren's Shell", {"hp": 200, "mr": 20}, [("as_slow_aura", {"radius": 2, "pct": 20})], "주변 2칸 적 공격 속도 -20%."),
    ("황제의 인장", "Emperor's Seal", {"armor": 25, "mr": 25}, [("aura_allies", {"radius": 1, "armor": 15, "mr": 15})], "인접 아군 방어력·마저 +15."),
    ("투기장 우승 벨트", "Champion's Belt", {"hp": 350, "ad_pct": 10}, [("stack_ad_on_kill", {"pct": 8, "max": 5})], "처치마다 공격력 +8% (최대 5)."),
    ("현상금 사냥꾼의 총", "Bounty Gun", {"ad_pct": 20, "crit": 10}, [("execute_low", {"threshold": 15})], "체력 15% 이하 적을 즉시 처형."),
    ("성녀의 묵주", "Saint's Rosary", {"hp": 200, "mana": 20}, [("heal_allies_timer", {"delay": 2, "radius": 9, "missing_pct": 8, "interval": 4})], "4초마다 아군 전체 잃은 체력 8% 회복."),
    ("황룡의 비늘", "Gold Dragon Scale", {"armor": 40, "hp": 300}, [("thorns", {"pct": 15})], "받은 물리 피해 15% 반사."),
    ("별의 관측기", "Star Observer", {"ap": 20, "crit": 25}, [("spell_crit", {}), ("crit_dmg_bonus", {"pct": 15})], "스킬 치명타 가능 + 치명타 피해 +15%."),
    ("증기 심장", "Steam Heart", {"hp": 300, "as_pct": 15}, [("stack_on_hit", {"ad_pct": 2, "max": 20})], "공격/피격마다 공격력 +2% (최대 20)."),
    ("안개의 등불", "Mist Lantern", {"mr": 30, "hp": 150}, [("cc_immune", {"duration": 30})], "30초간 군중 제어 면역."),
    ("피의 성배", "Blood Chalice", {"omnivamp": 20, "ad_pct": 10}, [("overheal_shield", {"max_pct": 40})], "초과 치유량이 방어막이 된다(최대 40%)."),
    ("와이번의 발톱", "Wyvern Talon", {"ad_pct": 15, "as_pct": 10}, [("dash_dmg_bonus", {"pct": 50})], "도약/강하 스킬 피해 +50%."),
    ("골렘의 핵", "Golem Core", {"armor": 35, "mr": 35}, [("gargoyle", {"per_enemy": 15})], "자신을 노리는 적 1명당 방어력·마저 +15."),
    ("요정의 가루", "Fairy Dust", {"as_pct": 25}, [("dodge", {"pct": 15})], "15% 확률로 공격을 회피."),
    ("폭풍의 눈", "Eye of the Storm", {"ap": 30}, [("shock_every_n", {"n": 3, "targets": 4, "dmg": 90, "mr_shred": 30, "duration": 4})], "3번째 공격마다 적 4명에게 90 마법 피해 + 마저 감소."),
    ("용병왕의 계약서", "Mercenary King's Contract", {"ad_pct": 10, "ap": 10, "hp": 150}, [("gold_bonus", {"pct": 30})], "전투 승리 시 골드 +30%."),
    ("태초의 불씨", "Primordial Ember", {"ap": 35}, [("burn_on_hit", {"pct_per_sec": 2.0, "duration": 5, "grievous": 50})], "피해를 준 적에게 매초 최대 체력 2% 화상 + 치유 감소 50%."),
    ("거인의 심장", "Giant's Heart", {"hp": 900}, [], "체력 +900."),
    ("리치의 지팡이", "Lich Staff", {"ap": 50, "mana": 10}, [("mana_on_kill", {"mana": 30})], "적 처치 시 마나 +30."),
    ("얼음 여왕의 왕관", "Frost Queen's Crown", {"ap": 25, "mr": 25}, [("slow_on_cast", {"pct": 40, "duration": 3})], "스킬에 맞은 적 공격 속도 -40% (3초)."),
    ("모래시계", "Hourglass", {"mana": 25, "hp": 150}, [("stasis_low_hp", {"threshold": 30, "duration": 2})], "체력 30% 이하 시 2초간 무적 정지(1회)."),
    ("전설의 모루", "Legendary Anvil", {"armor": 20, "mr": 20, "hp": 150}, [("random_items", {"count": 1})], "전투마다 무작위 조합 아이템 1개의 능력치를 얻는다."),
    ("암살자의 가면", "Assassin's Mask", {"crit": 30, "ad_pct": 10}, [("backline_jump", {})], "전투 시작 시 적 후열로 도약한다."),
    ("수호자의 횃불", "Guardian's Torch", {"hp": 250, "armor": 20}, [("aura_allies", {"radius": 1, "hp_pct": 10})], "인접 아군 최대 체력 +10%."),
    ("바다의 삼지창", "Sea Trident", {"ad_pct": 20, "mana": 10}, [("aoe_on_attack", {"targets": 2, "ad_ratio": 0.4})], "공격 시 인접 적 2명에게 공격력 40% 추가 피해."),
    ("부족의 토템", "Tribal Totem", {"hp": 300, "ad_pct": 10}, [("stack_on_hit", {"ad_pct": 3, "max": 15})], "피격/공격마다 공격력 +3% (최대 15)."),
    ("천공의 나침반", "Sky Compass", {"as_pct": 15, "ap": 15}, [("extra_range", {"range": 2})], "사거리 +2."),
    ("불멸의 갑주", "Immortal Armor", {"armor": 50, "hp": 200}, [("low_hp_shield", {"threshold": 50, "shield_pct": 40, "def": 30, "duration": 6})], "체력 50% 이하 시 최대 체력 40% 방어막 + 방어력·마저 +30."),
    ("정령 계약서", "Elemental Pact", {"ap": 30}, [("summon_on_cast", {"hp_pct": 25, "ad_pct": 25, "max": 1})], "스킬 사용 시 정령 소환(최대 1)."),
    ("드워프의 룬 망치", "Dwarven Rune Hammer", {"ad_pct": 20, "armor": 20}, [("shred_on_hit", {"pct": 40, "duration": 3})], "공격 적중 시 방어력 40% 감소."),
    ("뱀파이어의 망토", "Vampire Cloak", {"omnivamp": 15, "hp": 200}, [("heal_on_kill", {"pct": 20})], "처치 시 최대 체력 20% 회복."),
    ("기계 심장", "Mech Heart", {"hp": 350, "as_pct": 10}, [("turret_stat_bonus", {"pct": 50})], "소환한 포탑/소환수 능력치 +50%."),
    ("성기사의 서약", "Paladin's Vow", {"armor": 30, "mr": 30}, [("start_shield", {"pct": 30, "duration": 10})], "전투 시작 시 최대 체력 30% 방어막(10초)."),
    ("공허의 눈", "Void Eye", {"ap": 40, "crit": 10}, [("true_dmg_on_cast", {"pct": 20})], "스킬 피해의 20%만큼 고정 피해 추가."),
    ("샤미센의 줄", "Shamisen String", {"as_pct": 20, "mana": 10}, [("aura_allies", {"radius": 1, "as_pct": 10})], "인접 아군 공격 속도 +10%."),
    ("전쟁의 북", "War Drum", {"hp": 200, "ad_pct": 10}, [("aura_allies", {"radius": 1, "ad_pct": 10})], "인접 아군 공격력 +10%."),
    ("마도 학술원의 증표", "Academy Token", {"ap": 25, "mana": 20}, [("cast_mana_allies", {"radius": 9, "mana": 5})], "스킬 사용 시 아군 전체 마나 +5."),
    ("용의 알 껍질", "Dragon Eggshell", {"armor": 30, "mr": 30, "hp": 200}, [("magic_dr", {"pct": 15})], "받는 마법 피해 -15%."),
    ("늑대의 이빨", "Wolf Fang", {"ad_pct": 15, "crit": 15}, [("execute_low", {"threshold": 10}), ("heal_on_kill", {"pct": 10})], "체력 10% 이하 적 처형, 처치 시 10% 회복."),
    ("고블린의 폭탄", "Goblin Bomb", {"ad_pct": 10, "ap": 10}, [("kill_explode", {"dmg": 300, "radius": 1})], "적 처치 시 주변 1칸 300 마법 피해."),
    ("오아시스의 물병", "Oasis Flask", {"hp": 200, "mana": 15}, [("heal_on_cast_allies", {"pct": 4}), ("regen", {"pct_per_sec": 0.8})], "스킬 사용 시 아군 4% 회복 + 자신 재생."),
    ("해적의 보물지도", "Pirate's Map", {"crit": 20, "hp": 150}, [("gold_bonus", {"pct": 50})], "전투 승리 시 골드 +50%."),
    ("빛의 심판봉", "Rod of Judgment", {"ap": 30, "mr": 20}, [("giant_slayer", {"hp_threshold": 1600, "bonus_pct": 30})], "최대 체력 1600 이상 적에게 피해 +30%."),
    ("트롤의 곤봉", "Troll Club", {"ad_pct": 30}, [("as_pct_penalty", {"pct": -15}), ("stack_ad_on_kill", {"pct": 10, "max": 5})], "공격력 +30%, 공격 속도 -15%, 처치마다 공격력 +10%."),
    ("별똥별 조각", "Meteor Shard", {"ap": 35, "as_pct": 10}, [("shock_every_n", {"n": 4, "targets": 1, "dmg": 200, "mr_shred": 0, "duration": 0})], "4번째 공격마다 200 마법 피해."),
    ("시간의 회중시계", "Pocket Watch", {"mana": 20, "as_pct": 10}, [("mana_regen", {"per_sec": 2}), ("mana_on_attack", {"mana": 2})], "매초 마나 +2, 공격 시 마나 +2."),
    ("수호천사의 깃털", "Angel Feather", {"hp": 250, "mr": 20}, [("revive", {"hp_pct": 40}), ("heal_on_revive_allies", {"pct": 10})], "1회 부활(40%) + 부활 시 아군 10% 회복."),
    ("대족장의 도끼", "Chieftain's Axe", {"ad_pct": 25, "hp": 200}, [("aoe_on_attack", {"targets": 2, "ad_ratio": 0.3})], "공격 시 인접 적 2명에게 공격력 30% 추가 피해."),
    ("심문관의 낙인", "Inquisitor's Brand", {"ad_pct": 15, "ap": 15}, [("burn_on_hit", {"pct_per_sec": 1.5, "duration": 4, "grievous": 50}), ("execute_low", {"threshold": 12})], "화상 + 치유 감소 + 12% 이하 처형."),
]

# 지원 아이템 30: 아군 지원 (장착자는 능력치 소량)
SUPPORT = [
    ("전쟁 깃발", "War Banner", {"hp": 100}, [("aura_allies", {"radius": 1, "ad_pct": 12, "ap": 12})], "인접 아군 공격력·주문력 +12%."),
    ("수호의 깃발", "Guardian Banner", {"hp": 100}, [("aura_allies", {"radius": 1, "armor": 20, "mr": 20})], "인접 아군 방어력·마저 +20."),
    ("치유의 향로", "Healing Censer", {"hp": 100}, [("heal_allies_timer", {"delay": 2, "radius": 1, "missing_pct": 12, "interval": 4})], "4초마다 인접 아군 잃은 체력 12% 회복."),
    ("질풍의 뿔피리", "Gale Horn", {"hp": 100}, [("aura_allies", {"radius": 1, "as_pct": 15})], "인접 아군 공격 속도 +15%."),
    ("마나의 샘", "Mana Spring", {"hp": 100}, [("aura_allies", {"radius": 1, "mana_regen": 2})], "인접 아군 매초 마나 +2."),
    ("성역의 등불", "Sanctuary Lamp", {"hp": 100}, [("aura_allies", {"radius": 1, "start_shield_pct": 15})], "인접 아군 전투 시작 시 15% 방어막."),
    ("용기의 나팔", "Horn of Courage", {"hp": 100}, [("aura_allies", {"radius": 9, "ad_pct": 6, "ap": 6})], "아군 전체 공격력·주문력 +6%."),
    ("철벽의 북", "Iron Drum", {"hp": 100}, [("aura_allies", {"radius": 9, "armor": 10, "mr": 10})], "아군 전체 방어력·마저 +10."),
    ("저주의 토템", "Curse Totem", {"hp": 100}, [("aura_enemies", {"radius": 2, "armor": -15, "mr": -15})], "주변 2칸 적 방어력·마저 -15."),
    ("둔화의 토템", "Slow Totem", {"hp": 100}, [("as_slow_aura", {"radius": 2, "pct": 15})], "주변 2칸 적 공격 속도 -15%."),
    ("재생의 토템", "Regen Totem", {"hp": 100}, [("aura_allies", {"radius": 1, "regen_pct": 1.0})], "인접 아군 매초 1% 재생."),
    ("전술 지도", "Tactical Map", {"hp": 100}, [("aura_allies", {"radius": 9, "start_mana": 15})], "아군 전체 시작 마나 +15."),
    ("흡혈의 깃발", "Vampiric Banner", {"hp": 100}, [("aura_allies", {"radius": 1, "omnivamp": 10})], "인접 아군 피해 흡혈 +10%."),
    ("치명의 깃발", "Lethal Banner", {"hp": 100}, [("aura_allies", {"radius": 1, "crit": 20})], "인접 아군 치명타 +20%."),
    ("내구의 깃발", "Durable Banner", {"hp": 100}, [("aura_allies", {"radius": 1, "durability": 8})], "인접 아군 내구력 +8%."),
    ("사정거리 망원경", "Range Scope", {"hp": 100}, [("aura_allies", {"radius": 1, "range": 1})], "인접 아군 사거리 +1."),
    ("가시 울타리", "Thorn Fence", {"hp": 100}, [("aura_allies", {"radius": 1, "thorns": 8})], "인접 아군 물리 피해 8% 반사."),
    ("용의 깃발", "Dragon Banner", {"hp": 100}, [("aura_allies", {"radius": 1, "hp_pct": 15})], "인접 아군 최대 체력 +15%."),
    ("공성 사다리", "Siege Ladder", {"hp": 100}, [("aura_allies", {"radius": 9, "structure_dmg_pct": 50})], "아군 전체 구조물에 주는 피해 +50%."),
    ("보급 마차", "Supply Wagon", {"hp": 100}, [("aura_allies", {"radius": 9, "heal_on_wave_pct": 25})], "웨이브 종료 시 아군 전체 25% 회복(웨이브 전투)."),
    ("정찰병의 각적", "Scout's Horn", {"hp": 100}, [("aura_allies", {"radius": 9, "start_as_pct": 20, "start_as_dur": 6})], "전투 시작 6초간 아군 전체 공격 속도 +20%."),
    ("기수의 안장", "Rider's Saddle", {"hp": 100}, [("aura_allies", {"radius": 1, "dash_dmg_pct": 30})], "인접 아군 강하/도약 피해 +30%."),
    ("암살 지령서", "Assassination Order", {"hp": 100}, [("aura_allies", {"radius": 1, "crit_dmg": 20})], "인접 아군 치명타 피해 +20%."),
    ("마법 증폭기", "Spell Amplifier", {"hp": 100}, [("aura_allies", {"radius": 1, "ap": 20})], "인접 아군 주문력 +20."),
    ("사제의 성수", "Priest's Holy Water", {"hp": 100}, [("aura_allies", {"radius": 9, "heal_pct": 20})], "아군 전체 받는 치유 +20%."),
    ("소환사의 서", "Summoner's Tome", {"hp": 100}, [("aura_allies", {"radius": 9, "summon_stat_pct": 30})], "아군 소환수 능력치 +30%."),
    ("공학자의 공구", "Engineer's Toolkit", {"hp": 100}, [("aura_allies", {"radius": 9, "turret_stat_pct": 30})], "아군 포탑 능력치 +30%."),
    ("용병 계약서", "Mercenary Contract", {"hp": 100}, [("gold_bonus", {"pct": 20}), ("aura_allies", {"radius": 1, "ad_pct": 5})], "골드 +20%, 인접 아군 공격력 +5%."),
    ("행운의 토끼발", "Rabbit's Foot", {"hp": 100}, [("drop_bonus", {"pct": 10})], "전투 보상 아이템 드랍률 +10%."),
    ("영웅의 부적", "Hero's Amulet", {"hp": 100}, [("hero_drop_bonus", {"pct": 10})], "영웅 드랍 확률 +10% (조우 전투)."),
]

# 국가 특산품 24 (국가 순서대로)
NATIONAL = [
    ("회색 늑대의 문장", {"ad_pct": 10, "hp": 150}, [("gold_bonus", {"pct": 15})], "골드 +15%."),
    ("아스텔 왕실 검", {"ad_pct": 15, "armor": 15}, [("start_shield", {"pct": 12, "duration": 6})], "시작 시 12% 방어막."),
    ("미르 포도주", {"hp": 250}, [("regen", {"pct_per_sec": 1.0})], "매초 1% 재생."),
    ("하르벤 용병 휘장", {"ad_pct": 12, "ap": 12}, [("stack_ad_on_kill", {"pct": 5, "max": 4})], "처치마다 공격력 +5%."),
    ("루멘 성유물함", {"mr": 30, "hp": 150}, [("revive", {"hp_pct": 25})], "1회 부활(25%)."),
    ("리에스 항해 나침반", {"as_pct": 15, "crit": 10}, [("gold_bonus", {"pct": 20})], "골드 +20%."),
    ("발하임 늑대 가죽", {"hp": 300, "ad_pct": 8}, [("low_hp_shield", {"threshold": 50, "shield_pct": 20, "ad_pct": 20, "duration": 5})], "체력 50% 이하 시 방어막 + 공격력."),
    ("카르나 모래 유리", {"ap": 25, "mana": 10}, [("first_cast_bonus", {"pct": 40})], "첫 스킬 +40%."),
    ("토르가 전쟁 가면", {"ad_pct": 15, "hp": 150}, [("stack_on_hit", {"ad_pct": 2, "max": 15})], "피격/공격마다 공격력 +2%."),
    ("쿠르간 기마 활", {"as_pct": 20, "ad_pct": 5}, [("extra_range", {"range": 1})], "사거리 +1."),
    ("사이람 벚꽃 검", {"ad_pct": 15, "crit": 15}, [("crit_dmg_bonus", {"pct": 20})], "치명타 피해 +20%."),
    ("엘로웬 세계수 잎", {"hp": 200, "mr": 20}, [("regen", {"pct_per_sec": 1.2})], "매초 1.2% 재생."),
    ("그란두르 룬 강철", {"armor": 35, "mr": 15}, [("thorns", {"pct": 8})], "물리 피해 8% 반사."),
    ("서리 제도 고래 기름", {"hp": 200, "as_pct": 10}, [("as_slow_aura", {"radius": 1, "pct": 15})], "인접 적 공속 -15%."),
    ("티아마 진주 목걸이", {"mana": 25, "mr": 20}, [("mana_regen", {"per_sec": 2})], "매초 마나 +2."),
    ("베일 요정 날개", {"as_pct": 20}, [("dodge", {"pct": 10})], "10% 회피."),
    ("자이로스 독 송곳니", {"ad_pct": 10, "as_pct": 10}, [("burn_on_hit", {"pct_per_sec": 1.0, "duration": 4, "grievous": 33})], "독(화상) + 치유 감소."),
    ("녹스 흑요석 두개골", {"ap": 30, "omnivamp": 8}, [("summon_on_kill", {"hp_pct": 25, "ad_pct": 25, "max": 1})], "처치 시 망령 소환."),
    ("황혼 요새 핏빛 잔", {"omnivamp": 15, "hp": 150}, [("heal_on_kill", {"pct": 12})], "처치 시 12% 회복."),
    ("마카브 흑요석 핵", {"armor": 25, "mr": 25}, [("gargoyle", {"per_enemy": 10})], "노리는 적당 방어력·마저 +10."),
    ("네오스 에너지 셀", {"ap": 20, "as_pct": 15}, [("mana_refund_on_cast", {"mana": 15})], "스킬 후 마나 +15."),
    ("셀레스티아 별의 서", {"ap": 35, "mana": 15}, [("cast_mana_allies", {"radius": 1, "mana": 6})], "스킬 시 인접 아군 마나 +6."),
    ("드라케스탄 용의 알 조각", {"hp": 300, "ap": 15, "ad_pct": 5}, [("magic_dr", {"pct": 10})], "받는 마법 피해 -10%."),
    ("애쉬펠 재의 비늘", {"ad_pct": 15, "ap": 15}, [("burn_on_hit", {"pct_per_sec": 1.5, "duration": 4, "grievous": 33}), ("kill_explode", {"dmg": 150, "radius": 1})], "화상 + 처치 시 폭발."),
]

CONSUMABLES = [
    ("스태미너 물약(소)", "Stamina Potion S", "stamina", {"stamina": 20}, 200, 10, "영웅 1명의 스태미너 20 회복."),
    ("스태미너 물약(중)", "Stamina Potion M", "stamina", {"stamina": 50}, 450, 22, "영웅 1명의 스태미너 50 회복."),
    ("스태미너 물약(대)", "Stamina Potion L", "stamina", {"stamina": 100}, 800, 40, "영웅 1명의 스태미너 전부 회복."),
    ("부대 스태미너 보급", "Squad Stamina Ration", "stamina", {"stamina_all": 30}, 1500, 70, "보유 영웅 전체 스태미너 30 회복."),
    ("영웅 서약서(일반)", "Hero Pact (Common)", "drop", {"hero_drop_mult": 1.5}, 600, 30, "조우 전투 1회 영웅 드랍 확률 ×1.5."),
    ("영웅 서약서(고급)", "Hero Pact (Rare)", "drop", {"hero_drop_mult": 2.0}, 1400, 60, "조우 전투 1회 영웅 드랍 확률 ×2.0."),
    ("영웅 서약서(전설)", "Hero Pact (Legendary)", "drop", {"hero_drop_mult": 3.0}, 0, 150, "조우 전투 1회 영웅 드랍 확률 ×3.0. 보석 전용."),
    ("매력 징표", "Charm Token", "affinity", {"affinity": 10}, 500, 25, "지정 영웅의 호감도 +10. 호감도 100 도달 시 확정 영입(천장)."),
    ("매력 징표 묶음", "Charm Token Bundle", "affinity", {"affinity": 50}, 0, 110, "지정 영웅의 호감도 +50. 보석 전용."),
    ("황금 열쇠", "Golden Key", "key", {"treasure_entry": 1}, 1000, 45, "보물 전투 입장권."),
    ("아이템 드랍 부적", "Item Drop Charm", "drop", {"item_drop_mult": 1.5}, 400, 20, "전투 1회 아이템 드랍 확률 ×1.5."),
    ("재료 드랍 부적", "Material Drop Charm", "drop", {"material_drop_mult": 1.5}, 400, 20, "전투 1회 승급 재료 드랍 ×1.5."),
]
MATERIALS = [
    ("영혼의 파편", "Soul Shard", "common", 40, "모든 영웅 승급의 기본 재료. 대부분의 전투에서 드랍."),
    ("용의 정수", "Dragon Essence", "rare", 250, "2성·3성 승급 재료. 토벌/레이드/고난도 전투에서 드랍."),
    ("별의 결정", "Star Crystal", "epic", 1500, "3성 승급 재료. 악몽 난이도, 레이드, 결전에서 드랍."),
]

PRICES = {"component": 300, "completed": 900, "emblem": 1500, "special": 3000, "uncraftable_emblem": 2500,
          "radiant": 3500, "artifact": 2800, "support": 1800, "national": 2200}


def merge_stats(*ds):
    out = {}
    for d in ds:
        for k, v in d.items():
            out[k] = out.get(k, 0) + v
    return out


def main():
    items = []
    comp_by_idx = {i + 1: c for i, c in enumerate(COMPONENTS)}
    for cid, ko, en, stat, val, desc in COMPONENTS + SPECIAL_COMPONENTS:
        items.append(dict(id=cid, name_ko=ko, name_en=en, category="component", stats=({stat: val} if stat != "none" else {}),
                          hooks=[], desc=desc, price_gold=PRICES["component"], recipe=None))

    # 조합 아이템
    n = 0
    for (i, j), (ko, en, extra, hooks, desc) in sorted(COMBOS.items()):
        n += 1
        ci, cj = comp_by_idx[i], comp_by_idx[j]
        stats = merge_stats({ci[3]: ci[4]}, {cj[3]: cj[4]}, extra)
        items.append(dict(id=f"I{n:03d}", name_ko=ko, name_en=en, category="completed", stats=stats,
                          hooks=[dict(type=h[0], params=h[1]) for h in hooks], desc=desc,
                          price_gold=PRICES["completed"], recipe=[ci[0], cj[0]]))
    completed = [it for it in items if it["category"] == "completed"]

    # 상징
    oname = {o[0]: o[1] for o in ORIGINS}; cname = {c[0]: c[1] for c in CLASSES}
    e = 0
    for i, okey in SCALE_EMBLEM.items():
        e += 1; ci = comp_by_idx[i]
        items.append(dict(id=f"E{e:03d}", name_ko=f"{oname[okey]}의 상징", name_en=f"{okey.title()} Emblem", category="emblem",
                          stats={ci[3]: ci[4]}, hooks=[dict(type="grant_trait", params={"trait": okey})],
                          desc=f"장착한 영웅이 '{oname[okey]}' 출신 특성을 추가로 얻는다. {ci[5]}", price_gold=PRICES["emblem"], recipe=["C11", ci[0]]))
    for i, ckey in CREST_EMBLEM.items():
        e += 1; ci = comp_by_idx[i]
        items.append(dict(id=f"E{e:03d}", name_ko=f"{cname[ckey]}의 상징", name_en=f"{ckey.title()} Emblem", category="emblem",
                          stats={ci[3]: ci[4]}, hooks=[dict(type="grant_trait", params={"trait": ckey})],
                          desc=f"장착한 영웅이 '{cname[ckey]}' 직업 특성을 추가로 얻는다. {ci[5]}", price_gold=PRICES["emblem"], recipe=["C12", ci[0]]))
    for okey in UNCRAFTABLE_ORIGIN:
        e += 1
        items.append(dict(id=f"E{e:03d}", name_ko=f"{oname[okey]}의 상징", name_en=f"{okey.title()} Emblem", category="emblem",
                          stats={"hp": 100}, hooks=[dict(type="grant_trait", params={"trait": okey})],
                          desc=f"장착한 영웅이 '{oname[okey]}' 출신 특성을 추가로 얻는다. 조합 불가(구매/보상 전용).", price_gold=PRICES["uncraftable_emblem"], recipe=None))
    for ckey in UNCRAFTABLE_CLASS:
        e += 1
        items.append(dict(id=f"E{e:03d}", name_ko=f"{cname[ckey]}의 상징", name_en=f"{ckey.title()} Emblem", category="emblem",
                          stats={"hp": 100}, hooks=[dict(type="grant_trait", params={"trait": ckey})],
                          desc=f"장착한 영웅이 '{cname[ckey]}' 직업 특성을 추가로 얻는다. 조합 불가(구매/보상 전용).", price_gold=PRICES["uncraftable_emblem"], recipe=None))
    specials = [
        ("용의 심장", "Dragon Heart", ["C11", "C11"], [("team_slot", {"slots": 1})], "팀 슬롯 +1. 장착 영웅은 전투에서 자리를 차지하지 않는 것으로 계산."),
        ("영웅의 왕관", "Hero's Crown", ["C12", "C12"], [("team_slot", {"slots": 1})], "팀 슬롯 +1."),
        ("전설의 인장", "Legendary Seal", ["C11", "C12"], [("double_trait_count", {})], "장착 영웅의 출신·직업 특성 카운트를 2로 계산."),
    ]
    for ko, en, rec, hooks, desc in specials:
        e += 1
        items.append(dict(id=f"E{e:03d}", name_ko=ko, name_en=en, category="emblem", stats={}, hooks=[dict(type=h[0], params=h[1]) for h in hooks],
                          desc=desc, price_gold=PRICES["special"], recipe=rec))

    # 빛나는 (radiant)
    for k, it in enumerate(completed):
        stats = {s: (round(v * 1.6) if s not in ("durability",) else v + 8) for s, v in it["stats"].items()}
        hooks = []
        for h in it["hooks"]:
            p = dict(h["params"])
            for pk in list(p.keys()):
                if pk in ("pct", "mana", "dmg", "ad_ratio", "missing_pct", "bonus_pct", "shield_pct", "ap", "per_enemy", "per_sec", "hp_pct", "mr_shred", "omnivamp", "dmg_pct", "ad_pct", "armor"):
                    p[pk] = round(p[pk] * 1.5, 2) if isinstance(p[pk], (int, float)) else p[pk]
            hooks.append(dict(type=h["type"], params=p))
        items.append(dict(id=f"R{k+1:03d}", name_ko="빛나는 " + it["name_ko"], name_en="Radiant " + it["name_en"], category="radiant",
                          stats=stats, hooks=hooks, desc="빛나는 강화판: 능력치 ×1.6, 효과 ×1.5. " + it["desc"], price_gold=PRICES["radiant"], recipe=None, base_item=it["id"]))

    for k, (ko, en, stats, hooks, desc) in enumerate(ARTIFACTS):
        items.append(dict(id=f"A{k+1:03d}", name_ko=ko, name_en=en, category="artifact", stats=stats, hooks=[dict(type=h[0], params=h[1]) for h in hooks],
                          desc=desc, price_gold=PRICES["artifact"], recipe=None))
    for k, (ko, en, stats, hooks, desc) in enumerate(SUPPORT):
        items.append(dict(id=f"S{k+1:03d}", name_ko=ko, name_en=en, category="support", stats=stats, hooks=[dict(type=h[0], params=h[1]) for h in hooks],
                          desc=desc, price_gold=PRICES["support"], recipe=None))
    for k, ((ko, stats, hooks, desc), nation) in enumerate(zip(NATIONAL, NATIONS)):
        items.append(dict(id=f"N{k+1:03d}", name_ko=ko, name_en=f"{nation[2]} Specialty", category="national", stats=stats,
                          hooks=[dict(type=h[0], params=h[1]) for h in hooks], desc=f"[{nation[1]} 특산] {desc}", price_gold=PRICES["national"], recipe=None, nation=nation[0]))
    for k, (ko, en, kind, eff, gold, gem, desc) in enumerate(CONSUMABLES):
        items.append(dict(id=f"X{k+1:03d}", name_ko=ko, name_en=en, category="consumable", kind=kind, effect=eff, desc=desc,
                          price_gold=(gold if gold > 0 else None), price_gem=gem, stats={}, hooks=[], recipe=None))
    for k, (ko, en, grade, gold, desc) in enumerate(MATERIALS):
        items.append(dict(id=f"M{k+1:03d}", name_ko=ko, name_en=en, category="material", grade=grade, desc=desc, price_gold=gold, stats={}, hooks=[], recipe=None))

    from collections import Counter
    cnt = Counter(it["category"] for it in items)
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, "items.json"), "w", encoding="utf-8") as f:
        json.dump({"version": 1, "count": len(items), "by_category": dict(cnt), "prices": PRICES, "items": items}, f, ensure_ascii=False, indent=1)
    print("items:", len(items), dict(cnt))


if __name__ == "__main__":
    main()
