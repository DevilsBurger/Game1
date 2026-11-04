# -*- coding: utf-8 -*-
"""테스트 벡터 재검증: 파이썬 레퍼런스가 저장된 결과를 그대로 재현해야 한다(결정론). C# 포팅도 같은 파일로 검증한다."""
import os, sys, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "sim"))
from engine import GameData
from make_vectors import run_vector

VEC = os.path.join(os.path.dirname(__file__), "vectors", "battle_vectors.json")


def test_vectors_reproduce():
    if not os.path.exists(VEC):
        return
    d = GameData()
    doc = json.load(open(VEC, encoding="utf-8"))
    for v in doc["vectors"]:
        got = run_vector(d, v)
        assert got["winner"] == v["expected"]["winner"], v["name"]
        assert abs(got["time"] - v["expected"]["time"]) < 1e-6, v["name"]
        assert got["survivors"] == v["expected"]["survivors"], v["name"]
        assert got["total_damage"] == v["expected"]["total_damage"], v["name"]
