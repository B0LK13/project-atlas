"""AS-OBSIDIAN-CAPTURE-001 F19 -- adversarial tests for write attribution.

A green attribution test proves nothing on its own: a classifier that returned
``GOVERNED_AND_ATTRIBUTED`` unconditionally would pass every happy-path check
written against it. So the happy path is one test here and the other eight are
attempts to break the binding -- forging it, losing it, confusing it,
inheriting it where it should not be inherited, and mis-binding a write to the
wrong package.

Each attack asserts the classifier reports the *weaker* state it is entitled
to, never a stronger one. Widening an unknown into a known is the specific
failure this file exists to prevent.
"""

from __future__ import annotations

import asyncio
import pathlib
import subprocess
import sys
import threading
from typing import Any

import pytest
from human_content_attribution import (
    _ACTIVE,
    Attribution,
    AttributionLedger,
    _Binding,
    bind,
    classify,
)
from human_content_boundary import HUMAN_MARKER

from project_atlas.orchestration.autonomy.models import (
    AgentCapability,
    AgentLease,
    NodeState,
)

PIN = "0" * 40
NOTE = b"<!-- BEGIN HUMAN: notes -->\nkeep me\n<!-- END HUMAN: notes -->\n"


def _lease(
    worktree: pathlib.Path,
    *,
    allow: tuple[str, ...] = ("vault",),
    forbid: tuple[str, ...] = (),
    **kw: Any,
) -> AgentLease:
    fields: dict[str, Any] = {
        "lease_id": "lease-1",
        "agent_id": "agent-1",
        "package_id": "AS-OBSIDIAN-CAPTURE-001",
        "branch": "test/f19",
        "worktree": str(worktree),
        "base_pin": PIN,
        "authorized_paths": tuple(allow),
        "forbidden_paths": tuple(forbid),
        "capabilities": (AgentCapability.IMPLEMENT,),
        "start_state": NodeState.READY,
        "expected_output": "attribution",
        "expiry_or_terminal_condition": "DONE",
        "sequence": 1,
    }
    fields.update(kw)
    return AgentLease(**fields)


@pytest.fixture
def note(tmp_path: pathlib.Path) -> pathlib.Path:
    target = tmp_path / "vault" / "n.md"
    target.parent.mkdir(parents=True)
    target.write_bytes(NOTE)
    assert HUMAN_MARKER in target.read_bytes()
    return target


# --------------------------------------------------------------- the happy path
def test_f19_a_write_inside_an_active_lease_is_governed_and_attributed(
    tmp_path: pathlib.Path, note: pathlib.Path
) -> None:
    """The one test that is allowed to be green for the ordinary reason."""
    lease = _lease(tmp_path)
    ledger = AttributionLedger()
    with bind(lease):
        entry = ledger.record(note, "os.replace", altered=True)
    assert entry.attribution is Attribution.GOVERNED_AND_ATTRIBUTED
    # Attribution is only useful if it carries the authority context with it.
    assert (entry.agent_id, entry.lease_id) == ("agent-1", "lease-1")
    assert entry.base_pin == PIN, "the exact state the write was made against"


# ------------------------------------------------------------------- forgery
def test_f19_a_forged_binding_is_refused_rather_than_believed(
    tmp_path: pathlib.Path, note: pathlib.Path
) -> None:
    """Constructing a binding by hand must not manufacture authority.

    This is the attack that matters most: if a plain `_Binding(lease, token)`
    were enough, every classification would be self-asserted and the whole
    mechanism would be decorative.
    """
    forged = _Binding(lease=_lease(tmp_path), token=123456)
    reset = _ACTIVE.set(forged)
    try:
        assert classify(note) is Attribution.DETECTED_BUT_UNATTRIBUTED
    finally:
        _ACTIVE.reset(reset)


def test_f19_forgery_refusal_is_not_vacuous(tmp_path: pathlib.Path, note: pathlib.Path) -> None:
    """The control for the test above.

    A forged binding is refused because its token was never minted -- not
    because `_Binding` objects are refused generally. Mint the token and the
    same object classifies as governed, which is what proves the refusal
    turned on trust rather than on shape.
    """
    import human_content_attribution as attribution

    forged = _Binding(lease=_lease(tmp_path), token=987654)
    reset = _ACTIVE.set(forged)
    attribution._MINTED.add(987654)
    try:
        assert classify(note) is Attribution.GOVERNED_AND_ATTRIBUTED
    finally:
        attribution._MINTED.discard(987654)
        _ACTIVE.reset(reset)


# ------------------------------------------------------------------- lease loss
def test_f19_a_write_that_escapes_the_lease_is_not_credited_to_it(
    tmp_path: pathlib.Path, note: pathlib.Path
) -> None:
    """Deferred work must not inherit authority that has already ended.

    A queued or finalised write running after the block exits is exactly how
    a real system loses track of authority, so the stale binding is replayed
    here deliberately.
    """
    lease = _lease(tmp_path)
    captured: list[_Binding] = []
    with bind(lease):
        binding = _ACTIVE.get()
        assert binding is not None
        captured.append(binding)
        assert classify(note) is Attribution.GOVERNED_AND_ATTRIBUTED

    reset = _ACTIVE.set(captured[0])  # replay the *same* binding afterwards
    try:
        assert classify(note) is Attribution.DETECTED_BUT_UNATTRIBUTED
    finally:
        _ACTIVE.reset(reset)


def test_f19_an_inactive_lease_grants_nothing(tmp_path: pathlib.Path, note: pathlib.Path) -> None:
    """`active=False` is an authority statement and must be honoured."""
    with bind(_lease(tmp_path, active=False)):
        assert classify(note) is Attribution.DETECTED_BUT_UNATTRIBUTED


# --------------------------------------------------------------- mis-binding
def test_f19_a_write_outside_the_lease_scope_is_attributed_but_unauthorized(
    tmp_path: pathlib.Path,
) -> None:
    """Knowing who did it does not make it allowed -- the two are separate."""
    outside = tmp_path / "elsewhere" / "n.md"
    outside.parent.mkdir(parents=True)
    outside.write_bytes(NOTE)
    with bind(_lease(tmp_path, allow=("vault",))):
        assert classify(outside) is Attribution.ATTRIBUTED_BUT_UNAUTHORIZED


def test_f19_a_forbidden_path_beats_an_authorizing_one(
    tmp_path: pathlib.Path, note: pathlib.Path
) -> None:
    """Overlapping scopes must resolve to the restrictive answer."""
    with bind(_lease(tmp_path, allow=("vault",), forbid=("vault",))):
        assert classify(note) is Attribution.ATTRIBUTED_BUT_UNAUTHORIZED


def test_f19_an_empty_allow_list_authorizes_nothing(
    tmp_path: pathlib.Path, note: pathlib.Path
) -> None:
    """An empty allow-list is empty. Reading it as "unrestricted" would turn
    the least-specified lease into the most powerful one."""
    with bind(_lease(tmp_path, allow=())):
        assert classify(note) is Attribution.ATTRIBUTED_BUT_UNAUTHORIZED


# ------------------------------------------------------------ confusion
def test_f19_nested_leases_do_not_bleed_into_each_other(
    tmp_path: pathlib.Path, note: pathlib.Path
) -> None:
    """The inner lease owns its writes; the outer one resumes on exit."""
    outer = _lease(tmp_path, lease_id="outer", agent_id="agent-outer")
    inner = _lease(tmp_path, lease_id="inner", agent_id="agent-inner", allow=())
    ledger = AttributionLedger()
    with bind(outer):
        first = ledger.record(note, "os.replace", altered=False)
        with bind(inner):
            second = ledger.record(note, "os.replace", altered=False)
        third = ledger.record(note, "os.replace", altered=False)
    assert first.lease_id == "outer"
    assert second.lease_id == "inner", "inner write mis-attributed to the outer lease"
    assert second.attribution is Attribution.ATTRIBUTED_BUT_UNAUTHORIZED
    assert third.lease_id == "outer", "outer authority did not resume"


# ------------------------------------------------------------ inheritance
def test_f19_inheritance_across_concurrency_is_measured_not_assumed(
    tmp_path: pathlib.Path, note: pathlib.Path
) -> None:
    """`asyncio` copies context; `threading` does not. Both are pinned.

    The asymmetry is a property of CPython, not of this design, and it is the
    kind of thing a refactor changes silently. An await'ed helper *is* the
    same execution and must stay attributed; a bare thread is a different
    execution and must not inherit authority it was never granted.
    """
    lease = _lease(tmp_path)
    seen: dict[str, Attribution] = {}

    async def _async_leg() -> None:
        with bind(lease):

            async def inner() -> None:
                seen["task"] = classify(note)

            await asyncio.create_task(inner())

    asyncio.run(_async_leg())
    assert seen["task"] is Attribution.GOVERNED_AND_ATTRIBUTED, (
        "an awaited task is the same execution and lost its authority"
    )

    def _thread_leg() -> None:
        seen["thread"] = classify(note)

    with bind(lease):
        worker = threading.Thread(target=_thread_leg)
        worker.start()
        worker.join()
    assert seen["thread"] is Attribution.DETECTED_BUT_UNATTRIBUTED, (
        "a bare thread inherited authority it was never granted"
    )


# --------------------------------------------------- the boundary of the claim
def test_f19_a_subprocess_write_is_outside_the_observable_boundary(
    tmp_path: pathlib.Path, note: pathlib.Path
) -> None:
    """The limitation, stated as a passing test rather than as prose.

    A child process carries no trusted identity, so a write it makes must be
    reported as unexplained -- not attributed to whatever lease happened to be
    active in the parent. Reconciliation is what makes that state reachable at
    all; without it `OUTSIDE_OBSERVABLE_BOUNDARY` would be a vocabulary entry
    nothing could emit.
    """
    ledger = AttributionLedger()
    before = {str(note): note.read_bytes()}
    with bind(_lease(tmp_path)):
        subprocess.run(
            [
                sys.executable,
                "-c",
                f"import pathlib;pathlib.Path({str(note)!r}).write_bytes("
                f"b'<!-- BEGIN HUMAN: notes -->\\nCLOBBERED\\n"
                f"<!-- END HUMAN: notes -->\\n')",
            ],
            check=True,
        )
    after = {str(note): note.read_bytes()}
    assert after != before, "the fixture did not actually damage the note"
    assert ledger.writes == [], "an in-process record for an out-of-process write"

    escaped = ledger.reconcile(before, after)
    assert [e.attribution for e in escaped] == [Attribution.OUTSIDE_OBSERVABLE_BOUNDARY]
    assert escaped[0].agent_id == "", (
        "a lease active in the parent was credited with a child process's write"
    )


def test_f19_absence_of_observation_is_not_evidence_of_absence(
    tmp_path: pathlib.Path, note: pathlib.Path
) -> None:
    """NO_OUTPUT != STILL_RUNNING_CORRECTLY, applied to attribution.

    With no boundary installed, "no write was seen" carries no information at
    all, and the classifier must say `UNKNOWN` rather than reporting the clean
    result that an uninstalled observer trivially produces.
    """
    assert classify(note, observed=False, installed=False) is Attribution.UNKNOWN
    assert classify(note, observed=True, installed=False) is Attribution.UNKNOWN

    ledger = AttributionLedger(installed=False)
    before = {str(note): note.read_bytes()}
    note.write_bytes(NOTE.replace(b"keep me", b"changed"))
    escaped = ledger.reconcile(before, {str(note): note.read_bytes()})
    assert [e.attribution for e in escaped] == [Attribution.UNKNOWN], (
        "an unwatched change was reported as if the boundary had been watching"
    )


def test_f19_the_binding_is_not_a_defence_against_hostile_in_process_code(
    tmp_path: pathlib.Path, note: pathlib.Path
) -> None:
    """The honest limit of the mechanism, pinned so it cannot be overclaimed.

    Code sharing this interpreter can mint itself a token, exactly as it can
    unhook the boundary that observes it. This test *passes when the attack
    succeeds*: it documents the threat model rather than pretending the
    defence extends further than it does.
    """
    import human_content_attribution as attribution

    stolen = 555_000
    reset = _ACTIVE.set(_Binding(lease=_lease(tmp_path), token=stolen))
    attribution._MINTED.add(stolen)
    try:
        assert classify(note) is Attribution.GOVERNED_AND_ATTRIBUTED
    finally:
        attribution._MINTED.discard(stolen)
        _ACTIVE.reset(reset)


def test_f19_every_state_in_the_vocabulary_is_actually_emitted(
    tmp_path: pathlib.Path, note: pathlib.Path
) -> None:
    """No decorative states -- and this test earns that claim by producing them.

    An earlier revision asserted a hand-written set against the enum, which is
    the exact shape of a test that cannot fail for the reason it claims: the
    literal would have been updated alongside any new member and stayed green
    while nothing emitted it. Every state below now comes back from a real
    call, so a member with no producer fails this test.
    """
    produced: set[Attribution] = set()

    with bind(_lease(tmp_path, allow=("vault",))):
        produced.add(classify(note))
        produced.add(classify(tmp_path / "elsewhere.md"))
    produced.add(classify(note))
    produced.add(classify(note, observed=True, installed=False))

    ledger = AttributionLedger()
    before = {str(note): note.read_bytes()}
    note.write_bytes(NOTE.replace(b"keep me", b"unobserved change"))
    produced.update(e.attribution for e in ledger.reconcile(before, {str(note): note.read_bytes()}))

    missing = set(Attribution) - produced
    assert not missing, f"no code path emits: {sorted(m.value for m in missing)}"


# ------------------------------------------------- detection meets attribution
def test_f19_a_real_damaging_write_is_reported_with_the_lease_that_caused_it(
    tmp_path: pathlib.Path, note: pathlib.Path
) -> None:
    """The whole point, exercised through a real writer rather than a stub.

    F18 alone reports "operator regions changed at this path". Bound to a
    lease, the same event reports which agent, under which package, against
    which base pin -- which is the difference between an alarm and an account
    of what happened.
    """
    from human_content_boundary import enforced

    import project_atlas.obsidian_projection as op

    damage = b"<!-- BEGIN HUMAN: notes -->\nCLOBBERED\n<!-- END HUMAN: notes -->\n"
    lease = _lease(tmp_path, allow=("vault",))
    with enforced() as boundary, bind(lease):
        op._write_atomic(note, damage, vault=tmp_path / "vault")

    assert len(boundary.violations) == 1, "F18 detection regressed"
    damaging = [w for w in boundary.ledger.writes if w.altered]
    assert damaging, "a damaging write produced no attribution record"
    entry = damaging[0]
    assert entry.attribution is Attribution.GOVERNED_AND_ATTRIBUTED
    assert (entry.agent_id, entry.package_id, entry.base_pin) == (
        "agent-1",
        "AS-OBSIDIAN-CAPTURE-001",
        PIN,
    )


def test_f19_the_same_write_outside_scope_is_reported_as_unauthorized(
    tmp_path: pathlib.Path, note: pathlib.Path
) -> None:
    """Identical damage, different authority -- and the report must differ.

    The control for the test above: it proves the classification tracks the
    lease scope rather than merely echoing whichever lease was bound.
    """
    from human_content_boundary import enforced

    import project_atlas.obsidian_projection as op

    damage = b"<!-- BEGIN HUMAN: notes -->\nCLOBBERED\n<!-- END HUMAN: notes -->\n"
    lease = _lease(tmp_path, allow=("some-other-package",))
    with enforced() as boundary, bind(lease):
        op._write_atomic(note, damage, vault=tmp_path / "vault")

    damaging = [w for w in boundary.ledger.writes if w.altered]
    assert damaging, "a damaging write produced no attribution record"
    assert damaging[0].attribution is Attribution.ATTRIBUTED_BUT_UNAUTHORIZED
    assert damaging[0].agent_id == "agent-1", "the actor is still known"


def test_f19_an_unleased_damaging_write_is_detected_but_unattributed(
    tmp_path: pathlib.Path, note: pathlib.Path
) -> None:
    """The state F18 could reach on its own, still reported honestly.

    Adding attribution must not tempt the ledger into inventing an actor for
    a write that had none.
    """
    from human_content_boundary import enforced

    import project_atlas.obsidian_projection as op

    damage = b"<!-- BEGIN HUMAN: notes -->\nCLOBBERED\n<!-- END HUMAN: notes -->\n"
    with enforced() as boundary:
        op._write_atomic(note, damage, vault=tmp_path / "vault")

    damaging = [w for w in boundary.ledger.writes if w.altered]
    assert damaging, "a damaging write produced no attribution record"
    assert damaging[0].attribution is Attribution.DETECTED_BUT_UNATTRIBUTED
    assert damaging[0].agent_id == "", "an actor was invented for an unleased write"
