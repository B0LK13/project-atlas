"""AS-ORCH-LOCAL-DISPATCH-001: governed local-process dispatch port.

Wires ``orchestration.local_process_transport``'s disabled-by-default LOCAL
PROCESS execution primitive (PR-B, ``AS-ORCH-LOCAL-PROC-001``) into
``AutonomousLoop``'s existing ``DispatchPort`` seam (``loop.py``) -- the
same extensibility point the loop already has for any non-``IN_PROCESS``
execution host, previously unused in production (the real CLI entrypoint,
``run_governor_loop_tick()``, constructs ``AutonomousLoop`` with
``dispatch=None``).

Does not create a second governor. Does not bypass ``lease()``'s existing
checks (``READY`` state, dependency satisfaction, owner gate, surface
overlap) -- this port is only ever invoked from ``_dispatch_leased()``,
strictly downstream of an already-granted lease. Does not accept
arbitrary caller-supplied authority: every field in the task envelope
this port builds is read from the DURABLE LEASE PROJECTION record for
the currently active lease, never from a parameter a caller could set.

DISABLED BY DEFAULT: constructing this port requires an already-enabled
``LocalProcessExecutorConfig`` (``config.enabled=True``, PR-B's own
disabled-by-default gate) AND an explicit, non-empty, fixed ``argv_template``
supplied by the operator at construction time -- never derived from the
WorkNode/proposal/lease content itself (a governed node choosing its own
executable would be a code-injection vector). The actual argv a task runs
is always ``(*argv_template, <path to a governed request JSON file>)`` --
the fixed template decides HOW to interpret that file; this port never
interprets task content itself, and never implies Cursor, OpenAI,
Anthropic, network access, or API billing (mirrors
``local_process_transport.py``'s own non-claims).

Every dispatch attempt also restores the worktree to a clean state
before returning (IV finding, PR #662 review round 1) -- an accepted
result is committed, a rejected one is discarded back to the exact
pre-run baseline (see ``_commit_accepted_result`` /
``_restore_worktree_to_baseline``). Without this, ANY outcome left the
worktree dirty and every subsequent dispatch against the same root --
a legitimate governed remediation retry of the same lease, or a
completely unrelated node's first-ever dispatch -- died immediately on
``local_process_transport.py``'s own ``WORKTREE_NOT_CLEAN``
precondition, never genuinely running. This module still performs no
git mutation of its own execution-authority claims: it commits/discards
purely as worktree housekeeping between dispatches, never sets
``merge_authorized``/``execution_authorized`` on anything, and the
transport primitive's own enforcement is unchanged.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Final

from project_atlas.orchestration.autonomy.lease_projection import (
    RELATIVE_DEFAULT as LEASE_PROJECTION_RELATIVE_DEFAULT,
)
from project_atlas.orchestration.autonomy.lease_projection import (
    ProjectedLease,
    active_rows,
    load_projection,
)
from project_atlas.orchestration.local_process_transport import (
    LocalProcessExecutorConfig,
    LocalTaskEnvelope,
    run_local_task,
)

PACKAGE_ID: Final[str] = "AS-ORCH-LOCAL-DISPATCH-001"

#: Where durable dispatch receipts live, relative to the project root --
#: sibling to the lease projection store, same ``.atlas/orchestration/``
#: convention every other durable store in this package already uses.
RECEIPTS_RELATIVE: Final[Path] = Path(".atlas") / "orchestration" / "autonomy" / "local_dispatch"

_DISPATCH_ID_PREFIX: Final[str] = "local-process:"


class LocalDispatchError(ValueError):
    """A local-process dispatch could not proceed at all -- a genuine
    protocol/precondition violation (no active lease, ambiguous active
    lease, duplicate dispatch), never an ordinary task-execution failure
    (those are reported as a ``FAILED`` status, not raised)."""

    code: str = "LOCAL_DISPATCH_ERROR"

    def __init__(self, message: str, *, code: str | None = None) -> None:
        super().__init__(message)
        if code is not None:
            self.code = code


def _dispatch_id_for(lease_id: str) -> str:
    return f"{_DISPATCH_ID_PREFIX}{lease_id}"


def _receipt_filename(dispatch_id: str) -> str:
    # dispatch_id contains ':' (from _dispatch_id_for's prefix), which is
    # not a safe filename character on Windows -- substitute for the
    # FILENAME only; the logical dispatch_id string used in every
    # comparison/return value is never altered.
    return dispatch_id.replace(":", "_").replace("/", "_") + ".json"


def _receipts_dir(root: Path) -> Path:
    resolved_root = root.expanduser().resolve()
    target = (resolved_root / RECEIPTS_RELATIVE).resolve()
    if not target.is_relative_to(resolved_root):
        raise LocalDispatchError("receipt store path escapes project root", code="PATH_UNSAFE")
    return target


def _write_json_atomic(target: Path, payload: dict[str, object]) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(payload, sort_keys=True, indent=2, ensure_ascii=True) + "\n"
    tmp = target.with_name(f".{target.name}.tmp")
    tmp.write_text(encoded, encoding="utf-8")
    tmp.replace(target)


def _read_receipt(root: Path, dispatch_id: str) -> dict[str, object] | None:
    path = _receipts_dir(root) / _receipt_filename(dispatch_id)
    if not path.is_file():
        return None
    try:
        decoded: object = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(decoded, dict):
        return None
    return decoded


def _write_receipt(root: Path, dispatch_id: str, payload: dict[str, object]) -> None:
    path = _receipts_dir(root) / _receipt_filename(dispatch_id)
    _write_json_atomic(path, payload)


def _single_active_lease(root: Path) -> ProjectedLease:
    """The one active lease this dispatch is for.

    Mirrors ``DispatchPort.find_active_dispatch_id()``'s own documented
    assumption that the underlying dispatch slot is a single GLOBAL slot,
    not per-lease (see ``loop.py``'s ``DispatchPort`` docstring) -- this
    port makes that assumption explicit and fails closed rather than
    guessing when it does not hold, exactly the same posture the existing
    001D dispatch subsystem already has.
    """
    store = root / LEASE_PROJECTION_RELATIVE_DEFAULT
    projection = load_projection(store)
    active = active_rows(projection)
    if not active:
        raise LocalDispatchError("no active lease found to dispatch", code="NO_ACTIVE_LEASE")
    if len(active) > 1:
        raise LocalDispatchError(
            "more than one active lease found -- cannot determine which to dispatch",
            code="AMBIGUOUS_ACTIVE_LEASE",
        )
    return active[0]


def _request_payload(lease: ProjectedLease, *, dispatch_id: str) -> dict[str, object]:
    """Informational content for the launched process to read -- never
    itself a source of authority (argv/authorized_paths/forbidden_paths
    are set on the LocalTaskEnvelope directly from the SAME lease
    fields, independent of whether the launched process reads or honors
    this file at all)."""
    return {
        "schema_version": 1,
        "package_id": "AS-ORCH-LOCAL-DISPATCH-001",
        "dispatch_id": dispatch_id,
        "lease_id": lease.lease_id,
        "work_id": lease.package_id,
        "base_pin": lease.base_pin,
        "worktree": lease.worktree,
        "authorized_paths": list(lease.authorized_paths),
        "forbidden_paths": list(lease.forbidden_paths),
        "merge_authorized": False,
        "execution_authorized": False,
    }


def _run_git(args: list[str], *, cwd: Path, timeout_seconds: int = 30) -> None:
    subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, text=True, timeout=timeout_seconds
    )


def _restore_worktree_to_baseline(root: Path, *, baseline_sha: str) -> None:
    """Discard a rejected or otherwise-failed dispatch attempt's changes
    entirely, restoring the worktree to precisely the state
    ``run_local_task()`` started from.

    IV finding (PR #662 review round 1): without this, a dispatch that
    left ANY change behind -- a real out-of-scope violation, or even a
    fully successful in-scope run that nothing committed -- made
    ``local_process_transport.py``'s own ``_require_clean_worktree()``
    precondition permanently fail for every subsequent dispatch against
    the same root, including a legitimate governed remediation retry of
    the SAME lease and a completely unrelated node's first-ever dispatch.
    ``git reset --hard`` discards tracked changes back to the fixed
    baseline every measurement was already diffed against (the same SHA
    ``LocalExecutionResult.baseline_sha`` names); ``git clean -fd``
    removes newly created untracked, non-ignored paths. Gitignored paths
    are deliberately left alone -- ``git status --porcelain`` (what
    ``_require_clean_worktree()`` actually checks) never reports them
    regardless, so leaving them is not a blocker, and forcibly sweeping
    ignored paths (``-x``) would risk deleting pre-existing ignored
    content (a `.venv`, a build cache) that happened to already sit
    inside a now-forbidden-labeled directory.

    Only ever called for a FAILED result (nonzero exit, timeout, or an
    authority violation) -- see ``_commit_accepted_result`` for the
    counterpart on an accepted one. A failure here (e.g. ``baseline_sha``
    no longer resolvable) is a genuine, real dispatch-protocol failure,
    not swallowed -- it propagates to ``dispatch_once()``'s own
    exception handling, which records it as a FAILED receipt rather than
    crashing the tick.
    """
    _run_git(["reset", "--hard", baseline_sha], cwd=root)
    _run_git(["clean", "-fd"], cwd=root)


def _commit_accepted_result(root: Path, *, dispatch_id: str, work_id: str) -> None:
    """Commit an authority-clean, exit-0 dispatch result so the worktree
    returns to clean -- the accepted-result counterpart of
    ``_restore_worktree_to_baseline``. Without this, a genuinely
    successful run would leave the SAME permanent
    ``WORKTREE_NOT_CLEAN`` lockout for every future dispatch that a
    rejected one would, since ``_require_clean_worktree()`` cannot tell
    "good" uncommitted changes from "bad" ones -- only that changes
    exist.

    Deterministic, content-free commit message (work_id + dispatch_id
    only, mirroring this repository's NFR-001 "no wall-clock content in
    generated content" convention as closely as a commit -- which always
    carries a non-deterministic author/committer date via git itself --
    can). Requires the operator's git identity (``user.name``/
    ``user.email``) to already be configured, exactly like any other
    commit in this repository; a missing identity fails the underlying
    ``git commit`` call, which propagates as an ordinary, non-crashing
    FAILED dispatch outcome (see ``dispatch_once()``'s exception
    handling), never a silent no-op or a claimed-but-absent commit.
    """
    _run_git(["add", "-A"], cwd=root)
    message = f"AS-ORCH-LOCAL-DISPATCH-001: {work_id} ({dispatch_id})"
    _run_git(["commit", "-m", message], cwd=root, timeout_seconds=60)


class LocalProcessDispatchPort:
    """``loop.py.DispatchPort`` implementation backed by
    ``local_process_transport.run_local_task()``.

    Every authority-relevant field on the ``LocalTaskEnvelope`` this port
    builds (``authorized_paths``, ``forbidden_paths``) comes from the
    durable lease projection record for the currently active lease --
    never from ``argv_template`` (fixed, operator-supplied, applies
    uniformly to every dispatch this port instance ever performs) and
    never from anything a WorkNode/proposal/task content could influence.
    """

    def __init__(
        self,
        *,
        config: LocalProcessExecutorConfig,
        argv_template: tuple[str, ...],
    ) -> None:
        if not config.enabled:
            raise LocalDispatchError(
                "LocalProcessDispatchPort requires an already-enabled "
                "LocalProcessExecutorConfig -- refusing to construct a port "
                "that could never actually dispatch anything, which would "
                "silently mask a misconfiguration rather than fail loudly "
                "at startup",
                code="LOCAL_EXECUTION_DISABLED",
            )
        if not argv_template:
            raise LocalDispatchError(
                "argv_template must be a non-empty, explicit, operator-"
                "supplied command -- never inferred",
                code="ARGV_TEMPLATE_REQUIRED",
            )
        self._config = config
        self._argv_template = argv_template

    def dispatch_once(self, root: Path) -> dict[str, object]:
        lease = _single_active_lease(root)
        # Attempt-indexed dispatch_id, not one fixed id per lease: the
        # existing governed remediation cycle (governor.py's
        # complete_verification()/remediate_and_resume(), unchanged by
        # this PR) legitimately re-dispatches the SAME lease again after a
        # genuine, already-resolved failure (up to
        # MAX_AUTONOMOUS_REMEDIATION_CYCLES times) -- that is a real,
        # governed retry, not a duplicate. loop.py's own
        # `completed_dispatch_ids` guard also requires each dispatch to
        # have its own never-reused id regardless. Only a dispatch whose
        # PRIOR attempt receipt is still genuinely unresolved (status
        # RUNNING -- a real overlapping/concurrent re-dispatch, or a
        # caller bug that never awaited the first one) is refused.
        attempt = 0
        while True:
            dispatch_id = f"{_dispatch_id_for(lease.lease_id)}:{attempt}"
            existing = _read_receipt(root, dispatch_id)
            if existing is None:
                break
            if existing.get("status") == "RUNNING":
                raise LocalDispatchError(
                    f"dispatch {dispatch_id!r} is still unresolved -- refusing "
                    "to start an overlapping dispatch for the same lease",
                    code="DUPLICATE_DISPATCH",
                )
            attempt += 1
        # Written BEFORE the (potentially long-running) child process
        # starts, so a crash of THIS process mid-run leaves a durable,
        # positively-checkable "something was dispatched for this lease"
        # marker -- find_active_dispatch_id()/recover() rely on this
        # existing, never on inferring anything from the child's own
        # aliveness.
        _write_receipt(
            root,
            dispatch_id,
            {
                "dispatch_id": dispatch_id,
                "lease_id": lease.lease_id,
                "package_id": lease.package_id,
                "status": "RUNNING",
            },
        )
        request_path = _receipts_dir(root) / f"{dispatch_id.replace(':', '_')}-request.json"
        _write_json_atomic(request_path, _request_payload(lease, dispatch_id=dispatch_id))
        relative_request_path = request_path.relative_to(root.expanduser().resolve()).as_posix()

        envelope = LocalTaskEnvelope(
            work_id=lease.package_id,
            argv=(*self._argv_template, relative_request_path),
            authorized_paths=lease.authorized_paths,
            forbidden_paths=lease.forbidden_paths,
        )
        try:
            result = run_local_task(envelope, self._config, project_root=root)
        except Exception as exc:
            # dispatch_once() must never let an ordinary task-execution
            # failure escape as an uncaught exception -- loop.py's
            # _dispatch_leased() does not wrap this call in a try/except,
            # so an uncaught exception here would crash the whole tick
            # rather than cleanly finalize the node as failed. Genuine
            # protocol violations (no active lease, duplicate dispatch)
            # are raised ABOVE this point, before any process starts;
            # everything past that point is treated as this dispatch's
            # own, cleanly-reported outcome.
            _write_receipt(
                root,
                dispatch_id,
                {
                    "dispatch_id": dispatch_id,
                    "lease_id": lease.lease_id,
                    "package_id": lease.package_id,
                    "status": "FAILED",
                    "error": str(exc),
                },
            )
            return {"dispatch_id": dispatch_id, "status": "FAILED", "digest": dispatch_id}

        passed = result.exit_code == 0 and result.authority_clean
        # IV finding (PR #662 review round 1): without this step, the
        # worktree was left exactly as run_local_task()'s child process
        # left it -- dirty on ANY outcome, accepted or rejected -- which
        # made local_process_transport.py's own _require_clean_worktree()
        # precondition permanently fail every subsequent dispatch against
        # this same root: a legitimate governed remediation retry of the
        # SAME lease, and a completely unrelated node's first-ever
        # dispatch, both died on WORKTREE_NOT_CLEAN. An accepted result is
        # committed so its changes durably persist and the tree returns
        # to clean; a rejected one is discarded back to the exact
        # pre-run baseline so the NEXT attempt starts genuinely fresh,
        # not layered on top of a violating or otherwise-broken attempt.
        cleanup_error: str | None = None
        try:
            if passed:
                _commit_accepted_result(root, dispatch_id=dispatch_id, work_id=lease.package_id)
            else:
                _restore_worktree_to_baseline(root, baseline_sha=result.baseline_sha)
        except Exception as exc:
            # A cleanup failure on an otherwise-accepted result must not
            # be reported as COMPLETED -- an accepted result the
            # governed system could not durably commit is not safe to
            # certify. A cleanup failure on an already-rejected result
            # changes nothing about its own FAILED status; it is
            # recorded purely for diagnosis (the NEXT dispatch attempt
            # will independently, safely fail closed on
            # WORKTREE_NOT_CLEAN regardless, rather than silently
            # running on top of undiscarded residue).
            passed = False
            cleanup_error = str(exc)
        receipt: dict[str, object] = {
            "dispatch_id": dispatch_id,
            "lease_id": lease.lease_id,
            "package_id": lease.package_id,
            "status": "COMPLETED" if passed else "FAILED",
            "exit_code": result.exit_code,
            "timed_out": result.timed_out,
            "authority_clean": result.authority_clean,
            "changed_paths": list(result.changed_paths),
            "violations": [{"path": v.path, "reason": v.reason} for v in result.violations],
            "stdout_digest": result.stdout_digest,
            "stderr_digest": result.stderr_digest,
        }
        if cleanup_error is not None:
            receipt["worktree_cleanup_error"] = cleanup_error
        _write_receipt(root, dispatch_id, receipt)
        return {
            "dispatch_id": dispatch_id,
            "status": "COMPLETED" if passed else "FAILED",
            "digest": dispatch_id,
        }

    def recover(self, root: Path, dispatch_id: str) -> dict[str, object]:
        receipt = _read_receipt(root, dispatch_id)
        if receipt is None:
            # Should not normally happen -- dispatch_once() always writes
            # a RUNNING receipt before loop.py could ever have learned
            # this dispatch_id. Treated as "cannot confirm completion",
            # the same non-committal default CallableDispatchPort itself
            # falls back to -- never guessed as COMPLETED/FAILED.
            return {"dispatch_id": dispatch_id, "status": "RUNNING"}
        return {
            "dispatch_id": dispatch_id,
            "status": str(receipt.get("status", "RUNNING")),
            "digest": dispatch_id,
        }

    def find_active_dispatch_id(self, root: Path, *, lease_id: str) -> str | None:
        # The MOST RECENT attempt for this lease -- the one a crash could
        # plausibly have interrupted before the loop's own state learned
        # its id. Earlier, already-superseded attempts (a completed
        # remediation retry) are not "active"; this returns None only when
        # NO attempt at all has ever been recorded for this lease.
        base = _dispatch_id_for(lease_id)
        attempt = 0
        found: str | None = None
        while True:
            candidate = f"{base}:{attempt}"
            if _read_receipt(root, candidate) is None:
                break
            found = candidate
            attempt += 1
        return found


__all__ = [
    "PACKAGE_ID",
    "RECEIPTS_RELATIVE",
    "LocalDispatchError",
    "LocalProcessDispatchPort",
]
