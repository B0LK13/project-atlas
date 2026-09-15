"""D-183 — D-177 demo estate must declare a visible Time Machine succession.

Fixture-only. Does not change production Time Machine / query semantics.
Harbor golden fixture remains the implementation acceptance path.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from project_atlas.temporal_evidence import extract_source_temporal_facts

_ESTATE = Path("fixtures/demo/estate/project-a")


def test_architecture_declares_t1_valid_time() -> None:
    text = (_ESTATE / "ARCHITECTURE.md").read_text(encoding="utf-8")
    facts = extract_source_temporal_facts(
        source_id="demo-architecture",
        path="project-a/ARCHITECTURE.md",
        text=text,
    )
    assert facts.document_timestamp is not None
    assert facts.document_timestamp.date() == date(2024, 1, 15)
    assert "Deployment: PostgreSQL 15" in text


def test_runtime_declares_t2_valid_time() -> None:
    text = (_ESTATE / "src" / "RUNTIME.md").read_text(encoding="utf-8")
    facts = extract_source_temporal_facts(
        source_id="demo-runtime",
        path="project-a/src/RUNTIME.md",
        text=text,
    )
    assert facts.document_timestamp is not None
    assert facts.document_timestamp.date() == date(2024, 8, 20)
    assert "Deployment: PostgreSQL 16" in text
    arch = extract_source_temporal_facts(
        source_id="demo-architecture",
        path="project-a/ARCHITECTURE.md",
        text=(_ESTATE / "ARCHITECTURE.md").read_text(encoding="utf-8"),
    )
    assert arch.document_timestamp is not None
    assert facts.document_timestamp > arch.document_timestamp
