"""Governed mutating execution port. Consumes a lease; never grants one.

MUTATING_PORT_IS_AUTHORITY = NO
MERGE_AUTHORIZED = FALSE
DIRECT_MAIN = FALSE
001D_ASK_TRANSPORT_UNCHANGED = YES
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from collections.abc import Iterable
from enum import StrEnum
from pathlib import Path
from typing import Final, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from project_atlas.orchestration.autonomy.evidence import hash_payload
from project_atlas.orchestration.autonomy.models import CANONICAL_REPOSITORY_IDENTITY
from project_atlas.orchestration.autonomy.trust import require_full_pin
from project_atlas.source_identity import IdentityLockError, ProjectIdentityLock

MUTATING_PORT_PACKAGE_ID: Final[str] = "AS-ORCH-CONTINUATION-BROKER-001"
WORKER_PROMPT_SUPPRESSION: Final[str] = (
    "DO NOT ASK HUMAN FOR ROUTINE NEXT STEP. "
    "WHEN UNCERTAIN: RETURN MACHINE BLOCKER TO PRIMARY GOVERNOR. "
    "DO NOT TERMINATE THE PROJECT DAG. "
    "DO NOT REQUEST MERGE AUTHORITY. "
    "DO NOT CHOOSE OWNER POLICY."
)
_FORBIDDEN_WORKER_COMMANDS: Final[frozenset[str]] = frozenset(
    {
        "git push main",
        "git push --force",
        "git push -f",
        "git rebase",
        "git merge",
    }
)
_ALLOWED_ACP_KINDS: Final[frozenset[str]] = frozenset(
    {
        "read_repo",
        "edit_worktree",
        "run_tests",
        "git_status",
        "git_diff",
        "git_add_package",
        "git_commit_package",
        "git_push_governed_branch",
    }
)


class MutatingTransportError(ValueError):
    """Fail-closed mutating transport error. Not an authority grant."""

    code = "MUTATING_TRANSPORT_FAILED_CLOSED"

    def __init__(self, message: str, *, code: str | None = None) -> None:
        super().__init__(message)
        if code is not None:
            self.code = code


class MutatingRole(StrEnum):
    IMPLEMENTER = "IMPLEMENTER"
    REMEDIATOR = "REMEDIATOR"


class WorkerBackendType(StrEnum):
    CLOUD_API = "CLOUD_API"
    LOCAL_ACP = "LOCAL_ACP"
    LOCAL_AGENT = "LOCAL_AGENT"
    PROCESS = "PROCESS"
    NONE = "NONE"


class WorkerQuestionClass(StrEnum):
    IMPLEMENTATION_CHOICE = "IMPLEMENTATION_CHOICE"
    ROUTINE_NEXT_STEP = "ROUTINE_NEXT_STEP"
    RECOVERABLE_FAILURE = "RECOVERABLE_FAILURE"
    SAFE_DEFAULT_AVAILABLE = "SAFE_DEFAULT_AVAILABLE"
    OWNER_AUTHORITY_REQUIRED = "OWNER_AUTHORITY_REQUIRED"


class MutatingLeaseBinding(BaseModel):
    """Lease-derived launch binding. Not owner authority."""

    model_config = ConfigDict(extra="forbid")

    package_id: str = Field(min_length=1, max_length=128)
    lease_id: str = Field(min_length=1, max_length=128)
    dispatch_id: str = Field(min_length=1, max_length=128)
    cycle_id: str = Field(min_length=1, max_length=128)
    repository_identity: str = Field(min_length=1, max_length=256)
    base_main: str = Field(min_length=40, max_length=40)
    role: MutatingRole
    allowed_paths: tuple[str, ...] = Field(min_length=1, max_length=32)
    branch: str = Field(min_length=1, max_length=256)
    worktree: str = Field(min_length=1, max_length=256)
    merge_authorized: Literal[False] = False
    direct_main: Literal[False] = False

    @field_validator("base_main")
    @classmethod
    def _pin(cls, value: str) -> str:
        return require_full_pin(value, "mutating base main")

    @field_validator("branch", "worktree")
    @classmethod
    def _not_main(cls, value: str) -> str:
        lowered = value.replace("\\", "/").rstrip("/").split("/")[-1].lower()
        if lowered in {"main", "master"}:
            raise ValueError("mutating worker cannot target the main worktree")
        return value

    @model_validator(mode="after")
    def _no_authority(self) -> MutatingLeaseBinding:
        if self.merge_authorized or self.direct_main:
            raise ValueError("mutating binding cannot carry merge or direct-main authority")
        return self


class MutatingLaunchReceipt(BaseModel):
    model_config = ConfigDict(extra="forbid")

    backend: WorkerBackendType
    agent_id: str
    run_id: str
    status: str
    recovered: bool = False
    merge_authorized: Literal[False] = False


class MutatingExecutionPort(Protocol):
    """Launch or recover one leased mutating worker. Not a governor."""

    def start(self, binding: MutatingLeaseBinding, prompt: str) -> MutatingLaunchReceipt:
        """Start exactly one worker for a valid lease."""

    def recover(self, agent_id: str, run_id: str) -> MutatingLaunchReceipt:
        """Reconcile an existing worker. Must not spawn a duplicate."""

    def follow_up(self, agent_id: str, prompt: str) -> MutatingLaunchReceipt:
        """Start exactly one follow-up run on an existing worker lineage."""


def classify_worker_question(text: str) -> WorkerQuestionClass:
    """A worker question is not automatically an owner question."""
    lowered = text.lower()
    if any(token in lowered for token in ("merge to main", "owner grant", "waiver", "force push")):
        return WorkerQuestionClass.OWNER_AUTHORITY_REQUIRED
    routine = ("should i continue", "what next", "how should i proceed")
    if any(token in lowered for token in routine):
        return WorkerQuestionClass.ROUTINE_NEXT_STEP
    if "retry" in lowered or "timeout" in lowered or "429" in lowered:
        return WorkerQuestionClass.RECOVERABLE_FAILURE
    if "which implementation" in lowered or "prefer" in lowered:
        return WorkerQuestionClass.IMPLEMENTATION_CHOICE
    return WorkerQuestionClass.SAFE_DEFAULT_AVAILABLE


def decide_acp_permission(kind: str, binding: MutatingLeaseBinding) -> Literal["ALLOW", "REJECT"]:
    """Default REJECT. Allow only package-compatible actions."""
    del binding
    if kind in _ALLOWED_ACP_KINDS:
        return "ALLOW"
    return "REJECT"


def command_is_forbidden(command: str) -> bool:
    lowered = " ".join(command.lower().split())
    if any(token in lowered for token in _FORBIDDEN_WORKER_COMMANDS):
        return True
    return "push" in lowered and "main" in lowered


def require_active_lease(
    leases: Iterable[object] | None,
    binding: MutatingLeaseBinding,
) -> None:
    """Port consumes an existing lease. It never mints one."""
    items = tuple(leases) if leases is not None else ()
    for item in items:
        lease_id = getattr(item, "lease_id", None)
        package_id = getattr(item, "package_id", None)
        active = getattr(item, "active", False)
        if lease_id == binding.lease_id and package_id == binding.package_id and active:
            return
    raise MutatingTransportError(
        "mutating worker requires an active governor lease",
        code="LEASE_MISSING",
    )


def compose_worker_prompt(objective: str) -> str:
    return f"{objective.strip()}\n\n{WORKER_PROMPT_SUPPRESSION}"


def _inside(root: Path, target: Path) -> bool:
    try:
        target.relative_to(root)
    except ValueError:
        return False
    return True


class ProcessMutatingBackend:
    """Real OS-process mutating backend. Isolated worktree only. Not Cursor Ask."""

    output_filename = "implemented.txt"
    kind = "MUTATING"

    def __init__(self, *, root: Path, store: Path, sleep_seconds: float = 0.0) -> None:
        self._root = root.resolve()
        self._store = store
        self._store.mkdir(parents=True, exist_ok=True)
        self._lock = self._store / ".mutating.lock"
        self._sleep_seconds = max(0.0, sleep_seconds)
        self.start_calls = 0

    def start(self, binding: MutatingLeaseBinding, prompt: str) -> MutatingLaunchReceipt:
        self._validate_binding(binding)
        worktree = self._resolve_worktree(binding.worktree)
        if worktree.exists() and worktree.is_symlink():
            raise MutatingTransportError("worktree symlink is forbidden", code="SYMLINK_STATE")
        worktree.mkdir(parents=True, exist_ok=True)
        existing = self._load_active(binding.package_id)
        if existing is not None and existing.get("status") in {"CREATING", "RUNNING"}:
            return self.recover(str(existing["agent_id"]), str(existing["run_id"]))
        self.start_calls += 1
        agent_id = f"proc-{binding.package_id}"
        script = worktree / "governed_worker.py"
        result_path = worktree / "result.json"
        script.write_text(
            "import json, pathlib, sys, time\n"
            f"root = pathlib.Path({str(worktree)!r})\n"
            "payload = json.loads(sys.argv[1])\n"
            "time.sleep(float(payload.get('sleep', 0)))\n"
            "out = root / payload['file']\n"
            "if '..' in pathlib.Path(payload['file']).parts:\n"
            "    raise SystemExit(2)\n"
            "out.write_text(payload['body'], encoding='utf-8')\n"
            "pathlib.Path(payload['result']).write_text("
            "json.dumps({'status':'FINISHED'}), encoding='utf-8')\n",
            encoding="utf-8",
        )
        payload = json.dumps(
            {
                "file": self.output_filename,
                "body": f"{binding.package_id}\n{compose_worker_prompt(prompt)}\n",
                "result": str(result_path),
                "sleep": self._sleep_seconds,
                "kind": self.kind,
            },
            sort_keys=True,
        )
        try:
            with ProjectIdentityLock(self._lock, wait_seconds=2.0, stale_seconds=30.0):
                proc = subprocess.Popen(
                    [sys.executable, str(script), payload],
                    cwd=worktree,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
        except IdentityLockError as exc:
            raise MutatingTransportError("mutating lock is held", code="CONCURRENT_WORKER") from exc
        run_id = f"prun-{proc.pid}"
        record = {
            "agent_id": agent_id,
            "run_id": run_id,
            "pid": proc.pid,
            "status": "RUNNING",
            "package_id": binding.package_id,
            "lease_id": binding.lease_id,
            "worktree": str(worktree),
            "worktree_relative": binding.worktree,
            "base_main": binding.base_main,
            "repository_identity": binding.repository_identity,
            "kind": self.kind,
            "digest": hash_payload({"agent_id": agent_id, "run_id": run_id}),
        }
        self._persist_active(binding.package_id, record)
        return MutatingLaunchReceipt(
            backend=WorkerBackendType.PROCESS,
            agent_id=agent_id,
            run_id=run_id,
            status="RUNNING",
        )

    def recover(self, agent_id: str, run_id: str) -> MutatingLaunchReceipt:
        record = self._find(agent_id, run_id)
        if record is None:
            raise MutatingTransportError("unknown mutating worker", code="UNKNOWN_WORKER")
        pid = int(str(record["pid"]))
        running = _pid_running(pid)
        result = Path(str(record["worktree"])) / "result.json"
        if result.is_file():
            record["status"] = "FINISHED"
            self._persist_active(str(record["package_id"]), record)
            return MutatingLaunchReceipt(
                backend=WorkerBackendType.PROCESS,
                agent_id=agent_id,
                run_id=run_id,
                status="FINISHED",
                recovered=True,
            )
        if running:
            return MutatingLaunchReceipt(
                backend=WorkerBackendType.PROCESS,
                agent_id=agent_id,
                run_id=run_id,
                status="RUNNING",
                recovered=True,
            )
        record["status"] = "ERROR"
        self._persist_active(str(record["package_id"]), record)
        return MutatingLaunchReceipt(
            backend=WorkerBackendType.PROCESS,
            agent_id=agent_id,
            run_id=run_id,
            status="ERROR",
            recovered=True,
        )

    def follow_up(self, agent_id: str, prompt: str) -> MutatingLaunchReceipt:
        record = self._find(agent_id, None)
        if record is None:
            raise MutatingTransportError("unknown mutating worker lineage", code="UNKNOWN_WORKER")
        active = str(record.get("status")) in {"CREATING", "RUNNING"}
        if active and _pid_running(int(str(record["pid"]))):
            return self.recover(agent_id, str(record["run_id"]))
        binding = MutatingLeaseBinding(
            package_id=str(record["package_id"]),
            lease_id=str(record["lease_id"]),
            dispatch_id=f"follow-{agent_id}",
            cycle_id="follow-up",
            repository_identity=str(
                record.get("repository_identity") or CANONICAL_REPOSITORY_IDENTITY
            ),
            base_main=str(record.get("base_main") or "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"),
            role=MutatingRole.IMPLEMENTER,
            allowed_paths=("implemented.txt",),
            branch="cursor/governed-worker",
            worktree=str(record.get("worktree_relative") or "workers/follow"),
        )
        return self.start(binding, prompt)

    def _validate_binding(self, binding: MutatingLeaseBinding) -> None:
        if binding.merge_authorized or binding.direct_main:
            raise MutatingTransportError("merge/direct-main is forbidden", code="AUTHORITY_DENIED")
        worktree = binding.worktree.replace("\\", "/")
        if worktree in {".", ""} or ".." in Path(worktree).parts:
            raise MutatingTransportError("worktree path is unsafe", code="PATH_UNSAFE")

    def _resolve_worktree(self, relative: str) -> Path:
        if Path(relative).is_absolute() or ".." in Path(relative).parts:
            raise MutatingTransportError("worktree path is unsafe", code="PATH_UNSAFE")
        target = (self._root / relative).resolve()
        if not _inside(self._root, target):
            raise MutatingTransportError("worktree escapes root", code="PATH_UNSAFE")
        return target

    def _persist_active(self, package_id: str, record: dict[str, object]) -> None:
        path = self._store / f"{package_id}.json"
        encoded = json.dumps(record, sort_keys=True, indent=2)
        tmp = path.with_name(f".{path.name}.tmp")
        tmp.write_text(encoded + "\n", encoding="utf-8")
        os.replace(tmp, path)

    def _load_active(self, package_id: str) -> dict[str, object] | None:
        path = self._store / f"{package_id}.json"
        if not path.is_file():
            return None
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise MutatingTransportError("worker record corrupt", code="STATE_CORRUPT")
        return payload

    def _find(self, agent_id: str, run_id: str | None) -> dict[str, object] | None:
        for path in sorted(self._store.glob("*.json")):
            payload = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(payload, dict):
                continue
            if payload.get("agent_id") != agent_id:
                continue
            if run_id is None or payload.get("run_id") == run_id:
                return payload
        return None


def pid_is_running(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def _pid_running(pid: int) -> bool:
    return pid_is_running(pid)


def cloud_api_key_present() -> bool:
    return bool(os.environ.get("CURSOR_API_KEY"))


def local_cursor_cli_present() -> bool:
    from shutil import which

    return which("agent") is not None or which("cursor-agent") is not None


class ProcessReadOnlyBackend(ProcessMutatingBackend):
    """Real OS-process read-only verifier. Worktree write only. Not Agent-mode mutation."""

    output_filename = "verified.txt"
    kind = "READONLY"
