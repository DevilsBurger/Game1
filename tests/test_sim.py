# -*- coding: utf-8 -*-
import os, sys, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "sim"))
from engine import GameData, Battle
from engine.hexgrid import hdist, hneighbors, COLS, ROWS

ROOT = os.path.join(os.path.dirname(__file__), "..")
D = GameData()


def test_hex_distance_and_neighbors():
    assert hdist((0, 0), (0, 0)) == 0
    assert hdist((0, 0), (1, 0)) == 1
    assert hdist((0, 0), (7, 0)) == 7
    assert all(hdist((3, 3), n) == 1 for n in hneighbors((3, 3)))
    assert len(hneighbors((3, 3))) == 6
    assert COLS == 8 and ROWS == 7


def test_data_counts():
    assert len(D.heroes) == 196
    assert len(D.origins) == 14 and len(D.classes) == 14
    items = json.load(open(os.path.join(ROOT, "data", "items.json"), encoding="utf-8"))
    assert items["count"] >= 280
    battles = json.load(open(os.path.join(ROOT, "data", "battles.json"), encoding="utf-8"))
    assert battles["count"] >= 1000
    assert battles["by_kind"]["encounter"] == 196
    quests = json.load(open(os.path.join(ROOT, "data", "quests.json"), encoding="utf-8"))
    assert quests["by_kind"]["hero_chain"] == 70


def test_roster_grid_unique():
    pairs = {(h["origin"], h["class"]) for h in D.heroes.values()}
    assert len(pairs) == 196


def test_damage_formula():
    a = D.hero_spec("H012"); e = D.hero_spec("H003")
    b = Battle(D, [a], [e], seed=1)
    u, v = b.units[0], b.units[1]
    v.e_armor = 100
    hp0 = v.hp
    b.damage(u, v, 200, "physical")
    assert abs((hp0 - v.hp) - 100) < 1e-6


def test_mana_and_cast():
    b = Battle(D, [D.hero_spec("H004")], [D.hero_spec("H003")], seed=2)
    r = b.run()
    assert r["winner"] in (0, 1)
    assert any(u["stats"]["casts"] > 0 for u in r["units"])


def test_determinism():
    ids = ["H001", "H010", "H020", "H030", "H040"]; ids2 = ["H050", "H060", "H070", "H080", "H090"]
    r1 = Battle(D, [D.hero_spec(h) for h in ids], [D.hero_spec(h) for h in ids2], seed=42).run()
    r2 = Battle(D, [D.hero_spec(h) for h in ids], [D.hero_spec(h) for h in ids2], seed=42).run()
    assert r1 == r2


def test_all_archetypes_and_items_run():
    seen = set()
    for h in D.heroes.values():
        a = h["skill"]["archetype"]
        if a in seen: continue
        seen.add(a)
        Battle(D, [D.hero_spec(h["id"], 3), D.hero_spec("H003")], [D.hero_spec("H017"), D.hero_spec("H031")], seed=3).run()
    for it in D.items.values():
        if it["category"] in ("consumable", "material"): continue
        Battle(D, [D.hero_spec("H005", items=[it["id"]]), D.hero_spec("H003")], [D.hero_spec("H017"), D.hero_spec("H020")], seed=5).run()


def test_traits_activate():
    astel = [h["id"] for h in D.heroes.values() if h["origin"] == "astel"][:4]
    b = Battle(D, [D.hero_spec(h) for h in astel], [D.hero_spec("H017")], seed=1)
    assert b.team_traits[0].get("astel") == 2


# ── 전투 분석 리포트 (08 §8.1)
def _report_pair(ids, ids2, seed, star2=1):
    mk = lambda hs, st: [D.hero_spec(h, st) for h in hs]
    plain = Battle(D, mk(ids, 1), mk(ids2, star2), seed=seed, rules={"record_events": True}).run()
    rep = Battle(D, mk(ids, 1), mk(ids2, star2), seed=seed, rules={"record_events": True, "report": True}).run()
    return plain, rep


def test_report_has_no_side_effects():
    ids = ["H001", "H010", "H020", "H030", "H040"]; ids2 = ["H050", "H060", "H070", "H080", "H090"]
    plain, rep = _report_pair(ids, ids2, 42)
    assert plain["report"] is None and rep["report"] is not None
    for k in ("winner", "time", "waves", "events", "units"):
        assert plain[k] == rep[k], k


def test_report_consistent_with_unit_stats():
    ids = ["H001", "H010", "H020", "H030", "H040"]; ids2 = ["H050", "H060", "H070", "H080", "H090"]
    for seed in (1, 7, 42):
        _, r = _report_pair(ids, ids2, seed)
        R = r["report"]; stats = {u["uid"]: u["stats"] for u in r["units"]}; team = {u["uid"]: u["team"] for u in r["units"]}
        for row in R["units"]:
            assert abs(sum(row["dealt"].values()) - stats[row["uid"]]["dmg"]) <= 3
            assert abs(sum(row["taken"].values()) - stats[row["uid"]]["taken"]) <= 3
            assert row["dealt_attack"] + row["dealt_skill"] <= sum(row["dealt"].values()) + 3
        # 행렬 합 = 받은 피해 합, 시간대 합 = 유닛이 준 피해 합
        assert abs(sum(m["amount"] for m in R["matrix"]) - sum(s["taken"] for s in stats.values())) <= len(R["matrix"])
        assert abs(sum(a + b for a, b in R["timeline"]) - sum(s["dmg"] for s in stats.values())) <= 2 * len(R["timeline"]) + len(stats)
        # 사망 기록은 실제 사망 유닛과 일치하고 시간 순
        dead = {u["uid"] for u in r["units"] if not u["alive"] and not u["is_summon"]}
        assert dead <= {d["uid"] for d in R["deaths"]}
        assert [d["t"] for d in R["deaths"]] == sorted(d["t"] for d in R["deaths"])
        for d in R["deaths"]:
            assert len(d["sources"]) <= 3 and sum(s["share"] for s in d["sources"]) <= 1.005
        assert team[R["mvp"]] == 0 and team[R["enemy_mvp"]] == 1
        assert sum(t["share"] for t in R["threats"]) <= 1.001


def test_report_hints_only_on_defeat():
    weak = ["H001", "H002", "H003"]; strong = ["H050", "H060", "H070", "H080", "H090"]
    _, lose = _report_pair(weak, strong, 5, star2=3)
    assert lose["winner"] == 1
    hints = lose["report"]["hints"]
    assert 1 <= len(hints) <= 3
    known = {"frontline_collapsed", "backline_dived", "single_threat", "physical_heavy", "magic_heavy", "cc_locked", "enemy_sustain", "damage_short"}
    assert all(h["code"] in known for h in hints)
    strings = json.load(open(os.path.join(ROOT, "data", "strings_ko.json"), encoding="utf-8"))
    assert all(f"ui.report.hint.{c}" in strings for c in known)
    mk = lambda hs, st: [D.hero_spec(h, st) for h in hs]
    win = Battle(D, mk(strong, 3), mk(weak, 1), seed=5, rules={"report": True}).run()
    assert win["winner"] == 0 and win["report"]["hints"] == []
