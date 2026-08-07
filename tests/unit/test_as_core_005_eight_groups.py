"""AS-CORE-005: eight real conflict-group temporal acceptance fixtures."""

from __future__ import annotations

import hashlib
from pathlib import Path

from project_atlas.domain.conflicts import ConflictState
from project_atlas.domain.temporal import ResolutionBasis, TemporalStatus
from project_atlas.knowledge_compiler import compile_knowledge

_FIXTURE_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "as-core-005" / "real-sources"


def _sid(path: str) -> str:
    digest = hashlib.sha256(path.encode("utf-8")).hexdigest()[:16]
    return f"source-{digest}"


def _entry(rel_path: str, classification: str = "validation") -> dict:
    # Vendored as docs__evidence__FILE or docs__plan.md
    key = rel_path.replace("/", "__")
    text = (_FIXTURE_DIR / key).read_text(encoding="utf-8")
    sha = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return {
        "source_id": _sid(rel_path),
        "path": rel_path,
        "classification": classification,
        "source": f"../../sources/imported-documents/{_sid(rel_path)}.md",
        "sha256": sha,
        "text": text,
    }


def _bundle(tmp_path: Path):
    entries = [
        _entry("docs/plan.md", "architecture"),
        _entry("docs/evidence/AS-CORE-002-post-merge-receipt.yaml"),
        _entry("docs/evidence/AS-CORE-002-source-lifecycle-recertification.yaml"),
        _entry("docs/evidence/AS-CORE-003-claim-identity-amendment-plan.yaml"),
        _entry("docs/evidence/AS-CORE-003-receipt.yaml"),
        _entry("docs/evidence/AS-CORE-003-v2-candidate-003.yaml"),
        _entry("docs/evidence/AS-CORE-003-v2-candidate-003-review.yaml"),
        _entry("docs/evidence/AS-CORE-003-v2-candidate-004.yaml"),
        _entry("docs/evidence/AS-CORE-003-v2-candidate-005.yaml"),
        _entry("docs/evidence/AS-CORE-003-v2-candidate-005-review.yaml"),
        _entry("docs/evidence/AS-CORE-003-v2-candidate-006.yaml"),
        _entry("docs/evidence/AS-CORE-003-v2-candidate-006-review-addendum.yaml"),
        _entry("docs/evidence/AS-CORE-003-v2-remediation-receipt.yaml"),
        _entry("docs/evidence/AS-ID-001-receipt.yaml"),
        _entry("docs/evidence/AS-ID-001-governor-remediation-receipt.yaml"),
        _entry("docs/evidence/AS-ID-001-final-certification-remediation-receipt.yaml"),
        _entry("docs/evidence/AS-ID-001-retired-slot-resolution-wiring-receipt.yaml"),
        _entry("docs/evidence/AS-RET-001-receipt.yaml"),
        _entry("docs/evidence/AS-RET-001-post-merge-receipt.yaml"),
        _entry("docs/evidence/AS-SEC-001-certification-carry-forward.yaml"),
        _entry("docs/evidence/AS-SEC-001-post-merge-validation.yaml"),
    ]
    return compile_knowledge("project-atlas", entries, tmp_path)


def _disp(bundle, subject: str, field: str):
    matches = [d for d in bundle.current_states if d.subject == subject and d.field == field]
    assert matches, f"missing disposition for {subject}/{field}"
    return matches[0]


def _conflict(bundle, subject: str, field: str):
    matches = [c for c in bundle.conflicts if c.subject == subject and c.field == field]
    assert matches, f"missing conflict for {subject}/{field}"
    return matches[0]


def test_eight_group_temporal_matrix(tmp_path: Path) -> None:
    bundle = _bundle(tmp_path)
    # Claims immutable: still present after temporal evaluation
    assert len(bundle.claims) >= 20

    # 1) plan.md roadmap — must remain unresolved (non-temporal)
    d = _disp(bundle, f"doc:{_sid('docs/plan.md')}", "roadmap")
    assert d.temporal_status is TemporalStatus.UNRESOLVED
    assert d.current_claim_id is None
    assert d.resolution_basis is ResolutionBasis.UNRESOLVED_SAME_SOURCE_MULTI
    c = _conflict(bundle, d.subject, "roadmap")
    assert c.state is ConflictState.UNRESOLVED

    # 2) AS-CORE-002 package_status
    d = _disp(bundle, "wp:AS-CORE-002", "package_status")
    assert d.temporal_status is TemporalStatus.CURRENT
    assert d.current_claim_id is not None
    current_val = next(cl.value for cl in bundle.claims if cl.claim_id == d.current_claim_id)
    assert current_val == "recertified-merge-eligible"
    assert "certified" in {
        cl.value for cl in bundle.claims if cl.claim_id in d.historical_claim_ids
    }
    assert _conflict(bundle, "wp:AS-CORE-002", "package_status").state is ConflictState.RESOLVED

    # 3) AS-CORE-003 package_status
    d = _disp(bundle, "wp:AS-CORE-003", "package_status")
    assert d.temporal_status is TemporalStatus.CURRENT
    current_val = next(cl.value for cl in bundle.claims if cl.claim_id == d.current_claim_id)
    assert current_val in {
        "local-validation-complete-pending-remote-ci",
        "local-validation-complete-pending-isolated-review",
    }
    # Tip must be the V2-006 (or highest evidenced candidate) status, not Planned
    assert current_val != "Planned"
    assert d.historical_claim_ids
    assert _conflict(bundle, "wp:AS-CORE-003", "package_status").state is ConflictState.RESOLVED

    # 4) AS-CORE-003 work-package id
    d = _disp(bundle, "wp:AS-CORE-003", "work-package")
    assert d.temporal_status is TemporalStatus.CURRENT
    current_val = next(cl.value for cl in bundle.claims if cl.claim_id == d.current_claim_id)
    assert current_val == "AS-CORE-003"
    hist_vals = {cl.value for cl in bundle.claims if cl.claim_id in d.historical_claim_ids}
    assert "AS-CORE-003-A" in hist_vals
    assert _conflict(bundle, "wp:AS-CORE-003", "work-package").state is ConflictState.RESOLVED

    # 5) AS-ID-001 package_status
    d = _disp(bundle, "wp:AS-ID-001", "package_status")
    assert d.temporal_status is TemporalStatus.CURRENT
    current_val = next(cl.value for cl in bundle.claims if cl.claim_id == d.current_claim_id)
    assert current_val == "implementation-complete-targeted-rereview-required"
    assert _conflict(bundle, "wp:AS-ID-001", "package_status").state is ConflictState.RESOLVED

    # 6) AS-ID-001 title — mandatory latest-wins rejection
    d = _disp(bundle, "wp:AS-ID-001", "title")
    assert d.temporal_status is TemporalStatus.AUTHORITY_PENDING
    assert d.current_claim_id is None
    assert d.resolution_basis is ResolutionBasis.TITLE_COLLAPSE
    assert "newest observation does not imply current truth" in d.rationale
    assert _conflict(bundle, "wp:AS-ID-001", "title").state is ConflictState.UNRESOLVED

    # 7) AS-RET-001
    d = _disp(bundle, "wp:AS-RET-001", "package_status")
    assert d.temporal_status is TemporalStatus.CURRENT
    current_val = next(cl.value for cl in bundle.claims if cl.claim_id == d.current_claim_id)
    assert current_val == "merged-and-post-merge-validated"
    assert _conflict(bundle, "wp:AS-RET-001", "package_status").state is ConflictState.RESOLVED

    # 8) AS-SEC-001
    d = _disp(bundle, "wp:AS-SEC-001", "package_status")
    assert d.temporal_status is TemporalStatus.CURRENT
    current_val = next(cl.value for cl in bundle.claims if cl.claim_id == d.current_claim_id)
    assert current_val == "merged-post-merge-validated"
    assert _conflict(bundle, "wp:AS-SEC-001", "package_status").state is ConflictState.RESOLVED

    # Aggregate acceptance
    resolved = [
        d
        for d in bundle.current_states
        if d.temporal_status is TemporalStatus.CURRENT and d.historical_claim_ids
    ]
    assert len(resolved) >= 6
    # Historical claims still in claim set
    for d in resolved:
        for hid in d.historical_claim_ids:
            assert any(cl.claim_id == hid for cl in bundle.claims)


def test_deterministic_replay_eight_groups(tmp_path: Path) -> None:
    a = _bundle(tmp_path / "a")
    b = _bundle(tmp_path / "b")
    assert [d.model_dump(mode="json") for d in a.current_states] == [
        d.model_dump(mode="json") for d in b.current_states
    ]
    assert [c.model_dump(mode="json") for c in a.conflicts] == [
        c.model_dump(mode="json") for c in b.conflicts
    ]
    assert sorted(cl.claim_id for cl in a.claims) == sorted(cl.claim_id for cl in b.claims)


def test_idempotent_recompilation_unchanged_claims(tmp_path: Path) -> None:
    first = _bundle(tmp_path / "first")
    # Second compilation into a fresh vault must not mutate claim identities
    # or erase historically superseded claim records.
    second = _bundle(tmp_path / "second")
    assert first.compilation_id == second.compilation_id
    assert {cl.claim_id for cl in first.claims} == {cl.claim_id for cl in second.claims}
    for d in first.current_states:
        if d.historical_claim_ids:
            for hid in d.historical_claim_ids:
                assert any(cl.claim_id == hid for cl in first.claims)
                assert any(cl.claim_id == hid for cl in second.claims)


def test_historical_discoverability_after_resolution(tmp_path: Path) -> None:
    bundle = _bundle(tmp_path)
    resolved = [
        d
        for d in bundle.current_states
        if d.temporal_status is TemporalStatus.CURRENT and d.historical_claim_ids
    ]
    assert len(resolved) >= 6
    for d in resolved:
        assert d.current_claim_id is not None
        assert d.rationale
        assert d.resolution_basis is not None
        # Historical claims remain addressable in the immutable claim set
        for hid in d.historical_claim_ids:
            hist = next(cl for cl in bundle.claims if cl.claim_id == hid)
            assert hist.value
            assert hist.claim_id != d.current_claim_id
