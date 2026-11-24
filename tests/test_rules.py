# -*- coding: utf-8 -*-
"""전투 유형 24 × 난이도 3 규칙 테스트: 유형별 첫 전투를 시나리오로 만들어 실행 가능·결정론·규칙 불변식을 검사한다 (23 문서 L1·C4)."""
import os, sys, json, random, pytest

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(ROOT, "sim"))
from engine import GameData, Battle  # noqa: E402
from scenario import build_scenario  # noqa: E402

battles = json.load(open(os.path.join(ROOT, "data", "battles.json"), encoding="utf-8"))
econ = json.load(open(os.path.join(ROOT, "data", "economy.json"), encoding="utf-8"))
D = GameData(battles=battles)
CURVE = econ.get("enemy_power_curve", {})
TYPES = sorted({b["type"] for b in battles["battles"]})
FIRST = {t: next(b for b in battles["battles"] if b["type"] == t) for t in TYPES}


def test_all_24_types_present():
    assert len(TYPES) == len(battles["battle_types"]) == 24


@pytest.mark.parametrize("diff", ["normal", "hard", "nightmare"])
@pytest.mark.parametrize("btype", TYPES)
def test_type_rules(btype, diff):
    b = FIRST[btype]
    allies, enemies, rules = build_scenario(D, b, diff, random.Random(1234), curve=CURVE)
    rules = dict(rules, record_events=True)
    r1 = Battle(D, allies, enemies, seed=42, rules=rules).run()
    r2 = Battle(D, allies, enemies, seed=42, rules=rules).run()
    waves = b["enemy"].get("waves", 1)
    assert r1["winner"] in (0, 1, -1)
    assert r1["events"] == r2["events"] and r1["winner"] == r2["winner"] and r1["time"] == r2["time"], "determinism"
    assert r1["time"] <= 45.0 * waves + 1.0
    assert 1 <= r1["waves"] <= waves  # wave_index는 1부터
    if waves > 1:
        assert len(rules["waves"]) == waves - 1
    for st in b["enemy"].get("structures", []):
        if st["side"] == "enemy":
            assert any(e.get("is_structure") for e in enemies)
        else:
            assert any(a.get("state", {}).get("must_survive") for a in allies)
    if btype == "assassination":
        assert rules.get("assassination") and any(e.get("state", {}).get("commander") for e in enemies)
    if btype == "rescue":
        assert any(a.get("state", {}).get("captive") for a in allies) and any(e.get("state", {}).get("jailer") for e in enemies)
    if btype == "escape":
        assert rules.get("escape")
    if b["participation"]["mode"] == "solo":
        assert len([a for a in allies if not a.get("is_structure")]) == 1
    p = b["participation"]
    n_allies = len([a for a in allies if not a.get("is_structure")])
    assert p["min"] <= n_allies <= p["max"]


def test_difficulty_scales_enemy_power():
    b = FIRST["skirmish"]
    hp = {}
    for diff in ("normal", "hard", "nightmare"):
        _, enemies, _ = build_scenario(D, b, diff, random.Random(1), curve=CURVE)
        hp[diff] = sum(e["hp"] for e in enemies if not e.get("is_structure"))
    assert hp["normal"] < hp["hard"] < hp["nightmare"]


# ── 후반 골드 경제 규칙 (07 §2.4~2.6, §3)
def test_gold_potion_cannot_loop_unbounded():
    """골드 물약은 전투 골드보다 싸므로 반드시 일일 한도가 있어야 한다."""
    items = {i["id"]: i for i in json.load(open(os.path.join(ROOT, "data", "items.json"), encoding="utf-8"))["items"]}
    battles = json.load(open(os.path.join(ROOT, "data", "battles.json"), encoding="utf-8"))["battles"]
    per_stamina = items["X003"]["price_gold"] / items["X003"]["effect"]["stamina"]
    profitable = sum(1 for b in battles if b["kind"] == "regional"
                     and b["difficulties"]["nightmare"]["rewards"]["gold"] > per_stamina * b["difficulties"]["nightmare"]["stamina_per_hero"] * b["participation"]["max"])
    assert profitable > 0                                   # 루프가 실제로 이득인 전투가 존재하고
    assert 1 <= econ["stamina"]["gold_potion_daily_limit"] <= 5   # 그래서 한도로 막는다


def test_repeat_gold_decay_and_facilities():
    steps = econ["repeat_gold_decay"]["steps"]
    assert [s["from_win"] for s in steps] == sorted(s["from_win"] for s in steps)
    assert all(0 < s["gold_mult"] < 1 for s in steps) and [s["gold_mult"] for s in steps] == sorted((s["gold_mult"] for s in steps), reverse=True)
    fac = econ["facilities"]; cost = [fac["cost_by_level"][str(n)] for n in range(1, fac["max_level"] + 1)]
    assert cost == sorted(cost) and cost[0] == fac["cost_base"]
    assert len(fac["list"]) == 5 and len({f["key"] for f in fac["list"]}) == 5
    # 시설은 전투 능력치·스태미너를 건드리지 않는다
    assert not any(k in f["effect"] for f in fac["list"] for k in ("hp", "ad", "ap", "armor", "stamina", "damage"))
    # 보유 영웅 호감도 파편 보상은 골드 → 파편 차익이 되면 안 된다
    items = {i["id"]: i for i in json.load(open(os.path.join(ROOT, "data", "items.json"), encoding="utf-8"))["items"]}
    ao = econ["affinity_owned"]
    cost_gold = ao["shard_reward_every"] / items["X008"]["effect"]["affinity"] * items["X008"]["price_gold"]
    assert ao["shard_reward_M001"] * items["M001"]["price_gold"] < cost_gold
