"""AS-ORIGIN-001 -- generic acceptance against the real Atlas-Demo showcase
estates (Phase 2A-1 directive Sec 8).

External dependency: ``D:/Atlas-Demo/estates/atlas-showcase-{gamma,alpha,
beta}``, a separate, owner-governed reference checkout. Strictly read-only:
every test here copies an estate's content into ``tmp_path`` before running
the real ingest pipeline against the copy; nothing is ever written back into
``D:/Atlas-Demo``. Automatically skipped when that path is not present (a
different machine, or a CI runner without the demo estates mounted).

``project_atlas.orchestration.origination`` contains zero Gamma/TASK-017/
Alpha/Beta-specific code anywhere in its production-path logic (directive
Sec 3/8): ``run_origination()`` below is the exact same generic function
called for all three estates.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from project_atlas.cli import EXIT_OK, main
from project_atlas.domain import (
    AuthorityLevel,
    Claim,
    ClaimLifecycle,
    ClaimType,
    ConfidenceState,
    ProvenanceReference,
    ReviewState,
)
from project_atlas.orchestration import origination as orig

ESTATES_ROOT = Path("D:/Atlas-Demo/estates")

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not ESTATES_ROOT.is_dir(),
        reason="D:/Atlas-Demo showcase estates are not present on this machine",
    ),
]


def _copy_estate(name: str, dest: Path) -> Path:
    source = ESTATES_ROOT / name
    shutil.copytree(source, dest, ignore=shutil.ignore_patterns(".git"))
    return dest


def _run_real_pipeline(tmp_path: Path, estate_name: str) -> Path:
    """Real `atlas discover`/`ingest`/`build-indexes`/`validate`, exactly as
    a real project would run them, against a throwaway copy of the estate.
    """
    estate = _copy_estate(estate_name, tmp_path / f"{estate_name}-copy")
    vault = tmp_path / f"vault-{estate_name}"
    manifest = tmp_path / f"{estate_name}-manifest.json"
    assert main(["init", "--output", str(vault)]) == EXIT_OK
    assert main(["discover", "--source", str(estate), "--output", str(manifest)]) == EXIT_OK
    assert (
        main(
            [
                "ingest",
                "--manifest",
                str(manifest),
                "--vault",
                str(vault),
                "--source",
                str(estate),
            ]
        )
        == EXIT_OK
    )
    assert main(["build-indexes", "--vault", str(vault)]) == EXIT_OK
    assert main(["validate", "--vault", str(vault)]) == EXIT_OK
    return vault


@pytest.mark.parametrize(
    "estate_name",
    ["atlas-showcase-alpha", "atlas-showcase-beta"],
)
def test_no_spurious_origination_on_estates_without_the_evidence_pattern(
    tmp_path: Path, estate_name: str
) -> None:
    """Negative acceptance (directive Sec 8 step 4): Alpha/Beta carry no
    unimplemented-and-specified work-item evidence pattern, so the generic
    origination pipeline -- with zero estate-specific code -- must propose
    nothing, even though real ingest does produce real evidence for them.
    """
    vault = _run_real_pipeline(tmp_path, estate_name)
    claims = orig.load_project_claims(vault, estate_name)
    assert claims, "real ingest should still produce *some* evidence for this estate"
    result = orig.run_origination(vault, estate_name)
    assert result is None
    assert not (vault / "projects" / estate_name / "roadmap.md").is_file()


def test_gamma_real_ingest_currently_yields_no_origination_quorum(tmp_path: Path) -> None:
    """Real, executed finding against Gamma -- reported honestly, not
    asserted to be a particular outcome in advance.

    With the *current, unmodified* deterministic extractor
    (``claim_identity.extract_claims``'s ``_LINE_RULES``), real
    ``atlas ingest`` against Gamma's prose ``docs/ROADMAP.md`` and
    ``docs/REQUIREMENTS.md`` produces zero ROADMAP_STATUS/WORK_PACKAGE_
    STATUS/TEST_RESULT claims naming TASK-017: the line rules require
    literal ``key: value`` syntax (e.g. ``Status: ...``) and both files are
    prose. ``docs/adr/ADR-0002-...md`` does contribute one claim (via the
    architecture-fallback rule), but as an ARCHITECTURE claim, not an
    intent/acceptance-eligible one. Verified directly against the real
    ``state/claims/atlas-showcase-gamma.json`` this pipeline writes -- see
    the session report for the full root-cause trace.

    This is the correct, fail-closed behavior of ``run_origination()``
    given that real evidence -- not a defect in this module -- and is
    flagged in the report as an open question for owner input about
    extraction richness, rather than being silently special-cased here.
    """
    vault = _run_real_pipeline(tmp_path, "atlas-showcase-gamma")
    claims = orig.load_project_claims(vault, "atlas-showcase-gamma")
    assert claims, "real ingest should still produce *some* evidence for Gamma"
    assert not any(
        claim.claim_type
        in (ClaimType.ROADMAP_STATUS, ClaimType.WORK_PACKAGE_STATUS, ClaimType.TEST_RESULT)
        and "TASK-017" in claim.value
        for claim in claims
    )
    result = orig.run_origination(vault, "atlas-showcase-gamma")
    assert result is None
    assert not (vault / "projects" / "atlas-showcase-gamma" / "roadmap.md").is_file()


def test_origination_logic_recognizes_gammas_task_017_evidence_when_structured(
    tmp_path: Path,
) -> None:
    """Supplementary, clearly-labeled proof that ``run_origination()``'s own
    policy logic -- fully generic, no TASK-017/Gamma string anywhere in
    ``origination.py``'s production path -- correctly recognizes Gamma's
    real TASK-017 evidence quorum once that evidence exists as structured
    claims (i.e. what a richer extractor would need to produce from these
    same real files). The corroborating claim's value is the real,
    verbatim skip reason read out of the real copied test file; the
    intent claim's status value is a normalized restatement of
    ``docs/ROADMAP.md``'s real "Next (specified, not implemented)" section
    into the one vocabulary token ``project_roadmap._normalize_status``
    understands (raw prose can never match that normalizer directly -- see
    the report).

    This test does **not** assert that unmodified ``atlas ingest`` produces
    these claims today; the previous test is the honest negative finding
    for that question.
    """
    estate = _copy_estate("atlas-showcase-gamma", tmp_path / "gamma-copy")
    roadmap_text = (estate / "docs" / "ROADMAP.md").read_text(encoding="utf-8")
    test_spec_text = (estate / "tests" / "test_task_017_dependency_validation.py").read_text(
        encoding="utf-8"
    )
    assert "TASK-017" in roadmap_text
    assert "pytest.mark.skip" in test_spec_text

    roadmap_line = next(
        line.strip("- ").strip()
        for line in roadmap_text.splitlines()
        if "TASK-017" in line and "dependency validation" in line
    )
    skip_reason = " ".join(
        line.strip().strip('"')
        for line in test_spec_text.splitlines()
        if "TASK-017 not yet implemented" in line or "and docs/REQUIREMENTS.md" in line
    ).strip()
    assert "TASK-017" in roadmap_line
    assert "TASK-017 not yet implemented" in skip_reason

    def _claim(
        claim_id: str, claim_type: ClaimType, field: str, value: str, resource: str, locator: str
    ) -> Claim:
        return Claim(
            claim_id=claim_id,
            project_id="atlas-showcase-gamma",
            subject="wp:TASK-017",
            claim_type=claim_type,
            field=field,
            value=value,
            provenance=[
                ProvenanceReference(source_id="src-1", resource=resource, locator=locator)
            ],
            authority=AuthorityLevel.MAINTAINED,
            confidence=ConfidenceState.HIGH,
            lifecycle=ClaimLifecycle.NEW,
            verification=ReviewState.UNREVIEWED,
        )

    claims = [
        _claim(
            "claim-gamma-intent",
            ClaimType.ROADMAP_STATUS,
            "status",
            "planned",  # normalized restatement of the real "Next (specified,
            # not implemented)" section -- see docstring above.
            "docs/ROADMAP.md",
            "heading:next-specified-not-implemented",
        ),
        _claim(
            "claim-gamma-accept",
            ClaimType.TEST_RESULT,
            "validation",
            skip_reason,  # the real, verbatim skip reason from the real file
            "tests/test_task_017_dependency_validation.py",
            "heading:test-task-017-dependency-validation",
        ),
    ]
    vault = tmp_path / "vault-structured"
    (vault / "projects" / "atlas-showcase-gamma").mkdir(parents=True)
    claims_dir = vault / "state" / "claims"
    claims_dir.mkdir(parents=True)
    (claims_dir / "atlas-showcase-gamma.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "project_id": "atlas-showcase-gamma",
                "claims": [c.model_dump(mode="json") for c in claims],
            }
        ),
        encoding="utf-8",
    )

    result = orig.run_origination(vault, "atlas-showcase-gamma")
    assert result is not None
    assert result.status == "VALID"
    assert result.authority_class == "EXECUTION_READY"
    assert {signal.claim_id for signal in result.source_evidence} == {
        "claim-gamma-intent",
        "claim-gamma-accept",
    }
    assert (vault / "projects" / "atlas-showcase-gamma" / "roadmap.md").is_file()

    # PROVENANCE_SURVIVES_RESTART, exercised once more against real content.
    reloaded = orig.read_origination_proposal(vault, "atlas-showcase-gamma", result.work_id)
    assert reloaded == result
