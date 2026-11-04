# -*- coding: utf-8 -*-
"""
C# 포팅 검증용 테스트 벡터 생성: 전투 설정(시드·편성·아이템·성급·규칙) + 파이썬 레퍼런스 결과(승자·시간·생존·유닛 통계).
출력: tests/vectors/battle_vectors.json  (tests/test_vectors.py가 재검증)
"""
import json, os, sys, random
sys.path.insert(0, os.path.dirname(__file__))
from engine import GameData, Battle
from scenario import structure_spec

ROOT = os.path.join(os.path.dirname(__file__), "..")
OUT = os.path.join(ROOT, "tests", "vectors")


def main():
    d = GameData()
    rng = random.Random(123)
    ids = list(d.heroes)
    items = [i["id"] for i in d.items.values() if i["category"] in ("completed", "artifact", "support")]
    vectors = []
    # 1) 무작위 팀전 (아이템·성급 혼합)
    for k in range(24):
        n = rng.choice([3, 5, 8])
        a = rng.sample(ids, n); b = rng.sample([x for x in ids if x not in a], n)
        A = [{"hero": h, "star": rng.choice([1, 2, 3]), "items": rng.sample(items, rng.choice([0, 1, 2, 3]))} for h in a]
        B = [{"hero": h, "star": rng.choice([1, 2, 3]), "items": rng.sample(items, rng.choice([0, 1, 2]))} for h in b]
        vectors.append({"name": f"random_{k}", "seed": 1000 + k, "allies": A, "enemies": B, "rules": {}})
    # 2) 1v1 전수 샘플
    for k in range(12):
        a, b = rng.sample(ids, 2)
        vectors.append({"name": f"duel_{k}", "seed": 2000 + k, "allies": [{"hero": a, "star": 2, "items": []}], "enemies": [{"hero": b, "star": 2, "items": []}], "rules": {}})
    # 3) 규칙: 웨이브·구조물·탈출·암살
    a = rng.sample(ids, 5); b = rng.sample([x for x in ids if x not in a], 4)
    vectors.append({"name": "waves_3", "seed": 3001, "allies": [{"hero": h, "star": 2, "items": []} for h in a],
                    "enemies": [{"hero": h, "star": 1, "items": []} for h in b], "rules": {"waves": [[{"hero": h, "star": 1, "items": []} for h in b]] * 2}})
    vectors.append({"name": "siege_wall", "seed": 3002, "allies": [{"hero": h, "star": 2, "items": []} for h in a],
                    "enemies": [{"hero": h, "star": 1, "items": []} for h in b] + [{"structure": "성벽", "hp": 6000, "state": {"priority": True, "arrow_aura_pct": 0.8}}], "rules": {}})
    vectors.append({"name": "guard_altar", "seed": 3003, "allies": [{"hero": h, "star": 1, "items": []} for h in a] + [{"structure": "제단", "hp": 2500, "state": {"must_survive": True}}],
                    "enemies": [{"hero": h, "star": 2, "items": []} for h in b], "rules": {}})
    vectors.append({"name": "escape_30s", "seed": 3004, "allies": [{"hero": h, "star": 1, "items": []} for h in a], "enemies": [{"hero": h, "star": 3, "items": []} for h in b], "rules": {"escape": True}})
    vectors.append({"name": "assassination", "seed": 3005, "allies": [{"hero": h, "star": 2, "items": []} for h in a],
                    "enemies": [{"hero": h, "star": 2, "items": [], "state": {"commander": True}} if i == 0 else {"hero": h, "star": 2, "items": []} for i, h in enumerate(b)], "rules": {"assassination": True}})
    out = []
    for v in vectors:
        res = run_vector(d, v)
        out.append({**v, "expected": res})
    os.makedirs(OUT, exist_ok=True)
    json.dump({"engine_version": 1, "dt": 0.05, "count": len(out), "vectors": out}, open(os.path.join(OUT, "battle_vectors.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("vectors:", len(out))


def to_spec(d, u):
    if "structure" in u:
        return structure_spec(u["structure"], u["hp"], state=u.get("state", {}))
    s = d.hero_spec(u["hero"], u["star"], items=u.get("items", []))
    if u.get("state"): s["state"] = u["state"]
    return s


def run_vector(d, v):
    rules = dict(v.get("rules", {}))
    if rules.get("waves"):
        rules["waves"] = [[to_spec(d, u) for u in wave] for wave in rules["waves"]]
    r = Battle(d, [to_spec(d, u) for u in v["allies"]], [to_spec(d, u) for u in v["enemies"]], seed=v["seed"], rules=rules).run()
    return {"winner": r["winner"], "time": r["time"], "survivors": sorted([u["name"] for u in r["units"] if u["alive"] and not u["is_summon"]]),
            "total_damage": {str(t): round(sum(u["stats"]["dmg"] for u in r["units"] if u["team"] == t)) for t in (0, 1)}}


if __name__ == "__main__":
    main()
