"""M2: TRUST_MAIN_INTERLOCK -- require_trust_current_for_merge().

Real incidents this formalizes: PR #653 (merged while the persisted trust
anchor was already stale, nothing machine-enforced to stop it) and PR #669
(a genuine 3-way merge the ordinary advancement path of the time could not
represent). Adversarial matrix for the fail-closed precondition, and for
its one narrow, explicit, non-generic exception (``TrustRepairCarrier``).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from project_atlas.orchestration.autonomy.models import (
    CANONICAL_REPOSITORY_IDENTITY,
    AdvancementReason,
    TrustedAnchorRecord,
)
from project_atlas.orchestration.autonomy.trust import (
    FixtureGitObserver,
    MergeGuardError,
    TrustError,
    TrustRepairCarrier,
    initialize_store,
    require_trust_current_for_merge,
    seal_anchor,
)

CURRENT_MAIN = "a" * 40
CURRENT_TREE = "b" * 40
NEXT_MAIN = "c" * 40
NEXT_TREE = "d" * 40
UNRELATED_ROOT = "e" * 40


def _anchor(
    *,
    main: str = CURRENT_MAIN,
    tree: str = CURRENT_TREE,
    identity: str = CANONICAL_REPOSITORY_IDENTITY,
) -> TrustedAnchorRecord:
    return seal_anchor(
        TrustedAnchorRecord(
            repository_identity=identity,
            trusted_main=main,
            trusted_tree=tree,
            predecessor_main=UNRELATED_ROOT,
            predecessor_tree=tree,
            advancement_reason=AdvancementReason.VERIFIED_OWNER_AUTHORIZED_MERGE,
            source_package="AS-ORCH-AUTONOMY-001-PIN-RETARGET",
            source_directive="D-AUTONOMY-PIN-RETARGET-003",
            source_pr=1,
            merge_commit=main,
            merge_parent_1=UNRELATED_ROOT,
            merge_parent_2=main,
            merge_tree=tree,
            certified_head=main,
            certified_tree=tree,
            certification_status="CERTIFIED",
            independent_verification_status="PASS",
            post_merge_seal="PASS",
            post_merge_ci="PASS",
            evidence_reference="tests/fixtures/interlock.json",
            evidence_digest="ab" * 32,
            sequence=1,
            record_digest="00" * 32,
        )
    )


def _topology(
    *, observed_main: str = CURRENT_MAIN, observed_tree: str = CURRENT_TREE
) -> FixtureGitObserver:
    return FixtureGitObserver(
        observed_main=observed_main,
        observed_tree=observed_tree,
        objects={CURRENT_MAIN: (CURRENT_TREE, ()), NEXT_MAIN: (NEXT_TREE, (CURRENT_MAIN,))},
    )


# ---------------------------------------------------------------------------
# Positive path
# ---------------------------------------------------------------------------


def test_trust_current_allows_merge(tmp_path: Path) -> None:
    current = _anchor()
    initialize_store(tmp_path, current)
    result = require_trust_current_for_merge(store=tmp_path, topology=_topology())
    assert result.trusted_main == CURRENT_MAIN


def test_returns_the_loaded_anchor_unmutated(tmp_path: Path) -> None:
    """Never a trust-state mutation: the store's current.json is
    byte-identical before and after a successful call."""
    current = _anchor()
    initialize_store(tmp_path, current)
    before = (tmp_path / "current.json").read_text(encoding="utf-8")
    require_trust_current_for_merge(store=tmp_path, topology=_topology())
    after = (tmp_path / "current.json").read_text(encoding="utf-8")
    assert before == after
    assert not (tmp_path / "history").exists()  # compare_and_advance never invoked


# ---------------------------------------------------------------------------
# Adversarial denial matrix
# ---------------------------------------------------------------------------


def test_stale_trust_denies_merge_without_carrier(tmp_path: Path) -> None:
    """Real incident shape, PR #653: main has moved (NEXT_MAIN is now
    live) but trust is still pinned at the old CURRENT_MAIN. No carrier
    supplied -- must deny."""
    current = _anchor()
    initialize_store(tmp_path, current)
    topology = _topology(observed_main=NEXT_MAIN, observed_tree=NEXT_TREE)
    with pytest.raises(MergeGuardError) as exc:
        require_trust_current_for_merge(store=tmp_path, topology=topology)
    assert exc.value.code == "TRUST_NOT_CURRENT_FOR_MERGE"
    assert isinstance(exc.value, TrustError)  # subclass, not a parallel hierarchy


def test_stale_trust_with_explicit_carrier_is_allowed(tmp_path: Path) -> None:
    """Real incident shape, PR #669/#671: trust is stale specifically
    because the repair carrier itself is what's being integrated. An
    explicit, narrow justification lets this ONE precondition check pass."""
    current = _anchor()
    initialize_store(tmp_path, current)
    topology = _topology(observed_main=NEXT_MAIN, observed_tree=NEXT_TREE)
    carrier = TrustRepairCarrier(source_pr=671, reason="ordinary-advancement 3-way-merge repair")
    result = require_trust_current_for_merge(
        store=tmp_path, topology=topology, trust_repair_carrier=carrier
    )
    # Still the STALE anchor -- the carrier doesn't mutate it, only lets this check pass.
    assert result.trusted_main == CURRENT_MAIN


def test_carrier_source_pr_must_be_positive() -> None:
    with pytest.raises(TrustError) as exc:
        TrustRepairCarrier(source_pr=0, reason="valid reason")
    assert exc.value.code == "INTERLOCK_MISUSE"
    with pytest.raises(TrustError):
        TrustRepairCarrier(source_pr=-1, reason="valid reason")


def test_carrier_reason_must_be_non_empty() -> None:
    with pytest.raises(TrustError) as exc:
        TrustRepairCarrier(source_pr=671, reason="")
    assert exc.value.code == "INTERLOCK_MISUSE"
    with pytest.raises(TrustError):
        TrustRepairCarrier(source_pr=671, reason="   ")


def test_missing_store_fails_closed(tmp_path: Path) -> None:
    with pytest.raises(TrustError):
        require_trust_current_for_merge(store=tmp_path / "does-not-exist", topology=_topology())


def test_corrupt_store_fails_closed(tmp_path: Path) -> None:
    current = _anchor()
    initialize_store(tmp_path, current)
    (tmp_path / "current.json").write_text("{not-json", encoding="utf-8")
    with pytest.raises(TrustError) as exc:
        require_trust_current_for_merge(store=tmp_path, topology=_topology())
    assert exc.value.code == "TRUST_UNVERIFIABLE"


def test_repository_identity_mismatch_fails_closed(tmp_path: Path) -> None:
    current = _anchor()
    initialize_store(tmp_path, current)
    with pytest.raises(TrustError) as exc:
        require_trust_current_for_merge(
            store=tmp_path,
            topology=_topology(),
            expected_repository_identity="github.com/someone-else/other-repo",
        )
    assert exc.value.code == "REPO_IDENTITY_MISMATCH"


def test_carrier_present_does_not_bypass_identity_mismatch(tmp_path: Path) -> None:
    """A trust_repair_carrier is a narrow exception to the STALENESS
    check only -- it must never let a wrong-repository store slip
    through. Identity verification happens before staleness is even
    evaluated."""
    current = _anchor()
    initialize_store(tmp_path, current)
    carrier = TrustRepairCarrier(source_pr=671, reason="attempted bypass")
    with pytest.raises(TrustError) as exc:
        require_trust_current_for_merge(
            store=tmp_path,
            topology=_topology(observed_main=NEXT_MAIN, observed_tree=NEXT_TREE),
            expected_repository_identity="github.com/someone-else/other-repo",
            trust_repair_carrier=carrier,
        )
    assert exc.value.code == "REPO_IDENTITY_MISMATCH"


def test_carrier_present_does_not_bypass_corrupt_store(tmp_path: Path) -> None:
    """Same principle: the carrier exception applies only to genuine
    staleness, never to an unverifiable store."""
    current = _anchor()
    initialize_store(tmp_path, current)
    (tmp_path / "current.json").write_text("{not-json", encoding="utf-8")
    carrier = TrustRepairCarrier(source_pr=671, reason="attempted bypass")
    with pytest.raises(TrustError) as exc:
        require_trust_current_for_merge(
            store=tmp_path, topology=_topology(), trust_repair_carrier=carrier
        )
    assert exc.value.code == "TRUST_UNVERIFIABLE"


def test_dict_masquerading_as_carrier_denied(tmp_path: Path) -> None:
    """IV finding, PR #672: the only pre-fix gate was `is None`, so a
    plain dict with plausible-looking keys silently satisfied it --
    mypy's type hint alone is not load-bearing against a loosely-typed
    caller (deserialized JSON, a CLI arg, an `Any`-typed kwargs
    passthrough). A real, exact-type TrustRepairCarrier is now required."""
    current = _anchor()
    initialize_store(tmp_path, current)
    topology = _topology(observed_main=NEXT_MAIN, observed_tree=NEXT_TREE)
    fake_carrier = {"source_pr": 671, "reason": "looks legitimate"}
    with pytest.raises(TrustError) as exc:
        require_trust_current_for_merge(
            store=tmp_path, topology=topology, trust_repair_carrier=fake_carrier  # type: ignore[arg-type]
        )
    assert exc.value.code == "INTERLOCK_MISUSE"


def test_bare_true_masquerading_as_carrier_denied(tmp_path: Path) -> None:
    """The exact bypass the class's own docstring claims is impossible --
    now genuinely impossible, not just discouraged by a type hint."""
    current = _anchor()
    initialize_store(tmp_path, current)
    topology = _topology(observed_main=NEXT_MAIN, observed_tree=NEXT_TREE)
    with pytest.raises(TrustError) as exc:
        require_trust_current_for_merge(
            store=tmp_path, topology=topology, trust_repair_carrier=True  # type: ignore[arg-type]
        )
    assert exc.value.code == "INTERLOCK_MISUSE"


def test_bare_string_masquerading_as_carrier_denied(tmp_path: Path) -> None:
    current = _anchor()
    initialize_store(tmp_path, current)
    topology = _topology(observed_main=NEXT_MAIN, observed_tree=NEXT_TREE)
    with pytest.raises(TrustError) as exc:
        require_trust_current_for_merge(
            store=tmp_path,
            topology=topology,
            trust_repair_carrier="PR #671 repair",  # type: ignore[arg-type]
        )
    assert exc.value.code == "INTERLOCK_MISUSE"


def test_subclass_overriding_validation_denied(tmp_path: Path) -> None:
    """A subclass that overrides `__post_init__` to skip the source_pr/
    reason validation would still pass a bare `isinstance` check --
    exact-type comparison (`type(x) is not TrustRepairCarrier`) closes
    this, since `TrustRepairCarrier` is frozen and not meant to be
    subclassed for this purpose."""

    class ForgedCarrier(TrustRepairCarrier):
        def __post_init__(self) -> None:  # skips all validation
            pass

    current = _anchor()
    initialize_store(tmp_path, current)
    topology = _topology(observed_main=NEXT_MAIN, observed_tree=NEXT_TREE)
    forged = ForgedCarrier(source_pr=-999, reason="")
    with pytest.raises(TrustError) as exc:
        require_trust_current_for_merge(
            store=tmp_path, topology=topology, trust_repair_carrier=forged
        )
    assert exc.value.code == "INTERLOCK_MISUSE"


def test_target_tree_mismatch_alone_still_denied(tmp_path: Path) -> None:
    """Staleness is (main, tree) together -- a tree-only mismatch (same
    commit SHA claimed, different tree observed) must still deny, exactly
    like a main mismatch."""
    current = _anchor()
    initialize_store(tmp_path, current)
    topology = _topology(observed_main=CURRENT_MAIN, observed_tree=NEXT_TREE)
    with pytest.raises(MergeGuardError):
        require_trust_current_for_merge(store=tmp_path, topology=topology)
