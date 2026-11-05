# -*- coding: utf-8 -*-
"""아트 제작 관리 시트: data/prompts.json → data/art_tracker.csv (ID, 분류, 대상, 우선순위, 규격, sref, 상태, 담당, 검수, 프롬프트)."""
import json, os, csv
ROOT = os.path.join(os.path.dirname(__file__), "..")
P = json.load(open(os.path.join(ROOT, "data", "prompts.json"), encoding="utf-8"))
heroes = {h["id"]: h for h in json.load(open(os.path.join(ROOT, "data", "heroes.json"), encoding="utf-8"))["heroes"]}
nations = {n["key"]: n for n in json.load(open(os.path.join(ROOT, "data", "nations.json"), encoding="utf-8"))["nations"]}
battles = json.load(open(os.path.join(ROOT, "data", "battles.json"), encoding="utf-8"))
mon_tier = {m["key"]: m["tier"] for m in battles["monsters"]}
ORIGIN_NATION = {"astel": "astel", "valheim": "valheim", "sairam": "sairam", "karna": "karna", "lies": "lies", "elowen": "elowen", "grandur": "grandur", "neos": "neos", "nox": "nox", "celestia": "celestia", "dragonkin": "drakestan", "torga": "torga", "lumen": "lumen", "freelancer": "bromel"}
SPEC = {"portrait": "1024x1024", "standing": "1024x1536", "unit": "1536x1024 sheet", "fullbody": "1920x1080"}
SREF = {"portrait": "SREF_PORTRAIT", "standing": "SREF_PORTRAIT", "unit": "SREF_UNIT", "fullbody": "SREF_BG"}
rows = []
def prio_of_act(act): return {1: "P1", 2: "P2", 3: "P3", 4: "P4", 5: "P4"}.get(act, "P3")
for h in P["heroes"]:
    hd = heroes.get(h["id"]); act = nations[ORIGIN_NATION[hd["origin"]]]["act"] if hd else 1
    for kind, pr in h["prompts"].items():
        rows.append([f"IMG-HERO-{kind.upper()}-{h['id']}", "hero", h["name_ko"], prio_of_act(act), SPEC[kind], SREF[kind], "todo", "", "", pr])
for m in P["monsters"]:
    for kind, pr in m["prompts"].items():
        rows.append([f"UNIT-MON-{kind.upper()}-{m['key']}" if kind != "unit" else f"UNIT-MON-{m['key']}", "monster", m["name_ko"], "P1" if mon_tier.get(m["key"], 1) <= 2 else "P2", SPEC[kind] if kind in SPEC else "1024x1024", SREF.get(kind, "SREF_UNIT"), "todo", "", "", pr])
for it in P["items"]:
    cat = it["id"][0]
    rows.append([f"IMG-ITEM-{it['id']}", "item", it["name_ko"], "P1" if cat in "CIM" else ("P2" if cat in "ESN" else "P3"), "512x512", "SREF_ITEM", "todo", "", "", it["prompt"]])
for b in P["backgrounds"]:
    nk = b["id"].split("-")[3] if b["id"].startswith("BG-NATION") else b["id"].split("-")[2]
    rows.append([b["id"], "background", b.get("region", nations[nk]["name_ko"]), prio_of_act(nations[nk]["act"]), "1920x1080", "SREF_BG", "todo", "", "", b["prompt"]])
for c in P["cutscenes"]:
    rows.append([c["id"], "cutscene", f"막 {c['act']}", prio_of_act(max(1, c["act"])), "1920x1080", "SREF_BG", "todo", "", "", c["prompt"]])
for u in P["ui"]:
    rows.append([u["id"], "ui", u["id"], "P0", "var", "SREF_UI", "todo", "", "", u["prompt"]])
rows.sort(key=lambda r: (r[3], r[1], r[0]))
with open(os.path.join(ROOT, "data", "art_tracker.csv"), "w", encoding="utf-8", newline="") as f:
    w = csv.writer(f); w.writerow(["asset_id", "category", "subject", "priority", "spec", "sref_slot", "status", "owner", "review", "prompt"])
    w.writerows(rows)
from collections import Counter
print("art tracker rows:", len(rows), dict(Counter(r[3] for r in rows)))
