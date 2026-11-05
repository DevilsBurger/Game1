# -*- coding: utf-8 -*-
"""server/openapi.yaml 정합성: 파싱, $ref 해석, operationId 유일, 15 문서 엔드포인트 포함, 에러 코드 enum 커버, 멱등 헤더."""
import os, re, yaml, pytest

ROOT = os.path.join(os.path.dirname(__file__), "..")
PATH = os.path.join(ROOT, "server", "openapi.yaml")


@pytest.fixture(scope="module")
def spec():
    return yaml.safe_load(open(PATH, encoding="utf-8"))


def test_refs_resolve(spec):
    text = open(PATH, encoding="utf-8").read()
    for group, name in set(re.findall(r"#/components/(\w+)/(\w+)", text)):
        assert name in spec["components"].get(group, {}), f"unresolved $ref {group}/{name}"


def test_operation_ids_unique(spec):
    ids = [op["operationId"] for p in spec["paths"].values() for m, op in p.items() if m in ("get", "post", "put", "patch", "delete")]
    assert len(ids) == len(set(ids)) and len(ids) >= 30


def test_doc15_endpoints_present(spec):
    paths = spec["paths"]
    for prefix in ["/auth", "/profile", "/roster", "/inventory", "/battle/start", "/battle/finish", "/shop", "/quest", "/config/balance"]:
        assert any(p.startswith(prefix) for p in paths), prefix


def test_error_codes_covered(spec):
    enum = set(spec["components"]["schemas"]["Error"]["properties"]["code"]["enum"])
    text = open(PATH, encoding="utf-8").read()
    mentioned = set(re.findall(r"\(([A-Z][A-Z_]{3,})\)", text)) | set(re.findall(r"\(([A-Z_]+/[A-Z_/]+)\)", text))
    flat = set()
    for m in mentioned:
        flat.update(m.split("/"))
    unknown = {c for c in flat if c.isupper() and c not in enum and c not in {"JWT", "GDPR", "KST", "CSPRNG", "DT", "ATT"}}
    assert not unknown, unknown


def test_mutations_idempotent(spec):
    exempt = {"/auth/guest", "/auth/link", "/auth/switch", "/auth/refresh", "/battle/abort", "/ftue/steps", "/telemetry/events", "/roster/presets", "/profile"}
    for path, item in spec["paths"].items():
        for m in ("post", "put"):
            if m in item and path not in exempt and not path.startswith("/roster/{hero_id}/equip"):
                params = item[m].get("parameters", [])
                assert any(p.get("$ref", "").endswith("IdempotencyKey") for p in params), f"{m.upper()} {path} lacks Idempotency-Key"


def test_battle_contract_matches_engine(spec):
    cs = spec["components"]["schemas"]["EventChecksum"]["properties"]
    assert set(cs) == {"count", "by_type", "damage_sum", "heal_sum"}
    req = spec["components"]["schemas"]["BattleStartRequest"]["properties"]
    assert req["difficulty"]["enum"] == ["normal", "hard", "nightmare"]
    assert req["formation"]["maxItems"] == 10
