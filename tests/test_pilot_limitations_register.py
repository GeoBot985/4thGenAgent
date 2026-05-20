from __future__ import annotations

import json

import pytest

from src.pilot_readiness import PILOT_LIMITATIONS, build_limitations_register


MINIMUM_LIMITATION_IDS = {
    "PILOT-LIM-001",
    "PILOT-LIM-002",
    "PILOT-LIM-003",
    "PILOT-LIM-004",
    "PILOT-LIM-005",
    "PILOT-LIM-006",
    "PILOT-LIM-007",
    "PILOT-LIM-008",
    "PILOT-LIM-009",
}

MINIMUM_AREAS = {
    "Live execution",
    "Production automation",
    "Live writes",
    "Recovery daemon",
    "Database backend",
    "Authentication",
    "Access control",
    "Deployment",
    "Alerting",
}


@pytest.fixture(scope="module")
def register():
    return build_limitations_register()


def test_limitations_register_returns_dict(register):
    assert isinstance(register, dict)


def test_limitations_register_is_valid_json(register):
    serialized = json.dumps(register, default=str)
    parsed = json.loads(serialized)
    assert parsed["register_type"] == "pilot_limitations"


def test_limitations_register_has_required_fields(register):
    assert "register_type" in register
    assert "version" in register
    assert "generated_at" in register
    assert "limitations" in register
    assert "claim" in register


def test_limitations_register_claim_does_not_claim_production_readiness(register):
    claim = register["claim"].lower()
    assert "production ready" not in claim
    assert "production-ready" not in claim


def test_limitations_register_has_minimum_count(register):
    assert len(register["limitations"]) >= 9


def test_all_required_limitation_ids_present(register):
    ids = {lim["limitation_id"] for lim in register["limitations"]}
    assert MINIMUM_LIMITATION_IDS.issubset(ids)


def test_all_required_areas_present(register):
    areas = {lim["area"] for lim in register["limitations"]}
    assert MINIMUM_AREAS.issubset(areas)


def test_each_limitation_has_required_fields(register):
    for lim in register["limitations"]:
        assert "limitation_id" in lim, f"limitation_id missing from {lim}"
        assert "area" in lim
        assert "description" in lim
        assert "impact" in lim
        assert "status" in lim
        assert "future_spec" in lim


def test_limitations_no_live_side_effects_documented(register):
    descriptions = " ".join(lim["description"].lower() for lim in register["limitations"])
    assert "side effect" in descriptions or "live" in descriptions


def test_limitations_no_production_automation_documented(register):
    descriptions = " ".join(lim["description"].lower() for lim in register["limitations"])
    assert "production" in descriptions or "unsupervised" in descriptions


def test_pilot_limitations_constant_matches_register(register):
    assert len(register["limitations"]) == len(PILOT_LIMITATIONS)
