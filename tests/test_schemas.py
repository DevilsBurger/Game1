# -*- coding: utf-8 -*-
"""JSON 스키마 검증 + 참조 무결성 (jsonschema 미설치 시 참조 무결성만)."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import gen_schemas


def test_schemas_validate():
    gen_schemas.write()
    assert gen_schemas.validate()
