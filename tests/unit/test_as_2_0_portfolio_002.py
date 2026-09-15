"""AS-2.0-PORTFOLIO-002 — cross-project dependency intelligence."""

from __future__ import annotations

from project_atlas.domain import (
    AuthorityLevel,
    Claim,
    ClaimLifecycle,
    ClaimType,
    ConfidenceState,
    ProvenanceReference,
    ReviewState,
)
from project_atlas.intelligence.portfolio_deps import (
    DependencyClass,
    detect_portfolio_dependencies,
)

HASH_A = "a" * 64


def _claim(
    claim_id: str,
    *,
    project_id: str,
    field: str,
    value: str,
    claim_type: ClaimType = ClaimType.ARCHITECTURE,
) -> Claim:
    return Claim(
        claim_id=claim_id,
        project_id=project_id,
        subject=f"project:{project_id}",
        claim_type=claim_type,
        field=field,
        value=value,
        provenance=[
            ProvenanceReference(source_id="src-a", resource="docs/src-a.md", sha256=HASH_A)
        ],
        authority=AuthorityLevel.PRIMARY,
        confidence=ConfidenceState.HIGH,
        lifecycle=ClaimLifecycle.NEW,
        verification=ReviewState.UNREVIEWED,
    )


def test_explicit_depends_on_is_an_edge() -> None:
    found = detect_portfolio_dependencies(
        {
            "harbor-api": [
                _claim(
                    "dep-1",
                    project_id="harbor-api",
                    field="depends_on",
                    value="lighthouse",
                    claim_type=ClaimType.RUNTIME_DEPENDENCY,
                )
            ],
            "lighthouse": [
                _claim("l1", project_id="lighthouse", field="datastore", value="Redis 7")
            ],
        }
    )
    assert found
    assert found[0].dep_class is DependencyClass.EXPLICIT
    assert found[0].source_project_id == "harbor-api"
    assert found[0].target_project_id == "lighthouse"
    assert found[0].authority_note == "dependency-not-inferred"


def test_shared_datastore_is_not_a_dependency() -> None:
    found = detect_portfolio_dependencies(
        {
            "harbor-api": [
                _claim("h1", project_id="harbor-api", field="datastore", value="PostgreSQL 16")
            ],
            "lighthouse": [
                _claim("l1", project_id="lighthouse", field="datastore", value="PostgreSQL 16")
            ],
        }
    )
    assert found == ()


def test_unknown_target_is_unresolved_not_invented() -> None:
    found = detect_portfolio_dependencies(
        {
            "harbor-api": [
                _claim(
                    "dep-x",
                    project_id="harbor-api",
                    field="depends_on",
                    value="missing-service",
                    claim_type=ClaimType.RUNTIME_DEPENDENCY,
                )
            ]
        }
    )
    assert found
    assert found[0].dep_class is DependencyClass.UNRESOLVED_TARGET
    assert found[0].target_project_id is None
