"""Tests for shared Claim Identity v2 primitives (AS-CORE-003)."""

from __future__ import annotations

import pytest

from project_atlas.claim_identity import (
    canonical_identity_key,
    claim_id_from_key,
    extract_claims,
    v2_claim_id,
)
from project_atlas.knowledge_compiler import _extract
from project_atlas.migrations.claim_v2_migration import _extract_candidates, _v2_claim_id


def test_canonical_identity_key_avoids_delimiter_collision() -> None:
    """F-001: embedded delimiters in components cannot produce the same key."""
    key_a = canonical_identity_key("a|b", "c", "purpose", "field", "loc")
    key_b = canonical_identity_key("a", "b|c", "purpose", "field", "loc")
    assert key_a != key_b
    assert key_a == canonical_identity_key("a|b", "c", "purpose", "field", "loc")


def test_canonical_identity_key_handles_unicode_and_whitespace() -> None:
    key = canonical_identity_key("pr\u00f6ject", "s\u00f6urce", "type", "f\u00efeld", "l\u00f2c")
    parsed = key
    assert parsed.startswith("[\"v2\"")
    assert claim_id_from_key(key).startswith("claim-")


def test_canonical_identity_key_empty_field_is_distinct() -> None:
    key_empty = canonical_identity_key("p", "s", "t", "", "loc")
    key_missing = canonical_identity_key("p", "s", "t", "field", "loc")
    assert key_empty != key_missing


@pytest.mark.parametrize(
    ("project", "source", "claim_type", "field", "locator"),
    [
        ("p|a", "s", "type", "field", "loc"),
        ("p", "s|a", "type", "field", "loc"),
        ("p", "s", "ty|pe", "field", "loc"),
        ("p", "s", "type", "fi|eld", "loc"),
        ("p", "s", "type", "field", "lo|c"),
    ],
)
def test_identity_components_can_contain_pipe(
    project: str, source: str, claim_type: str, field: str, locator: str
) -> None:
    """F-001 regression: every component may legally contain a pipe."""
    key = canonical_identity_key(project, source, claim_type, field, locator)
    assert claim_id_from_key(key).startswith("claim-")


def test_compiler_and_migration_v2_claim_ids_match() -> None:
    """Rule parity: identical inputs produce identical v2 claim ids."""
    compiler_id = v2_claim_id(
        "project-uuid",
        "sline-abc123",
        "purpose",
        "purpose",
        "heading:overview",
    )
    migration_id = _v2_claim_id(
        "project-uuid",
        "sline-abc123",
        "purpose",
        "purpose",
        "heading:overview",
    )
    assert compiler_id == migration_id


def test_extract_claims_agrees_between_compiler_and_migration() -> None:
    """Rule parity: compiler and migration consume the same parsed candidates."""
    text = (
        "# Overview\n\n"
        "purpose: test project\n\n"
        "requires: nebula {#dep1}\n\n"
        "roadmap: active\n"
    )
    compiler_claims = _extract(
        "project",
        {
            "source_id": "source",
            "source_lineage_id": "sline-test",
            "path": "source.md",
            "classification": "project-overview",
            "source": "../../sources/imported-documents/source.md",
            "sha256": "0" * 64,
            "text": text,
        },
    )
    migration_claims = _extract_candidates(
        "project", {"source.md": "sline-test"}, "commit", "source.md", text
    )
    assert len(compiler_claims) == len(migration_claims) == 3
    for a, b in zip(compiler_claims, migration_claims, strict=False):
        assert a.claim_id == b.v2_claim_id
        assert a.claim_type.value == b.claim_type
        assert a.field == b.field
        assert a.extraction_method == f"semantic-locator:{b.stable_semantic_locator}"


def test_extract_claims_explicit_id_takes_precedence() -> None:
    text = "# Overview\n\npurpose: test {#explicit-purpose}\n"
    claims = extract_claims(text)
    assert len(claims) == 1
    assert claims[0]["locator"] == "id:explicit-purpose"
    assert claims[0]["value"] == "test"
