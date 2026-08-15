"""AS-CODER-ALPHA-CONTEXT-FRESHNESS-ADV-001 — adversarial freshness regressions."""

from __future__ import annotations

import json
from pathlib import Path

from project_atlas.context_freshness_adv import (
    PACKAGE_ID,
    ContextSnapshot,
    DecisionSnapshot,
    GeneratedAnswer,
    QuarantineCapture,
    SourceSnapshot,
    assess_freshness,
    assess_reconnect_honesty,
    invariants_hold,
    report_as_dict,
    sha256_text,
    write_freshness_receipt,
)

HARBOR_API = "harbor-api"
HARBOR_PORTAL = "harbor-portal"


def _src(
    path: str,
    text: str,
    *,
    project_id: str = HARBOR_API,
    exists: bool = True,
) -> SourceSnapshot:
    return SourceSnapshot(
        path=path,
        project_id=project_id,
        sha256=sha256_text(text) if exists else None,
        exists=exists,
        text=text if exists else None,
    )


def _gov(status: str, decision_id: str = "ADR-001") -> DecisionSnapshot:
    return DecisionSnapshot(
        decision_id=decision_id,
        status=status,
        title="Select relational database",
        project_id=HARBOR_API,
    )


def test_clean_snapshot_has_zero_invariant_violations() -> None:
    source = _src("docs/ADR-001-database.md", "Accepted. Use PostgreSQL 15.")
    snap = ContextSnapshot(
        project_id=HARBOR_API,
        sources=(source,),
        decisions=(_gov("ACTIVE_GOVERNING"),),
        slot_texts={"governing_decisions": "ADR-001 PostgreSQL 15"},
        claims_material_change=False,
    )
    report = assess_freshness(snap, snap, case_id="clean")
    inv = invariants_hold(report, expect_stale=False)
    assert inv["STALE_CONTEXT_FALSE_NEGATIVE"] == 0
    assert inv["CROSS_PROJECT_LEAK_COUNT"] == 0
    assert inv["SUPERSEDED_AS_GOVERNING"] == 0
    assert inv["UNKNOWN_SUPPRESSION"] == 0
    assert inv["SECRET_ECHO"] == 0
    assert report.findings == ()


def test_governing_decision_becomes_superseded() -> None:
    source = _src("docs/ADR-001-database.md", "Accepted. Use PostgreSQL 15.")
    frozen = ContextSnapshot(
        project_id=HARBOR_API,
        sources=(source,),
        decisions=(_gov("ACTIVE_GOVERNING"),),
        slot_texts={"governing_decisions": "ADR-001 is governing"},
    )
    current = ContextSnapshot(
        project_id=HARBOR_API,
        sources=(source,),
        decisions=(_gov("SUPERSEDED"),),
        slot_texts={"governing_decisions": "ADR-001 superseded"},
    )
    report = assess_freshness(frozen, current, case_id="governing_superseded")
    assert any(item.kind == "superseded_as_governing" for item in report.findings)
    assert report.superseded_as_governing == 1
    assert invariants_hold(report, expect_stale=True)["STALE_CONTEXT_FALSE_NEGATIVE"] == 0


def test_source_deleted_after_context_generation() -> None:
    frozen = ContextSnapshot(
        project_id=HARBOR_API,
        sources=(_src("docs/ADR-001-database.md", "Accepted"),),
        slot_texts={"supporting_evidence": "docs/ADR-001-database.md"},
    )
    current = ContextSnapshot(
        project_id=HARBOR_API,
        sources=(
            _src("docs/ADR-001-database.md", "Accepted", exists=False),
        ),
        slot_texts={},
    )
    report = assess_freshness(frozen, current, case_id="source_deleted")
    assert any(item.kind == "stale_source" for item in report.findings)
    assert invariants_hold(report, expect_stale=True)["STALE_CONTEXT_FALSE_NEGATIVE"] == 0


def test_source_modified_after_handoff() -> None:
    frozen = ContextSnapshot(
        project_id=HARBOR_API,
        sources=(_src("src/RUNTIME.md", "runtime: PostgreSQL 16"),),
        slot_texts={"current_state": "PostgreSQL 16"},
    )
    current = ContextSnapshot(
        project_id=HARBOR_API,
        sources=(_src("src/RUNTIME.md", "runtime: PostgreSQL 17"),),
        slot_texts={"current_state": "PostgreSQL 16"},
    )
    report = assess_freshness(frozen, current, case_id="source_modified")
    assert any(item.kind == "stale_source" for item in report.findings)
    assert invariants_hold(report, expect_stale=True)["STALE_CONTEXT_FALSE_NEGATIVE"] == 0


def test_conflicting_source_introduced() -> None:
    frozen = ContextSnapshot(
        project_id=HARBOR_API,
        sources=(_src("ARCHITECTURE.md", "Use PostgreSQL 15"),),
        slot_texts={"current_state": "PostgreSQL 15"},
    )
    current = ContextSnapshot(
        project_id=HARBOR_API,
        sources=(
            _src("ARCHITECTURE.md", "Use PostgreSQL 15"),
            _src("src/RUNTIME.md", "conflict: runtime pins PostgreSQL 16"),
        ),
        slot_texts={"current_state": "PostgreSQL 15 vs 16 conflict"},
    )
    report = assess_freshness(frozen, current, case_id="conflict_introduced")
    assert any(item.kind == "missing_conflict" for item in report.findings)
    assert invariants_hold(report, expect_stale=True)["STALE_CONTEXT_FALSE_NEGATIVE"] == 0


def test_source_health_failure_introduced() -> None:
    frozen = ContextSnapshot(
        project_id=HARBOR_API,
        sources=(_src("README.md", "Harbor API"),),
        source_health_failures=(),
        slot_texts={"source_health": "source_count=1"},
    )
    current = ContextSnapshot(
        project_id=HARBOR_API,
        sources=(_src("README.md", "Harbor API"),),
        source_health_failures=("secrets/.env",),
        slot_texts={"source_health": "FAILED secrets/.env"},
    )
    report = assess_freshness(frozen, current, case_id="source_health_failure")
    assert any(item.kind == "source_health_gap" for item in report.findings)
    assert invariants_hold(report, expect_stale=True)["STALE_CONTEXT_FALSE_NEGATIVE"] == 0


def test_shared_filenames_do_not_leak_when_scoped() -> None:
    frozen = ContextSnapshot(
        project_id=HARBOR_API,
        sources=(_src("README.md", "Harbor API DEMO FIXTURE"),),
        slot_texts={"identity": "Harbor API DEMO FIXTURE"},
    )
    report = assess_freshness(
        frozen,
        frozen,
        sibling_tokens={
            HARBOR_PORTAL: ("Harbor Portal tenant list", "API key header"),
        },
        case_id="shared_filenames_clean",
    )
    assert report.cross_project_leak_count == 0
    assert invariants_hold(report, expect_stale=False)["CROSS_PROJECT_LEAK_COUNT"] == 0


def test_shared_filenames_detect_cross_project_leak() -> None:
    frozen = ContextSnapshot(
        project_id=HARBOR_API,
        sources=(_src("README.md", "Harbor API and Harbor Portal tenant list"),),
        slot_texts={"identity": "Harbor API and Harbor Portal tenant list"},
    )
    report = assess_freshness(
        frozen,
        frozen,
        sibling_tokens={HARBOR_PORTAL: ("Harbor Portal tenant list",)},
        case_id="shared_filenames_leak",
    )
    assert report.cross_project_leak_count == 1
    assert any(item.kind == "cross_project_leak" for item in report.findings)


def test_quarantined_capture_references_other_project() -> None:
    frozen = ContextSnapshot(
        project_id=HARBOR_API,
        sources=(_src("README.md", "Harbor API"),),
        slot_texts={"identity": "Harbor API"},
        quarantined_captures=(
            QuarantineCapture(
                capture_id="cap-portal",
                project_id=HARBOR_API,
                referenced_project_id=HARBOR_PORTAL,
                included_in_pack=True,
                text="see harbor-portal auth header",
            ),
        ),
    )
    report = assess_freshness(frozen, frozen, case_id="quarantine_other_project")
    assert report.cross_project_leak_count == 1
    assert "quarantined_capture_other_project" in report.covered_cases


def test_stale_generated_answer_detected() -> None:
    frozen = ContextSnapshot(
        project_id=HARBOR_API,
        generated_answers=(
            GeneratedAnswer(
                answer_id="ans-state-harbor-api",
                project_id=HARBOR_API,
                source_path="ARCHITECTURE.md",
                source_sha256=sha256_text("PostgreSQL 15"),
                parse_status="ok",
            ),
        ),
    )
    current = ContextSnapshot(
        project_id=HARBOR_API,
        generated_answers=(
            GeneratedAnswer(
                answer_id="ans-state-harbor-api",
                project_id=HARBOR_API,
                source_path="ARCHITECTURE.md",
                source_sha256=sha256_text("PostgreSQL 16"),
                parse_status="ok",
            ),
        ),
    )
    report = assess_freshness(frozen, current, case_id="stale_generated_answer")
    assert any(item.kind == "stale_generated_answer" for item in report.findings)
    assert invariants_hold(report, expect_stale=True)["STALE_CONTEXT_FALSE_NEGATIVE"] == 0


def test_malformed_generated_artifact_does_not_suppress_unknown() -> None:
    frozen = ContextSnapshot(
        project_id=HARBOR_API,
        claims_all_healthy=True,
        generated_answers=(
            GeneratedAnswer(
                answer_id="ans-broken",
                project_id=HARBOR_API,
                source_path="generated/answers/ans-broken.json",
                source_sha256=None,
                parse_status="ok",
                claims_healthy=True,
            ),
        ),
    )
    current = ContextSnapshot(
        project_id=HARBOR_API,
        generated_answers=(
            GeneratedAnswer(
                answer_id="ans-broken",
                project_id=HARBOR_API,
                source_path="generated/answers/ans-broken.json",
                source_sha256=None,
                parse_status="malformed",
                claims_healthy=True,
            ),
        ),
    )
    report = assess_freshness(frozen, current, case_id="malformed_artifact")
    kinds = {item.kind for item in report.findings}
    assert "malformed_artifact" in kinds
    assert "unknown_suppression" in kinds
    assert report.unknown_suppression == 1


def test_secret_echo_is_detected() -> None:
    frozen = ContextSnapshot(
        project_id=HARBOR_API,
        slot_texts={
            "current_state": "api_key = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ012345'",
        },
    )
    report = assess_freshness(frozen, frozen, case_id="secret_echo")
    assert report.secret_echo == 1
    assert any(item.kind == "secret_echo" for item in report.findings)


def test_no_change_reconnect_pass_when_fingerprints_match() -> None:
    source = _src("README.md", "Harbor API unchanged")
    before = ContextSnapshot(
        project_id=HARBOR_API,
        sources=(source,),
        claims_material_change=False,
    )
    after = ContextSnapshot(
        project_id=HARBOR_API,
        sources=(source,),
        claims_material_change=False,
    )
    assert assess_reconnect_honesty(before, after) == "PASS"
    report = assess_freshness(before, after, case_id="reconnect_pass")
    assert report.reconnect_honesty == "PASS"


def test_no_change_reconnect_fails_false_change_claim() -> None:
    source = _src("README.md", "Harbor API unchanged")
    before = ContextSnapshot(
        project_id=HARBOR_API,
        sources=(source,),
        claims_material_change=False,
    )
    after = ContextSnapshot(
        project_id=HARBOR_API,
        sources=(source,),
        claims_material_change=True,
    )
    assert assess_reconnect_honesty(before, after) == "FAIL"
    report = assess_freshness(before, after, case_id="reconnect_false_change")
    assert report.reconnect_honesty == "FAIL"
    assert any(item.kind == "false_change_claim" for item in report.findings)


def test_no_change_reconnect_unknown_without_fingerprints() -> None:
    before = ContextSnapshot(project_id=HARBOR_API, sources=())
    after = ContextSnapshot(
        project_id=HARBOR_API,
        sources=(),
        claims_material_change=False,
    )
    assert assess_reconnect_honesty(before, after) == "UNKNOWN"
    report = assess_freshness(before, after, case_id="reconnect_unknown")
    assert report.reconnect_honesty == "UNKNOWN"
    assert "no_change_reconnect_unknown" in report.covered_cases
    # Explicit: we do not rewrite connect.py and we do not fake PASS.


def test_receipt_is_deterministic_and_non_authoritative(tmp_path: Path) -> None:
    source = _src("README.md", "Harbor API")
    snap = ContextSnapshot(
        project_id=HARBOR_API,
        sources=(source,),
        claims_material_change=False,
    )
    report = assess_freshness(snap, snap, case_id="receipt")
    first = report_as_dict(report)
    second = report_as_dict(report)
    assert first == second
    assert first["package_id"] == PACKAGE_ID
    assert "generated_at" not in first
    path = write_freshness_receipt(tmp_path, report)
    again = write_freshness_receipt(tmp_path, report)
    assert path.read_bytes() == again.read_bytes()
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["honesty"]["connect_py_rewritten"] is False
    assert payload["honesty"]["authentic_pilot"] is False
