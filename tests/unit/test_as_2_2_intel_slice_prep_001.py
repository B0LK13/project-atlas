"""AS-2.2-INTEL-SLICE-PREP-001 — architecture/fixtures only (no src mutation)."""

from __future__ import annotations

import json
from pathlib import Path

from _atlas_2_2_maturity import assert_prep_branch_scope

ROOT = Path(__file__).resolve().parents[2]
PREP = ROOT / "docs" / "atlas-2.2" / "intel-slice"
FIXTURES = PREP / "fixtures"

DOCS = {
    "package": PREP / "AS-2.2-INTEL-SLICE-PREP-001.md",
    "architecture": PREP / "ARCHITECTURE.md",
    "invariants": PREP / "INVARIANTS.md",
    "fixture_plan": PREP / "FIXTURE-PLAN.md",
}

SAMPLE_FIXTURES = (
    "intel-slice-complete.sample.json",
    "intel-slice-incomplete.sample.json",
    "inputs-citations.sample.json",
)

NEGATIVE_FIXTURES = {
    "negative-authority-elevation.expect.json": (
        "authority_elevation",
        "intel-slice-authority-elevation-forbidden",
    ),
    "negative-silent-conflict-resolve.expect.json": (
        "silent_conflict_resolve",
        "intel-slice-silent-conflict-resolve-forbidden",
    ),
    "negative-llm-authority.expect.json": (
        "llm_authority",
        "intel-slice-llm-authority-forbidden",
    ),
    "negative-canonical-write.expect.json": (
        "canonical_write",
        "intel-slice-canonical-write-forbidden",
    ),
}

INPUT_FAMILIES = (
    "kf_fabric",
    "retrieval",
    "context_packs",
    "temporal",
    "conflicts",
)


def _load_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def test_prep_docs_exist_without_readme() -> None:
    for path in DOCS.values():
        assert path.is_file(), path
        text = path.read_text(encoding="utf-8")
        assert "AS-2.2-INTEL-SLICE" in text
        assert "PREP" in text.upper() or "prep" in text
    assert not (PREP / "README.md").exists()
    assert not any(PREP.rglob("README.md"))
    # Deepen PREP may add contracts/ + adr/; base package remains architecture + fixtures.


def test_package_card_non_claims() -> None:
    text = DOCS["package"].read_text(encoding="utf-8")
    assert "ATLAS_2_1_RELEASE_CERTIFIED" in text
    assert "**NO**" in text
    assert "ATLAS_2_2_INTELLIGENCE_IMPLEMENTATION_UNLOCKED" in text
    assert "architecture" in text.lower()
    assert "fixture" in text.lower()
    assert "NONE" in text or "do not mutate" in text.lower() or "Production mutation" in text


def test_architecture_documents_composition_layers() -> None:
    text = DOCS["architecture"].read_text(encoding="utf-8")
    assert "IntelligenceSliceEnvelope" in text or "intelligence slice" in text.lower()
    assert "KF" in text or "kf_fabric" in text
    assert "RET" in text or "retrieval" in text.lower()
    assert "TEMPORAL" in text or "temporal" in text.lower()
    assert "CONFLICT" in text or "conflict" in text.lower()
    assert "LLM ≠ authority" in text or "LLM ≠ AUTHORITY" in text
    assert "derived" in text.lower()


def test_invariants_document_fail_closed_walls() -> None:
    text = DOCS["invariants"].read_text(encoding="utf-8")
    assert "silent" in text.lower()
    assert "LLM ≠ authority" in text or "LLM ≠ AUTHORITY" in text
    assert "ATLAS_2_1_RELEASE_CERTIFIED" in text
    assert "ATLAS_2_2_INTELLIGENCE_IMPLEMENTATION_UNLOCKED" in text
    assert "NO" in text
    assert "canonical" in text.lower()


def test_complete_slice_cites_all_input_families() -> None:
    payload = _load_json(FIXTURES / "intel-slice-complete.sample.json")
    assert isinstance(payload, dict)
    assert payload["package_id"] == "AS-2.2-INTEL-SLICE-PREP-001"
    assert payload["status"] == "COMPLETE"
    assert payload["authority"]["level"] == "derived"
    assert payload["canonical_write"] is False
    assert payload["evidence_class"] == "fixture-only"
    assert payload["pilot_roots"] == 0
    assert payload["atlas_2_1_release_certified"] is False
    assert payload["atlas_2_2_intelligence_implementation_unlocked"] is False
    assert payload["authentic_estate"] is False
    assert "generated" in payload and "by" in payload["generated"]
    assert "at" not in payload["generated"]
    inputs = payload["inputs"]
    assert isinstance(inputs, dict)
    for family in INPUT_FAMILIES:
        assert family in inputs
        assert isinstance(inputs[family], list)
        assert len(inputs[family]) >= 1
    assert payload["unknown"] == []
    open_conflict = inputs["conflicts"][0]
    assert open_conflict["state"] == "open"


def test_incomplete_slice_retains_unknowns_and_open_conflicts() -> None:
    payload = _load_json(FIXTURES / "intel-slice-incomplete.sample.json")
    assert isinstance(payload, dict)
    assert payload["status"] == "INCOMPLETE"
    assert payload["authority"]["level"] == "derived"
    assert payload["canonical_write"] is False
    assert len(payload["unknown"]) >= 1
    assert any(item.get("code") == "temporal_unresolved" for item in payload["unknown"])
    conflicts = payload["inputs"]["conflicts"]
    assert conflicts and conflicts[0]["state"] == "open"


def test_inputs_citations_are_cite_only() -> None:
    payload = _load_json(FIXTURES / "inputs-citations.sample.json")
    assert isinstance(payload, dict)
    assert payload["package_id"] == "AS-2.2-INTEL-SLICE-PREP-001"
    assert payload["authority"]["level"] == "derived"
    assert payload["canonical_write"] is False
    assert payload["pilot_roots"] == 0
    citations = payload["citations"]
    assert isinstance(citations, list)
    assert len(citations) >= 5
    for row in citations:
        assert row["dual_own_emit"] is False
        assert row["citation_id"]


def test_negative_actions_are_rejected_forbidden() -> None:
    for name, (kind, error) in NEGATIVE_FIXTURES.items():
        payload = _load_json(FIXTURES / name)
        assert isinstance(payload, dict)
        assert payload["package_id"] == "AS-2.2-INTEL-SLICE-PREP-001"
        assert payload["kind"] == kind
        assert payload["status"] == "rejected_forbidden"
        assert payload["expected_error"] == error
        assert payload["authority"]["level"] == "derived"
        assert payload["canonical_write"] is False


def test_fixture_plan_lists_all_payloads() -> None:
    text = DOCS["fixture_plan"].read_text(encoding="utf-8")
    for name in SAMPLE_FIXTURES:
        assert name in text
    for name in NEGATIVE_FIXTURES:
        assert name in text
    assert "Gate credit" in text or "gate credit" in text.lower()
    assert "NO" in text


def test_no_runtime_mutation_in_branch_diff() -> None:
    """Capability-maturity-scoped 2.2 prep guard (D-INTEGRATE-007A).

    Keyed on docs/atlas-2.2/PACKAGE-MATURITY.json: 'intel-slice' must not
    mutate its production surface while prep-frozen; an implementation-
    unlocked capability may legitimately mutate its own surface.
    """
    assert_prep_branch_scope("intel-slice")
