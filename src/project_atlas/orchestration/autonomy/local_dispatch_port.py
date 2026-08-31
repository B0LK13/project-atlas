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
"""

from __future__ import annotations

import json
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
        _write_receipt(
            root,
            dispatch_id,
            {
                "dispatch_id": dispatch_id,
                "lease_id": lease.lease_id,
                "package_id": lease.package_id,
                "status": "COMPLETED" if passed else "FAILED",
                "exit_code": result.exit_code,
                "timed_out": result.timed_out,
                "authority_clean": result.authority_clean,
                "changed_paths": list(result.changed_paths),
                "violations": [
                    {"path": v.path, "reason": v.reason} for v in result.violations
                ],
                "stdout_digest": result.stdout_digest,
                "stderr_digest": result.stderr_digest,
            },
        )
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
