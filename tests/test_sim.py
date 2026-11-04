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
