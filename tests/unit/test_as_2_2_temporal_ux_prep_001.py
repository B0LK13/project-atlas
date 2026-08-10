"""AS-2.2-TEMPORAL-UX-PREP-001 — docs/contracts/fixtures only (no src mutation)."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import jsonschema
import pytest

ROOT = Path(__file__).resolve().parents[2]
PREP = ROOT / "docs" / "atlas-2.2" / "temporal-ux"
CONTRACTS = PREP / "contracts"
FIXTURES = PREP / "fixtures"

DOCS = {
    "package": PREP / "AS-2.2-TEMPORAL-UX-PREP-001.md",
    "architecture": PREP / "ARCHITECTURE.md",
    "contract": PREP / "CONTRACT.md",
    "invariants": PREP / "INVARIANTS.md",
    "fixture_plan": PREP / "FIXTURE-PLAN.md",
    "adr": PREP / "adr" / "ADR-2.2-TEMPORAL-UX-001-validity-lens-cockpit.md",
}

SCHEMA_FILES = {
    "cockpit": "temporal-cockpit-view.schema.json",
    "card": "validity-window-card.schema.json",
    "receipt": "as-of-lens-receipt.schema.json",
    "action": "temporal-action.schema.json",
}

FIXTURE_SCHEMA = {
    "cockpit-as-of-selected.sample.json": "cockpit",
    "validity-window-card.sample.json": "card",
    "as-of-lens-receipt.sample.json": "receipt",
    "negative-wall-clock.expect.json": "action",
    "negative-silent-winner.expect.json": "action",
    "negative-bitemporal-mutation.expect.json": "action",
}


def _load_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def _schema(name: str) -> dict:
    return _load_json(CONTRACTS / SCHEMA_FILES[name])  # type: ignore[return-value]


def test_prep_docs_exist_without_readme() -> None:
    for path in DOCS.values():
        assert path.is_file(), path
        text = path.read_text(encoding="utf-8")
        assert "AS-2.2-TEMPORAL-UX" in text or "TEMPORAL UX" in text
        assert "PREP" in text.upper() or "prep" in text
    assert not (PREP / "README.md").exists()
    assert not any(PREP.rglob("README.md"))


def test_contract_stubs_exist_and_are_not_package_data() -> None:
    package_schemas = ROOT / "src" / "project_atlas" / "schemas"
    for filename in SCHEMA_FILES.values():
        stub = CONTRACTS / filename
        assert stub.is_file(), stub
        body = stub.read_text(encoding="utf-8")
        assert "PREP STUB" in body
        assert "temporal" in body.lower() or "validity" in body.lower() or "as-of" in body.lower()
        assert not (package_schemas / filename).exists()


def test_fixtures_validate_against_prep_stubs() -> None:
    for fixture_name, schema_key in FIXTURE_SCHEMA.items():
        fixture_path = FIXTURES / fixture_name
        assert fixture_path.is_file(), fixture_path
        instance = _load_json(fixture_path)
        schema = _schema(schema_key)
        jsonschema.validate(instance=instance, schema=schema)


def test_package_card_non_claims() -> None:
    text = DOCS["package"].read_text(encoding="utf-8")
    assert "ATLAS_2_1_RELEASE_CERTIFIED" in text
    assert "**NO**" in text
    assert "ATLAS_2_2_INTELLIGENCE_IMPLEMENTATION_UNLOCKED" in text
    assert "bitemporal" in text
    lowered = text.lower()
    assert (
        "do not mutate" in lowered
        or "NONE" in text
        or "No bitemporal" in text
        or "NO BITEMPORAL" in text
    )


def test_invariants_document_fail_closed_walls() -> None:
    text = DOCS["invariants"].read_text(encoding="utf-8")
    assert "wall-clock" in text.lower() or "wall_clock" in text
    assert "silent winner" in text.lower() or "silent_winner" in text
    assert "UI ≠ canonical" in text or "UI≠canonical" in text
    assert "bitemporal" in text
    assert "ATLAS_2_1_RELEASE_CERTIFIED" in text
    assert "NO" in text


def test_open_cockpit_exposes_selected_window_and_derived_authority() -> None:
    cockpit = _load_json(FIXTURES / "cockpit-as-of-selected.sample.json")
    assert isinstance(cockpit, dict)
    assert cockpit["package_id"] == "AS-2.2-TEMPORAL-UX-PREP-001"
    assert cockpit["authority"]["level"] == "derived"
    assert cockpit["evidence_class"] == "fixture-only"
    assert cockpit["pilot_roots"] == 0
    assert cockpit["as_of_valid_time"] == "2024-06-15"
    assert cockpit["as_of_valid_time"] not in {"now", "today"}
    card = cockpit["cards"][0]
    assert card["disposition"] == "selected"
    assert card["valid_from"]
    assert card["authority"]["level"] == "derived"
    receipt = cockpit["receipt"]
    assert receipt["status"] == "selected"
    assert "claim.demo.status.planned" in receipt["selected_claim_ids"]


def test_negative_actions_are_rejected_forbidden() -> None:
    cases = {
        "negative-wall-clock.expect.json": (
            "wall_clock_as_of",
            "temporal-ux-wall-clock-forbidden",
        ),
        "negative-silent-winner.expect.json": (
            "silent_winner",
            "temporal-ux-silent-winner-forbidden",
        ),
        "negative-bitemporal-mutation.expect.json": (
            "bitemporal_mutation",
            "temporal-ux-bitemporal-mutation-forbidden",
        ),
    }
    for name, (kind, error) in cases.items():
        payload = _load_json(FIXTURES / name)
        assert isinstance(payload, dict)
        assert payload["kind"] == kind
        assert payload["status"] == "rejected_forbidden"
        assert payload["expected_error"] == error
        assert payload["authority"]["level"] == "derived"


def test_card_schema_rejects_missing_window() -> None:
    schema = _schema("card")
    bad = _load_json(FIXTURES / "validity-window-card.sample.json")
    assert isinstance(bad, dict)
    del bad["valid_from"]
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=bad, schema=schema)


def test_no_runtime_bitemporal_mutation() -> None:
    """Prep must not touch bitemporal or other src surfaces."""
    diff = subprocess.check_output(
        ["git", "diff", "--name-only", "origin/main...HEAD"],
        cwd=ROOT,
        text=True,
    )
    changed = {line.strip().replace("\\", "/") for line in diff.splitlines() if line.strip()}
    assert "src/project_atlas/bitemporal.py" not in changed
    assert "src/project_atlas/temporal_evaluator.py" not in changed
    for name in changed:
        assert not name.startswith("src/"), name
        assert name.startswith("docs/atlas-2.2/temporal-ux/") or name == (
            "tests/unit/test_as_2_2_temporal_ux_prep_001.py"
        ), name
        assert not name.endswith("README.md"), name
        assert name != "docs/atlas-2.2/README.md"
