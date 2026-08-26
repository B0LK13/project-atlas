"""D-191 / D-192 program documents exist and classify historical inputs."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ATLAS3 = ROOT / "docs" / "atlas-3"

REQUIRED = (
    "NORTH-STAR.md",
    "ARCHITECTURE.md",
    "MASTER-ROADMAP.md",
    "EPICS.md",
    "DEPENDENCY-DAG.md",
    "MIGRATION-2X-TO-3X.md",
    "PRODUCT-EXPERIENCE.md",
    "COMPETITIVE-POSITIONING.md",
    "ACCEPTANCE.md",
    "FOUNDATION.md",
    "SECURITY.md",
    "chronicle/HORIZON.md",
    "contracts/twin-node.schema.json",
    "contracts/twin-relationship.schema.json",
    "contracts/engineering-event.schema.json",
    "contracts/capability.schema.json",
    "HISTORICAL-INPUTS.md",
    "PACKAGE-MATURITY.json",
    "llm-memory/ARCHITECTURE.md",
    "llm-memory/PROVIDER-CONTRACT.md",
    "llm-memory/NORMALIZATION.md",
    "llm-memory/KNOWLEDGE-EXTRACTION.md",
    "llm-memory/RECONCILIATION.md",
    "llm-memory/PRIVACY.md",
    "llm-memory/SECURITY.md",
    "llm-memory/ACCEPTANCE.md",
    "llm-memory/PROVIDER-MATRIX.md",
)


def test_required_program_documents_exist() -> None:
    missing = [name for name in REQUIRED if not (ATLAS3 / name).is_file()]
    assert missing == []


def test_historical_inputs_not_erased() -> None:
    assert (ROOT / "docs" / "master-roadmap.md").is_file()
    assert (ROOT / "docs" / "implementation-roadmap.md").is_file()
    assert (ROOT / "docs" / "strategy" / "ATLAS-3.0-NORTH-STAR-BACKLOG.md").is_file()
    master = (ROOT / "docs" / "master-roadmap.md").read_text(encoding="utf-8")
    assert "historical input" in master.lower()
    impl = (ROOT / "docs" / "implementation-roadmap.md").read_text(encoding="utf-8")
    assert "historical input" in impl.lower()


def test_north_star_promises_and_stack() -> None:
    text = (ATLAS3 / "NORTH-STAR.md").read_text(encoding="utf-8")
    assert "NEVER EXPLAIN YOUR PROJECT TO AN AI TWICE" in text.upper() or "Never explain" in text
    assert "EVIDENCE" in text
    assert "AUTONOMY" in text
    assert "FULL_LIVE_DEMO_READY" in text
    assert "NOT_GRANTED" in text
    foundation = (ATLAS3 / "FOUNDATION.md").read_text(encoding="utf-8")
    assert "NO duplicated truth engines" in foundation
    assert "AT3-001" in foundation
    assert "ROADMAP_HORIZON" in (ATLAS3 / "chronicle" / "HORIZON.md").read_text(encoding="utf-8")


def test_epics_count_and_first_vertical() -> None:
    text = (ATLAS3 / "EPICS.md").read_text(encoding="utf-8")
    assert "AT3-003" in text
    assert "AT3-014" in text
    assert "AT3-015" in text
    assert "AT3-030" in text
    assert "AT3-050" in text
    assert "64" in text
    for package in range(35, 50):
        assert f"AT3-0{package}" in text


def test_package_maturity_denies_demo_mutation() -> None:
    data = json.loads((ATLAS3 / "PACKAGE-MATURITY.json").read_text(encoding="utf-8"))
    assert data["gates"]["FULL_LIVE_DEMO_READY"] == "NO"
    assert data["gates"]["MERGE_AUTHORIZATION"] == "NOT_GRANTED"
    frozen = data["packages"]["chatgpt-live-2x"]
    assert "src/project_atlas/chatgpt_bridge.py" in frozen["production_surface"]


def test_llm_memory_does_not_claim_native_history_sync() -> None:
    matrix = (ATLAS3 / "llm-memory" / "PROVIDER-MATRIX.md").read_text(encoding="utf-8")
    assert "NOT IMPLEMENTED" in matrix or "Not implemented" in matrix
    assert "CLAUDE.md" in matrix
    arch = (ATLAS3 / "llm-memory" / "ARCHITECTURE.md").read_text(encoding="utf-8")
    assert "NOT A GENERAL CORE CAPABILITY" in arch or "NOT IMPLEMENTED" in arch
