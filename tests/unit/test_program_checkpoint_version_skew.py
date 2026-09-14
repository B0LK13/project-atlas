"""SKEW-1: a cross-version checkpoint read fails closed AND distinguishably.

ATLAS-UPGRADE-STATE-COMPAT-001 measured the defect: a terminal checkpoint
written intact by an older version was refused as ``CHECKPOINT_DIGEST_MISMATCH``
-- "truncated or edited after it was written" -- and one written by a newer
version as ``CHECKPOINT_MALFORMED``. Both refusals were correct and both
diagnoses were wrong, and the upgrade one invites an operator to wipe intact
state. Fix option (a): the checkpoint schema version is bumped and checked on
the raw document before validation and before the digest.

The upgrade-direction fixture is not synthesized. ``tests/fixtures/
continuation-skew/v1-643c7ebe`` holds envelopes and checkpoints written by the
643c7ebe code itself (its own ``persist_envelope`` / ``persist_checkpoint``),
whose schema_version is 1. Under 643c7ebe the same files reconcile to
``ALREADY_COMPLETE`` (skew-done) and ``RESTART_FROM_TOP`` launchable (skew-open).

Every assertion keys on a code, a disposition or ``launchable`` -- never prose --
except the two version tokens the refusal is required to name.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from project_atlas.orchestration.program.capsule import build_capsule
from project_atlas.orchestration.program.continuation import (
    CHECKPOINT_SCHEMA_VERSION,
    CheckpointError,
    CheckpointPolicy,
    ContinuationCheckpoint,
    ExecutionIdentity,
    ReplayClass,
    TaskBudgets,
    TaskEnvelope,
    checkpoints_dir,
    envelopes_dir,
    list_checkpoints,
    load_checkpoint,
    persist_checkpoint,
    persist_envelope,
    seal_checkpoint,
)
from project_atlas.orchestration.program.models import AcceptanceCheck, AcceptanceKind
from project_atlas.orchestration.program.reconciliation import (
    Disposition,
    reconcile_one,
    reconcile_root,
)
from project_atlas.orchestration.program.store import write_json_atomic

V1_FIXTURE = (
    Path(__file__).resolve().parents[1] / "fixtures" / "continuation-skew" / "v1-643c7ebe"
)
WORKER = "fixture-worker-01"


def _install_v1_fixture(root: Path) -> None:
    """Copy the 643c7ebe-written records into a fresh state root, byte for byte."""
    for sub, target in (
        ("checkpoints", checkpoints_dir(root)),
        ("envelopes", envelopes_dir(root)),
    ):
        target.mkdir(parents=True, exist_ok=True)
        for item in sorted((V1_FIXTURE / sub).glob("*.json")):
            shutil.copyfile(item, target / item.name)


def _checkpoint_file(root: Path, task_id: str) -> Path:
    import hashlib

    name = hashlib.sha256(task_id.encode("utf-8")).hexdigest() + ".checkpoint.json"
    return checkpoints_dir(root) / name


def _envelope(task_id: str) -> TaskEnvelope:
    return TaskEnvelope(
        task_id=task_id,
        objective=f"fixture task {task_id}",
        capabilities_required=("IMPLEMENT",),
        candidate_head="a" * 40,
        candidate_tree="b" * 40,
        allowed_paths=(f"{task_id}.txt",),
        acceptance=(
            AcceptanceCheck(
                check_id=f"{task_id}-out",
                kind=AcceptanceKind.FILE_EXISTS,
                description=f"{task_id}.txt exists",
                path=f"{task_id}.txt",
            ),
        ),
        budgets=TaskBudgets(),
        checkpoint_policy=CheckpointPolicy(),
        replay_class=ReplayClass.IDEMPOTENT_MUTATION,
        approved_by="fixture-operator",
        approval_reference="tests/unit/test_program_checkpoint_version_skew.py",
        profile_ref="impl",
        worker_id=WORKER,
        program_id="fixture-program",
    )


def _current_checkpoint(
    envelope: TaskEnvelope, *, terminal: bool, sequence: int = 1
) -> ContinuationCheckpoint:
    return ContinuationCheckpoint(
        identity=ExecutionIdentity(
            task_id=envelope.task_id,
            worker_id=envelope.worker_id,
            session_id=f"session.{sequence}",
            attempt_id=f"{envelope.task_id}.attempt.{sequence}",
        ),
        envelope_digest=envelope.digest(),
        program_id=envelope.program_id,
        sequence=sequence,
        next_action=f"continue {envelope.task_id}",
        worktree_path="/fixture/worktree",
        git_head=envelope.candidate_head,
        git_tree=envelope.candidate_tree,
        replay_class=ReplayClass.COMPLETED if terminal else envelope.replay_class,
        terminal=terminal,
    )


def _assert_skew(exc: CheckpointError, *, writer: int, reader: int) -> None:
    assert exc.code == "CHECKPOINT_VERSION_SKEW", exc.code
    assert f"writer_schema_version={writer}" in str(exc), str(exc)
    assert f"reader_schema_version={reader}" in str(exc), str(exc)


# ------------------------------------------------------------------ fixture


def test_the_upgrade_fixture_is_a_genuine_version_1_record() -> None:
    """Guard the fixture itself: a v1 record, sealed, for both tasks."""
    files = sorted((V1_FIXTURE / "checkpoints").glob("*.checkpoint.json"))
    assert len(files) == 2
    for path in files:
        raw = json.loads(path.read_text(encoding="utf-8"))
        assert raw["schema_version"] == 1
        assert isinstance(raw["self_digest"], str) and len(raw["self_digest"]) == 64
    assert CHECKPOINT_SCHEMA_VERSION == 2


# --------------------------------------------------------- upgrade direction


@pytest.mark.parametrize("task_id", ["skew-done", "skew-open"])
def test_UPGRADE_a_record_from_an_older_version_is_VERSION_SKEW_not_DIGEST_MISMATCH(
    tmp_path: Path, task_id: str
) -> None:
    root = tmp_path / "state"
    _install_v1_fixture(root)
    before = _checkpoint_file(root, task_id).read_bytes()

    for verify in (True, False):
        with pytest.raises(CheckpointError) as caught:
            load_checkpoint(root, task_id, verify=verify)
        _assert_skew(caught.value, writer=1, reader=CHECKPOINT_SCHEMA_VERSION)
        assert caught.value.code != "CHECKPOINT_DIGEST_MISMATCH"

    with pytest.raises(CheckpointError) as listed:
        list_checkpoints(root)
    _assert_skew(listed.value, writer=1, reader=CHECKPOINT_SCHEMA_VERSION)

    verdict = reconcile_one(root, task_id, governed_root=tmp_path, our_worker_id=WORKER)
    assert verdict.disposition is Disposition.FAIL_CLOSED
    assert verdict.launchable is False
    assert verdict.evidence == ("CHECKPOINT_VERSION_SKEW",)

    # Not repaired, not re-sealed, not migrated in place.
    assert _checkpoint_file(root, task_id).read_bytes() == before


def test_UPGRADE_a_skewed_record_blocks_a_write_instead_of_being_overwritten(
    tmp_path: Path,
) -> None:
    root = tmp_path / "state"
    _install_v1_fixture(root)
    before = _checkpoint_file(root, "skew-open").read_bytes()
    envelope = TaskEnvelope.model_validate(
        json.loads(
            next(
                p
                for p in (V1_FIXTURE / "envelopes").glob("*.envelope.json")
                if json.loads(p.read_text(encoding="utf-8"))["task_id"] == "skew-open"
            ).read_text(encoding="utf-8")
        )
    )
    with pytest.raises(CheckpointError) as caught:
        persist_checkpoint(root, _current_checkpoint(envelope, terminal=False, sequence=2))
    assert caught.value.code == "CHECKPOINT_VERSION_SKEW"
    assert _checkpoint_file(root, "skew-open").read_bytes() == before


def test_MUTATION_the_same_v1_record_relabelled_as_current_is_a_DIGEST_MISMATCH(
    tmp_path: Path,
) -> None:
    """The version field is what the skew keys on.

    Change ONLY ``schema_version`` 1 -> current on the genuine v1 record. The
    version check then has nothing to say, and the record reaches the digest,
    which was sealed over schema_version 1 -- so it is refused as a digest
    mismatch. Without the version check, that is what every upgrade read said.
    """
    root = tmp_path / "state"
    _install_v1_fixture(root)
    path = _checkpoint_file(root, "skew-done")
    raw = json.loads(path.read_text(encoding="utf-8"))
    raw["schema_version"] = CHECKPOINT_SCHEMA_VERSION
    path.write_text(json.dumps(raw, indent=2, sort_keys=True), encoding="utf-8")
    with pytest.raises(CheckpointError) as caught:
        load_checkpoint(root, "skew-done")
    assert caught.value.code == "CHECKPOINT_DIGEST_MISMATCH"


# -------------------------------------------------------- rollback direction


def test_ROLLBACK_a_record_from_a_newer_version_is_VERSION_SKEW_not_MALFORMED(
    tmp_path: Path,
) -> None:
    """A reader meeting a record from a NEWER writer names the skew too.

    The newer record is modelled on the measured rollback case: a higher
    ``schema_version`` AND a field this reader does not know (643c7ebe's
    ``capture`` was exactly that to e696c71f).
    """
    root = tmp_path / "state"
    envelope = _envelope("newer-task")
    persist_envelope(root, envelope)
    persist_checkpoint(root, _current_checkpoint(envelope, terminal=True))
    path = _checkpoint_file(root, "newer-task")
    raw = json.loads(path.read_text(encoding="utf-8"))
    newer = CHECKPOINT_SCHEMA_VERSION + 1
    raw["schema_version"] = newer
    raw["field_from_the_future"] = {"status": "CAPTURE_AVAILABLE"}
    path.write_text(json.dumps(raw, indent=2, sort_keys=True), encoding="utf-8")

    for verify in (True, False):
        with pytest.raises(CheckpointError) as caught:
            load_checkpoint(root, "newer-task", verify=verify)
        _assert_skew(caught.value, writer=newer, reader=CHECKPOINT_SCHEMA_VERSION)
        assert caught.value.code != "CHECKPOINT_MALFORMED"

    verdicts = reconcile_root(root, governed_root=tmp_path, our_worker_id=WORKER)
    assert [(v.disposition, v.launchable, v.evidence) for v in verdicts] == [
        (Disposition.FAIL_CLOSED, False, ("CHECKPOINT_VERSION_SKEW",))
    ]


def test_MUTATION_the_newer_record_without_its_version_bump_is_MALFORMED(
    tmp_path: Path,
) -> None:
    """Same extra field, version left at current: what a reader said before."""
    root = tmp_path / "state"
    envelope = _envelope("extra-task")
    persist_envelope(root, envelope)
    persist_checkpoint(root, _current_checkpoint(envelope, terminal=True))
    path = _checkpoint_file(root, "extra-task")
    raw = json.loads(path.read_text(encoding="utf-8"))
    raw["field_from_the_future"] = {"status": "CAPTURE_AVAILABLE"}
    path.write_text(json.dumps(raw, indent=2, sort_keys=True), encoding="utf-8")
    with pytest.raises(CheckpointError) as caught:
        load_checkpoint(root, "extra-task")
    assert caught.value.code == "CHECKPOINT_MALFORMED"


# ------------------------------------------------ current-version behaviour


def test_a_genuinely_edited_record_at_the_current_version_is_still_DIGEST_MISMATCH(
    tmp_path: Path,
) -> None:
    root = tmp_path / "state"
    envelope = _envelope("edited-task")
    persist_envelope(root, envelope)
    persist_checkpoint(root, _current_checkpoint(envelope, terminal=False))
    path = _checkpoint_file(root, "edited-task")
    raw = json.loads(path.read_text(encoding="utf-8"))
    assert raw["schema_version"] == CHECKPOINT_SCHEMA_VERSION
    raw["next_action"] = "do something else entirely"
    path.write_text(json.dumps(raw, indent=2, sort_keys=True), encoding="utf-8")

    with pytest.raises(CheckpointError) as caught:
        load_checkpoint(root, "edited-task")
    assert caught.value.code == "CHECKPOINT_DIGEST_MISMATCH"
    verdict = reconcile_one(root, "edited-task", governed_root=tmp_path, our_worker_id=WORKER)
    assert verdict.disposition is Disposition.FAIL_CLOSED
    assert verdict.evidence == ("CHECKPOINT_DIGEST_MISMATCH",)
    assert verdict.launchable is False


def test_a_same_version_terminal_record_is_still_ALREADY_COMPLETE(tmp_path: Path) -> None:
    root = tmp_path / "state"
    envelope = _envelope("done-task")
    persist_envelope(root, envelope)
    sealed = persist_checkpoint(root, _current_checkpoint(envelope, terminal=True))
    assert sealed.schema_version == CHECKPOINT_SCHEMA_VERSION
    for _ in range(2):
        verdict = reconcile_one(root, "done-task", governed_root=tmp_path, our_worker_id=WORKER)
        assert verdict.disposition is Disposition.ALREADY_COMPLETE
        assert verdict.launchable is False


# ------------------------------------------------------ never launchable


def test_a_skewed_record_is_never_launchable_counted_against_a_launchable_control(
    tmp_path: Path,
) -> None:
    """Zero launchable verdicts, counted -- and the count is not vacuous.

    The control is the genuine v1 ``skew-open`` record with ONLY its version
    moved to current and its digest re-sealed over that: identical content at
    the current version reconciles to RESTART_FROM_TOP, launchable. So the
    skewed record's zero is caused by the version, not by the fixture.
    """
    passes = 3

    skewed = tmp_path / "skewed"
    _install_v1_fixture(skewed)
    skewed_launchable = sum(
        verdict.launchable
        for _ in range(passes)
        for verdict in reconcile_root(skewed, governed_root=tmp_path, our_worker_id=WORKER)
    )
    skewed_codes = {
        verdict.task_id: verdict.evidence
        for verdict in reconcile_root(skewed, governed_root=tmp_path, our_worker_id=WORKER)
    }
    assert skewed_launchable == 0
    assert skewed_codes == {
        "skew-done": ("CHECKPOINT_VERSION_SKEW",),
        "skew-open": ("CHECKPOINT_VERSION_SKEW",),
    }

    control = tmp_path / "control"
    _install_v1_fixture(control)
    for task_id in ("skew-done", "skew-open"):
        path = _checkpoint_file(control, task_id)
        raw = json.loads(path.read_text(encoding="utf-8"))
        raw["schema_version"] = CHECKPOINT_SCHEMA_VERSION
        raw.pop("self_digest")
        resealed = seal_checkpoint(ContinuationCheckpoint.model_validate(raw))
        write_json_atomic(path, resealed.model_dump(mode="json"))
    control_verdicts = {
        verdict.task_id: verdict
        for verdict in reconcile_root(control, governed_root=tmp_path, our_worker_id=WORKER)
    }
    assert control_verdicts["skew-done"].disposition is Disposition.ALREADY_COMPLETE
    assert control_verdicts["skew-open"].disposition is Disposition.RESTART_FROM_TOP
    control_launchable = sum(
        verdict.launchable
        for _ in range(passes)
        for verdict in reconcile_root(control, governed_root=tmp_path, our_worker_id=WORKER)
    )
    assert control_launchable == passes, "the control must be launchable, or the zero is vacuous"


def test_the_capsule_reports_a_skewed_record_as_fail_closed(tmp_path: Path) -> None:
    root = tmp_path / "state"
    _install_v1_fixture(root)
    capsule = build_capsule(root, governed_root=tmp_path, for_worker_id=WORKER)
    rows = {task.task_id: task for task in capsule.tasks}
    assert set(rows) == {"skew-done", "skew-open"}
    for row in rows.values():
        assert row.disposition == Disposition.FAIL_CLOSED.value
        assert row.launchable is False
