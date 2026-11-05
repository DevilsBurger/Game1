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
