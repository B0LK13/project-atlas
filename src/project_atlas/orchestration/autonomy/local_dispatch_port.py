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
is always ``(*argv_template, <absolute path to a governed request JSON
file>)`` -- the fixed template decides HOW to interpret that file; this
port never interprets task content itself, and never implies Cursor,
OpenAI, Anthropic, network access, or API billing (mirrors
``local_process_transport.py``'s own non-claims).

ISOLATED PER-ATTEMPT WORKTREE (IV findings, PR #662 review rounds 1-2):
every dispatch attempt runs inside a fresh ``git worktree`` checked out
from the lease's own ``base_pin`` -- never inside the project root's own
working tree, and never reused across attempts. This is the "lease
worktree" pipeline stage the directive's own design names explicitly.
Two independent adversarial IV rounds both rejected an earlier version
of this module that instead ran every attempt directly against the
shared project root and tried to restore/commit it clean between
attempts (``git reset --hard``/``git commit`` against ``root`` itself):
round 1 found that left the shared root permanently dirty after ANY
outcome (blocking every later dispatch, including a legitimate
remediation retry of the very same lease); round 2 found the
restore/commit step's own failure path (a missing git identity, an
embedded ``.git`` inside the changed tree, a task that self-commits)
reproduced the exact same lockout under realistic conditions its own
tests never exercised, AND that auto-committing onto whatever branch
``root`` happened to have checked out bypasses this codebase's own
established ``RESULT_ADAPTER_CAN_AUTHORIZE_MERGE = NO`` contract
(``dispatcher.py``'s ``AS-ORCH-001D-RESULT-BINDING-001``) with no
review/binding gate in between. Per-attempt worktree isolation removes
the entire bug class rather than patching around it again: each
attempt's worktree starts life freshly checked out (so
``local_process_transport.py``'s own ``_require_clean_worktree()``
precondition trivially holds every time, for every attempt, regardless
of what any other attempt or any other lease did), an attempt's
in-scope changes are left as real, inspectable, UNCOMMITTED working-tree
state on its own disposable branch (never committed onto ``root``'s
checked-out branch, never merged, never claiming merge/execution
authority -- a later, separate result-binding step is what would ever
promote them), and the project root's own working tree is never touched
by a dispatch at all. Worktrees are durable evidence, kept (not deleted)
after an attempt finishes -- like every other durable record this
package keeps (receipts, lease projection rows) -- so accumulation over
a long-running governed session is an explicit, disclosed, deferred
cleanup concern for a future reaper (mirroring this package's own
existing release/reaper precedent for leases), not a correctness gap.
"""

from __future__ import annotations

import hashlib
import json
import re
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

#: Where per-attempt isolated worktrees are checked out, relative to the
#: project root -- a sibling of the receipts store, same convention.
WORKTREES_RELATIVE: Final[Path] = RECEIPTS_RELATIVE / "worktrees"

_DISPATCH_ID_PREFIX: Final[str] = "local-process:"
_BRANCH_PREFIX: Final[str] = "atlas-local-dispatch/"
_SAFE_TOKEN_RE = re.compile(r"[^A-Za-z0-9._-]+")


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


def _safe_token(dispatch_id: str) -> str:
    # dispatch_id contains ':' (from _dispatch_id_for's prefix), which is
    # not a safe filename character on Windows and not a safe git branch
    # component either -- substitute for filenames/branch names ONLY; the
    # logical dispatch_id string used in every comparison/return value is
    # never altered.
    return _SAFE_TOKEN_RE.sub("_", dispatch_id)


def _receipt_filename(dispatch_id: str) -> str:
    return _safe_token(dispatch_id) + ".json"


def _receipts_dir(root: Path) -> Path:
    resolved_root = root.expanduser().resolve()
    target = (resolved_root / RECEIPTS_RELATIVE).resolve()
    if not target.is_relative_to(resolved_root):
        raise LocalDispatchError("receipt store path escapes project root", code="PATH_UNSAFE")
    return target


def _worktree_path(root: Path, dispatch_id: str) -> Path:
    resolved_root = root.expanduser().resolve()
    target = (resolved_root / WORKTREES_RELATIVE / _safe_token(dispatch_id)).resolve()
    if not target.is_relative_to(resolved_root):
        raise LocalDispatchError("dispatch worktree path escapes project root", code="PATH_UNSAFE")
    return target


def _dispatch_branch_name(dispatch_id: str) -> str:
    return f"{_BRANCH_PREFIX}{_safe_token(dispatch_id)}"


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


def _supervisor_git_status(root: Path) -> str:
    """The supervisor checkout's own tracked-file status -- must read
    IDENTICAL before and after every dispatch attempt. An isolated
    per-attempt worktree (see module docstring) gives GIT-level
    isolation (its own branch/index), never OS-level sandboxing:
    nothing stops a launched process from using an absolute or
    ``../``-traversal path to reach back into ``root``'s own checkout
    regardless of its own cwd. This is the supervisor-side half of that
    check (tracked files); see ``_protected_state_digest`` for the
    other half (the gitignored durable governance state)."""
    result = subprocess.run(
        ["git", "status", "--porcelain"], cwd=root, check=True, capture_output=True, text=True,
        timeout=30,
    )
    return result.stdout


def _protected_state_digest(root: Path, *, receipts_dir: Path) -> str:
    """Content digest of every file under ``.atlas/orchestration/`` --
    the durable governance state (lease projection, loop state,
    origination projection, every dispatch's own receipts) a dispatch
    attempt must never be able to touch -- EXCLUDING this port's own
    receipts store (``receipts_dir``), which ``dispatch_once()`` itself
    legitimately writes to before and after every attempt (compared
    exactly by identity there, not blindly content-hashed here).
    ``.atlas/orchestration/`` is gitignored, so ``_supervisor_git_status``
    alone never sees a mutation here -- this is what closes that blind
    spot for the SAME class of attack (an escape via an absolute/
    traversal path from inside the isolated worktree, or from a
    completely unrelated concurrent process).

    Scope note: ``WORKTREES_RELATIVE`` lives inside ``RECEIPTS_RELATIVE``,
    so excluding ``receipts_dir`` also excludes every dispatch's own
    worktree content -- deliberately: this guard's job is confirming the
    supervisor's LIVE governance state (lease projection, loop state,
    origination projection) survives one dispatch attempt uncorrupted,
    not policing the historical contents of a DIFFERENT, already-
    completed attempt's own disposable worktree.
    """
    orchestration_dir = (root / ".atlas" / "orchestration").resolve()
    if not orchestration_dir.is_dir():
        return hashlib.sha256(b"").hexdigest()
    resolved_receipts_dir = receipts_dir.resolve()
    hasher = hashlib.sha256()
    for path in sorted(orchestration_dir.rglob("*")):
        if not path.is_file():
            continue
        if path.resolve().is_relative_to(resolved_receipts_dir):
            continue
        hasher.update(path.relative_to(orchestration_dir).as_posix().encode("utf-8"))
        hasher.update(path.read_bytes())
    return hasher.hexdigest()


def _supervisor_integrity_violation(
    root: Path, *, receipts_dir: Path, status_before: str, state_before: str
) -> str | None:
    """Re-snapshot ``root`` and compare against the "before" snapshot a
    caller captured earlier -- returns a short, human-readable violation
    description if anything outside this dispatch's own receipt-writing
    changed, ``None`` if the supervisor checkout is confirmed
    byte-for-byte unchanged. See ``_supervisor_git_status``/
    ``_protected_state_digest`` docstrings for what each half covers."""
    status_after = _supervisor_git_status(root)
    state_after = _protected_state_digest(root, receipts_dir=receipts_dir)
    if status_before == status_after and state_before == state_after:
        return None
    parts = []
    if status_before != status_after:
        parts.append("tracked-file status changed")
    if state_before != state_after:
        parts.append("governance state under .atlas/orchestration/ changed")
    return "supervisor checkout was not byte-clean throughout the attempt: " + ", ".join(parts)


def _create_dispatch_worktree(root: Path, *, dispatch_id: str, base_pin: str) -> Path:
    """Check out a fresh, disposable ``git worktree`` for exactly one
    dispatch attempt, on its own never-reused branch, starting at the
    lease's own ``base_pin`` -- never at whatever ``root`` currently has
    checked out. Never reused across attempts: a fresh dispatch_id (this
    port's own attempt-indexing, unchanged) always means a fresh branch
    name and a fresh worktree path, so there is no stale state from a
    prior attempt to reset or clean -- the checkout itself already start
    from ``local_process_transport.py``'s own required clean baseline.

    Raises (via the underlying ``git`` command's non-zero exit,
    surfaced as ``subprocess.CalledProcessError``) if the branch or path
    somehow already exists, or ``base_pin`` does not resolve -- both
    genuine, real failures this function never swallows; the caller
    treats this the same as any other dispatch-attempt failure.
    """
    resolved_root = root.expanduser().resolve()
    path = _worktree_path(resolved_root, dispatch_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    branch = _dispatch_branch_name(dispatch_id)
    _run_git(
        ["worktree", "add", "-b", branch, str(path), base_pin],
        cwd=resolved_root,
        timeout_seconds=60,
    )
    return path


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
        resolved_root = root.expanduser().resolve()
        lease = _single_active_lease(resolved_root)
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
            existing = _read_receipt(resolved_root, dispatch_id)
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
            resolved_root,
            dispatch_id,
            {
                "dispatch_id": dispatch_id,
                "lease_id": lease.lease_id,
                "package_id": lease.package_id,
                "status": "RUNNING",
            },
        )
        request_path = _receipts_dir(resolved_root) / f"{_safe_token(dispatch_id)}-request.json"
        _write_json_atomic(request_path, _request_payload(lease, dispatch_id=dispatch_id))

        # Supervisor-checkout integrity guard (explicit adversarial
        # requirement, PR #662): captured AFTER this dispatch's own
        # legitimate writes above (both live under `_receipts_dir`,
        # already excluded from `_protected_state_digest`) and compared
        # again once the attempt finishes, BEFORE this dispatch's own
        # final receipt write. Isolated-worktree containment is a git-
        # level property only; this is the independent, filesystem-level
        # check that `resolved_root` itself -- tracked files AND the
        # gitignored durable governance state alike -- stayed byte-for-
        # byte identical throughout, regardless of what the attempt did
        # inside its own worktree or attempted via an absolute/traversal
        # path.
        receipts_dir = _receipts_dir(resolved_root)
        guard_status_before = _supervisor_git_status(resolved_root)
        guard_state_before = _protected_state_digest(resolved_root, receipts_dir=receipts_dir)

        try:
            worktree_path = _create_dispatch_worktree(
                resolved_root, dispatch_id=dispatch_id, base_pin=lease.base_pin
            )
            envelope = LocalTaskEnvelope(
                work_id=lease.package_id,
                # An ABSOLUTE path -- the child process's cwd is the
                # isolated worktree, a different directory than
                # `resolved_root`, so a root-relative path (this port's
                # pre-isolation design) would not resolve there.
                argv=(*self._argv_template, str(request_path)),
                authorized_paths=lease.authorized_paths,
                forbidden_paths=lease.forbidden_paths,
            )
            result = run_local_task(envelope, self._config, project_root=worktree_path)
        except Exception as exc:
            # dispatch_once() must never let an ordinary task-execution
            # failure escape as an uncaught exception -- loop.py's
            # _dispatch_leased() does not wrap this call in a try/except,
            # so an uncaught exception here would crash the whole tick
            # rather than cleanly finalize the node as failed. Genuine
            # protocol violations (no active lease, duplicate dispatch)
            # are raised ABOVE this point, before any process starts;
            # everything past that point -- including a failure to even
            # create the isolated worktree -- is treated as this
            # dispatch's own, cleanly-reported outcome. The guard is
            # still checked here: a crash partway through must not give
            # a launched process a free pass on the same integrity
            # requirement a clean completion is held to.
            failure_payload: dict[str, object] = {
                "dispatch_id": dispatch_id,
                "lease_id": lease.lease_id,
                "package_id": lease.package_id,
                "status": "FAILED",
                "error": str(exc),
            }
            guard_violation = _supervisor_integrity_violation(
                resolved_root,
                receipts_dir=receipts_dir,
                status_before=guard_status_before,
                state_before=guard_state_before,
            )
            if guard_violation is not None:
                failure_payload["supervisor_integrity_violation"] = guard_violation
            _write_receipt(resolved_root, dispatch_id, failure_payload)
            return {"dispatch_id": dispatch_id, "status": "FAILED", "digest": dispatch_id}

        passed = result.exit_code == 0 and result.authority_clean
        # No commit/restore step against `resolved_root` needed here (IV
        # findings, PR #662 review rounds 1-2, see module docstring) --
        # the attempt ran entirely inside its own isolated worktree,
        # which is left exactly as the attempt produced it (an accepted
        # result's in-scope changes stay real, inspectable, UNCOMMITTED
        # working-tree state on the attempt's own disposable branch,
        # never touching `resolved_root`'s own working tree at all) --
        # so `resolved_root` itself is never dirtied by any dispatch,
        # and no subsequent dispatch (a legitimate remediation retry of
        # this SAME lease, or a completely unrelated lease) can ever be
        # blocked by a prior attempt's leftover state.
        worktree_relative = worktree_path.relative_to(resolved_root).as_posix()
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
            "worktree": worktree_relative,
        }
        guard_violation = _supervisor_integrity_violation(
            resolved_root,
            receipts_dir=receipts_dir,
            status_before=guard_status_before,
            state_before=guard_state_before,
        )
        if guard_violation is not None:
            # An accepted result the supervisor's own checkout integrity
            # cannot vouch for is not safe to certify, regardless of
            # what the isolated worktree itself reported.
            passed = False
            receipt["status"] = "FAILED"
            receipt["supervisor_integrity_violation"] = guard_violation
        _write_receipt(resolved_root, dispatch_id, receipt)
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
    "WORKTREES_RELATIVE",
    "LocalDispatchError",
    "LocalProcessDispatchPort",
]
