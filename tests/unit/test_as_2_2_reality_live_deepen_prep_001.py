"""AS-2.2-REALITY-LIVE-DEEPEN-PREP-001 - docs/contracts/fixtures only."""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema

ROOT = Path(__file__).resolve().parents[2]
PREP = ROOT / "docs" / "atlas-2.2" / "reality-live"
CONTRACTS = PREP / "contracts"
FIXTURES = PREP / "fixtures"
BASE_CONTRACTS = ROOT / "docs" / "atlas-2.2" / "contracts" / "reality-live"


def _load(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def test_reality_live_deepen_docs_present() -> None:
    for name in (
        "AS-2.2-REALITY-LIVE-DEEPEN-PREP-001.md",
        "INVARIANTS.md",
        "FIXTURE-PLAN.md",
        "CONTRACT.md",
        "adr/ADR-2.2-REALITY-LIVE-002-collectors-deepen-prep.md",
    ):
        path = PREP / name
        assert path.is_file(), name
        text = path.read_text(encoding="utf-8")
        assert "PREP" in text.upper()
        assert "ATLAS_2_1_RELEASE_CERTIFIED" in text or "RELEASE" in text.upper()


def test_reality_live_deepen_extends_base() -> None:
    assert BASE_CONTRACTS.is_dir()
    package = (PREP / "AS-2.2-REALITY-LIVE-DEEPEN-PREP-001.md").read_text(encoding="utf-8")
    assert "contracts/reality-live/" in package
    assert "dual-owning" in package.lower() or "dual-own" in package.lower()


def test_reality_live_forbidden_negatives() -> None:
    schema = _load(CONTRACTS / "reality-live-forbidden-action.schema.json")
    assert "PREP STUB" in json.dumps(schema)
    for name in (
        "negative-estate-invent.expect.json",
        "negative-unknown-as-healthy.expect.json",
        "negative-layer-b-write.expect.json",
    ):
        payload = _load(FIXTURES / name)
        jsonschema.validate(payload, schema)  # type: ignore[arg-type]
        assert payload["expect"] == "reject"
        assert payload["pilot_pass"] is False
        assert payload["release_certified"] is False
