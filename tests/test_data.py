# -*- coding: utf-8 -*-
"""데이터 무결성 테스트: 카운트, 참조, 분포."""
import os, json
from collections import Counter

ROOT = os.path.join(os.path.dirname(__file__), "..")
D = lambda n: json.load(open(os.path.join(ROOT, "data", n), encoding="utf-8"))
heroes = D("heroes.json"); items = D("items.json"); nations = D("nations.json"); battles = D("battles.json"); quests = D("quests.json"); traits = D("traits.json"); econ = D("economy.json")
HID = {h["id"] for h in heroes["heroes"]}; IID = {i["id"] for i in items["items"]}; NK = {n["key"] for n in nations["nations"]}
MK = {m["key"] for m in battles["monsters"]}; BID = {b["id"] for b in battles["battles"]}


def test_hero_distribution():
    assert heroes["count"] == 196
    tiers = Counter(h["tier"] for h in heroes["heroes"])
    assert tiers == {1: 42, 2: 42, 3: 42, 4: 42, 5: 28}
    for o in traits["origins"]:
        c = Counter(h["tier"] for h in heroes["heroes"] if h["origin"] == o["key"])
        assert [c[t] for t in range(1, 6)] == [3, 3, 3, 3, 2], o["key"]
    for cl in traits["classes"]:
        n = sum(1 for h in heroes["heroes"] if h["class"] == cl["key"])
        assert n == 14


def test_items_recipes_and_prices():
    assert items["count"] >= 280
    comps = {i["id"] for i in items["items"] if i["category"] == "component"}
    assert len(comps) == 12
    completed = [i for i in items["items"] if i["category"] == "completed"]
    assert len(completed) == 55
    seen = set()
    for it in completed:
        key = tuple(sorted(it["recipe"]))
        assert key not in seen; seen.add(key)
        assert set(it["recipe"]) <= comps
    for it in items["items"]:
        if it["category"] not in ("consumable",):
            assert it.get("price_gold") is not None and it["price_gold"] > 0, it["id"]


def test_nations_and_battles():
    assert nations["count"] == 24 and battles["count"] >= 1000
    assert sum(1 for n in nations["nations"] if n["category"] == "숨겨진 나라") >= 5
    civs = {n["civilization"] for n in nations["nations"]}
    assert any("SF" in c for c in civs) and any("흑마법" in c for c in civs)
    kinds = battles["by_kind"]
    assert kinds["regional"] == 1080 and kinds["encounter"] == 196 and kinds["story"] == 76
    for b in battles["battles"]:
        assert b["nation"] in NK
        assert set(b["difficulties"].keys()) >= {"normal", "hard", "nightmare"}
        for u in b["enemy"]["units"]: assert u["unit"] in MK
        if b["enemy"]["boss"]: assert b["enemy"]["boss"]["unit"] in MK
        r = b["difficulties"]["normal"]["rewards"]
        assert r["gold"] > 0 and "M001" in r["materials"]
        assert b["difficulties"]["hard"]["rewards"]["gold"] > r["gold"] < b["difficulties"]["nightmare"]["rewards"]["gold"]
        if b["kind"] == "encounter": assert b["hero_id"] in HID and r["hero_drop"]["hero_id"] == b["hero_id"]


def test_every_hero_has_encounter_and_tier45_chain():
    enc = {b["hero_id"] for b in battles["battles"] if b["kind"] == "encounter"}
    assert enc == HID
    chains = {q["hero_id"] for q in quests["quests"] if q["kind"] == "hero_chain"}
    assert chains == {h["id"] for h in heroes["heroes"] if h["tier"] >= 4}
    for q in quests["quests"]:
        for s in q["steps"]: assert s["battle_id"] in BID, s


def test_economy_star_up_uniform_materials():
    for key in ("1_to_2", "2_to_3"):
        for t in range(1, 6):
            c = econ["star_up_cost"][key][str(t)]
            assert set(c.keys()) == {"M001", "M002", "M003", "gold"}
