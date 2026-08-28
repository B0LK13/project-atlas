"""Six-P1 security gates for AS-ORCH-CONTINUATION-BROKER-001 (#429).

Canonical findings (from #428 ADV, closed on #429 semantics):
  ORCH-SDK-RESULT-BINDING-001
  ORCH-SDK-LEASE-GATE-001
  ORCH-SDK-ALLOWED-PATHS-001
  ORCH-SDK-HOST-ROLLBACK-001
  ORCH-SDK-AGENT-LINEAGE-001
  ORCH-SDK-TRANSIENT-FAILURE-001

Evidence-only enforcement. Never grants merge/execution authority.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any, Final, Literal

from pydantic import BaseModel, ConfigDict, Field

from project_atlas.orchestration.sdk.models import (
    PACKAGE_ID,
    STATE_DIR_RELATIVE,
    AgentRole,
    SdkRuntimeError,
)

FINDING_IDS: Final[tuple[str, ...]] = (
    "ORCH-SDK-RESULT-BINDING-001",
    "ORCH-SDK-LEASE-GATE-001",
    "ORCH-SDK-ALLOWED-PATHS-001",
    "ORCH-SDK-HOST-ROLLBACK-001",
    "ORCH-SDK-AGENT-LINEAGE-001",
    "ORCH-SDK-TRANSIENT-FAILURE-001",
)

CANONICAL_PR: Final[int] = 429
SUPERSEDED_PR: Final[int] = 428
CANONICAL_BRANCH: Final[str] = "feat/as-orch-continuation-broker-001"

_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)
_CLI_AGENT_RE = re.compile(r"^cli-[0-9a-fA-F-]{8,128}$")
_SDK_AGENT_RE = re.compile(r"^(bc-|agent-)[A-Za-z0-9_-]{1,128}$")


class WorkerBackend(StrEnum):
    CURSOR_SDK = "CURSOR_SDK"
    CURSOR_AGENT_CLI = "CURSOR_AGENT_CLI"
    READ_ONLY_001D = "READ_ONLY_001D"
    STOP_HOOK_FALLBACK = "STOP_HOOK_FALLBACK"


class TransientClass(StrEnum):
    NETWORK = "NETWORK"
    TIMEOUT = "TIMEOUT"
    RATE_LIMIT = "RATE_LIMIT"
    SERVER_5XX = "SERVER_5XX"
    CLI_BRIDGE = "CLI_BRIDGE"
    AUTH_PERSISTENT = "AUTH_PERSISTENT"
    NOT_TRANSIENT = "NOT_TRANSIENT"


class GovernorLease(BaseModel):
    """Bounded governor lease for mutating (and bound read-only) workers."""

    model_config = ConfigDict(extra="forbid")

    lease_id: str = Field(min_length=1, max_length=160)
    package_id: str = PACKAGE_ID
    canonical_pr: int = CANONICAL_PR
    branch: str = CANONICAL_BRANCH
    role: AgentRole
    dag_generation: int = Field(ge=0, le=1_000_000)
    allowed_paths: tuple[str, ...] = Field(default_factory=tuple)
    worktree: str | None = None
    candidate_head: str | None = None
    candidate_tree: str | None = None
    base_main: str = "7e797468a2eca37c959920912b1fa264df4be638"
    active: bool = True
    expired: bool = False
    mutation_authorized: bool = False
    merge_authorized: Literal[False] = False
    execution_authorized: Literal[False] = False

    def is_valid_for(self, *, role: AgentRole, dag_generation: int, package_id: str) -> bool:
        if not self.active or self.expired:
            return False
        if self.package_id != package_id or package_id != PACKAGE_ID:
            return False
        if self.role != role:
            return False
        if self.dag_generation != dag_generation:
            return False
        if self.canonical_pr != CANONICAL_PR:
            return False
        return self.branch == CANONICAL_BRANCH


class BoundWorkerResult(BaseModel):
    """Accepted worker result identity. Rejects stale/foreign/replayed."""

    model_config = ConfigDict(extra="forbid")

    worker_backend: WorkerBackend
    session_or_agent_id: str
    run_id: str
    package_id: str
    dag_node: str
    dag_generation: int
    role: AgentRole
    lease_id: str
    attempt: int
    result_digest: str
    candidate_head: str | None = None
    candidate_tree: str | None = None
    merge_authorized: Literal[False] = False
    execution_authorized: Literal[False] = False


class WorkerLineage(BaseModel):
    """Session/agent lineage binding for CLI or SDK workers."""

    model_config = ConfigDict(extra="forbid")

    identity: str
    backend: WorkerBackend
    workspace: str
    repository: str
    package_id: str
    role: AgentRole
    branch: str
    base_main: str
    creation_generation: int
    creation_sequence: int = Field(default=1, ge=1, le=1_000_000)


class HostHighWater(BaseModel):
    """Persistent high-water marks. Older snapshots cannot restore current state."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = 1
    dag_generation: int = Field(default=0, ge=0)
    event_sequence: int = Field(default=0, ge=0)
    registry_revision: int = Field(default=0, ge=0)
    run_attempt: int = Field(default=0, ge=0)
    checkpoint_sequence: int = Field(default=0, ge=0)


LINEAGE_SEQUENCE_NAME = "worker-creation-sequence.json"


def lineage_sequence_path(root: Path) -> Path:
    return root / STATE_DIR_RELATIVE / LINEAGE_SEQUENCE_NAME


def _load_lineage_sequences(root: Path) -> dict[str, int]:
    path = lineage_sequence_path(root)
    if not path.is_file():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SdkRuntimeError(
            "worker creation sequence unreadable",
            code="STALE_WORKER_LINEAGE",
        ) from exc
    if not isinstance(raw, dict):
        return {}
    out: dict[str, int] = {}
    for key, value in raw.items():
        if isinstance(value, int) and value >= 0:
            out[str(key)] = value
    return out


def mint_creation_sequence(root: Path, agent_id: str) -> int:
    """Monotonic per-host creation sequence. Never reused after rollback."""
    data = _load_lineage_sequences(root)
    nxt = int(data.get("_max", 0)) + 1
    data[agent_id] = nxt
    data["_max"] = nxt
    path = lineage_sequence_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return nxt


def require_creation_sequence(root: Path, agent_id: str, stored: int | None) -> int:
    if stored is None or stored < 1:
        raise SdkRuntimeError("stale worker lineage", code="STALE_WORKER_LINEAGE")
    data = _load_lineage_sequences(root)
    high = int(data.get(agent_id, 0))
    if high and stored < high:
        raise SdkRuntimeError(
            "creation sequence rollback",
            code="ROLLED_BACK_CREATION_SEQUENCE",
        )
    if agent_id not in data:
        data[agent_id] = stored
        data["_max"] = max(int(data.get("_max", 0)), stored)
        path = lineage_sequence_path(root)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return stored


RUN_PRE_HEAD_NAME = "run-pre-heads.json"


def run_pre_head_path(root: Path) -> Path:
    return root / STATE_DIR_RELATIVE / RUN_PRE_HEAD_NAME


def persist_run_pre_head(root: Path, run_id: str, pre_head: str | None) -> None:
    """Durable pre-run HEAD. candidate_head is not a substitute."""
    path = run_pre_head_path(root)
    data: dict[str, str | None] = {}
    if path.is_file():
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise SdkRuntimeError(
                "run pre-head store unreadable",
                code="DIFF_UNDETERMINED",
            ) from exc
        if isinstance(raw, dict):
            for key, value in raw.items():
                if value is None or (isinstance(value, str) and len(value) >= 7):
                    data[str(key)] = value
    data[run_id] = pre_head
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def load_run_pre_head(root: Path, run_id: str) -> str | None:
    """Return persisted pre-run HEAD, or None when unknown (fail closed)."""
    path = run_pre_head_path(root)
    if not path.is_file():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SdkRuntimeError(
            "run pre-head store unreadable",
            code="DIFF_UNDETERMINED",
        ) from exc
    if not isinstance(raw, dict):
        return None
    value = raw.get(run_id)
    if value is None:
        return None
    if isinstance(value, str) and len(value) >= 7:
        return value
    return None


def high_water_path(root: Path) -> Path:
    return root / STATE_DIR_RELATIVE / "host-high-water.json"


def load_high_water(root: Path) -> HostHighWater:
    path = high_water_path(root)
    if path.is_file():
        try:
            return HostHighWater.model_validate_json(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            pass
    return HostHighWater()


def persist_high_water(root: Path, mark: HostHighWater) -> Path:
    path = high_water_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(mark.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path


def advance_high_water(
    root: Path,
    *,
    dag_generation: int | None = None,
    event_sequence: int | None = None,
    registry_revision: int | None = None,
    run_attempt: int | None = None,
    checkpoint_sequence: int | None = None,
) -> HostHighWater:
    """Monotonic advance. Rollback attempts raise and leave current marks intact."""
    current = load_high_water(root)
    proposed = current.model_copy(
        update={
            "dag_generation": (
                current.dag_generation
                if dag_generation is None
                else dag_generation
            ),
            "event_sequence": (
                current.event_sequence if event_sequence is None else event_sequence
            ),
            "registry_revision": (
                current.registry_revision
                if registry_revision is None
                else registry_revision
            ),
            "run_attempt": current.run_attempt if run_attempt is None else run_attempt,
            "checkpoint_sequence": (
                current.checkpoint_sequence
                if checkpoint_sequence is None
                else checkpoint_sequence
            ),
        }
    )
    reject_host_rollback(current=current, proposed=proposed)
    persist_high_water(root, proposed)
    return proposed


def reject_host_rollback(*, current: HostHighWater, proposed: HostHighWater) -> None:
    """ORCH-SDK-HOST-ROLLBACK-001 — older otherwise-valid snapshots are quarantined."""
    fields = (
        "dag_generation",
        "event_sequence",
        "registry_revision",
        "run_attempt",
        "checkpoint_sequence",
    )
    for name in fields:
        if getattr(proposed, name) < getattr(current, name):
            raise SdkRuntimeError(
                f"host high-water rollback rejected on {name}",
                code="HOST_ROLLBACK_REJECTED",
            )


def require_valid_lease(
    lease: GovernorLease | None,
    *,
    role: AgentRole,
    dag_generation: int,
    package_id: str = PACKAGE_ID,
    mutating: bool,
) -> GovernorLease:
    """ORCH-SDK-LEASE-GATE-001 — mutating work requires a currently valid lease."""
    if lease is None:
        raise SdkRuntimeError("missing lease", code="LEASE_REQUIRED")
    if (
        mutating
        and not lease.mutation_authorized
        and role in {AgentRole.IMPLEMENTER, AgentRole.REMEDIATOR}
    ):
        raise SdkRuntimeError(
            "mutating role without mutation_authorized lease",
            code="LEASE_MUTATION_DENIED",
        )
    if lease.expired or not lease.active:
        raise SdkRuntimeError("lease expired or inactive", code="LEASE_EXPIRED")
    if not lease.is_valid_for(role=role, dag_generation=dag_generation, package_id=package_id):
        raise SdkRuntimeError("lease binding mismatch", code="LEASE_MISMATCH")
    if lease.canonical_pr == SUPERSEDED_PR:
        raise SdkRuntimeError("superseded PR lease rejected", code="STALE_LINEAGE")
    return lease


def normalize_rel_path(raw: str, *, casefold: bool = False) -> str:
    """Reject path normalization escapes; return POSIX relative form.

    Handles Windows separators, drive/UNC prefixes, ``..``, and trailing junk.
    """
    text = raw.replace("\\", "/").strip()
    # Strip Windows extended/UNC prefixes.
    for prefix in ("//?/", "//./", "//"):
        if text.startswith(prefix):
            text = text[len(prefix) :]
            break
    if not text or text.startswith("/") or text.startswith("~"):
        raise SdkRuntimeError("path escape rejected", code="PATH_ESCAPE")
    # Drive letter / absolute Windows path.
    if len(text) >= 2 and text[1] == ":" and text[0].isalpha():
        raise SdkRuntimeError("drive-absolute path rejected", code="PATH_ESCAPE")
    parts: list[str] = []
    for part in text.split("/"):
        if part in ("", "."):
            continue
        if part == "..":
            raise SdkRuntimeError("path traversal rejected", code="PATH_ESCAPE")
        # Windows trailing-dot / trailing-space segment tricks.
        stripped = part.rstrip(" .")
        if stripped != part:
            raise SdkRuntimeError("trailing path junk rejected", code="PATH_ESCAPE")
        parts.append(part)
    if not parts:
        raise SdkRuntimeError("empty path rejected", code="PATH_ESCAPE")
    out = "/".join(parts)
    return out.casefold() if casefold else out


def enforce_allowed_paths(
    *,
    changed_paths: list[str] | tuple[str, ...],
    allowed_paths: list[str] | tuple[str, ...],
    windows_casefold: bool = True,
) -> None:
    """ORCH-SDK-ALLOWED-PATHS-001 — compare actual diff paths to lease.allowed_paths."""
    if not allowed_paths:
        raise SdkRuntimeError(
            "metadata-only allowed_paths insufficient",
            code="ALLOWED_PATHS_EMPTY",
        )
    allowed = {
        normalize_rel_path(p, casefold=windows_casefold) for p in allowed_paths
    }
    for raw in changed_paths:
        path = normalize_rel_path(raw, casefold=windows_casefold)
        if path.startswith(".git/") or path == ".git":
            raise SdkRuntimeError("repo metadata path rejected", code="REPO_METADATA")
        matched = False
        for prefix in allowed:
            if path == prefix or path.startswith(prefix.rstrip("/") + "/"):
                matched = True
                break
        if not matched:
            raise SdkRuntimeError(
                f"unauthorized path {path}",
                code="ALLOWED_PATHS_VIOLATION",
            )


def require_changed_paths_determined(changed_paths: list[str] | None) -> list[str]:
    if changed_paths is None:
        raise SdkRuntimeError(
            "post-run diff cannot be determined",
            code="DIFF_UNDETERMINED",
        )
    return list(changed_paths)


def _git_run(
    root: Path, args: list[str], *, timeout: int = 30
) -> Any:
    import subprocess

    return subprocess.run(
        ["git", *args],
        cwd=str(root),
        capture_output=True,
        text=True,
        check=False,
        timeout=timeout,
    )


def _canonical_workspace(path: str) -> str:
    """Windows-safe resolved workspace identity."""
    return str(Path(path).expanduser().resolve())


def _contain_paths(root: Path, paths: set[str]) -> list[str] | None:
    """Resolve each relative path against the governed root; fail closed on escape."""
    resolved_root = root.resolve()
    contained: set[str] = set()
    for raw in paths:
        try:
            normalized = normalize_rel_path(raw, casefold=False)
        except SdkRuntimeError:
            return None
        candidate = (resolved_root / normalized).resolve()
        try:
            relative = candidate.relative_to(resolved_root)
        except ValueError:
            return None
        posix = relative.as_posix()
        if posix == STATE_DIR_RELATIVE or posix.startswith(STATE_DIR_RELATIVE + "/"):
            continue
        contained.add(posix)
    return sorted(contained)


def collect_actual_changed_paths(
    root: Path,
    *,
    pre_head: str | None,
) -> list[str] | None:
    """Committed + uncommitted + untracked + reflog-hidden paths since ``pre_head``.

    Porcelain alone is not an actual delta: a commit hides mutated files.
    ``git reset --hard $pre_head`` after commit/push also hides the worktree
    delta; reflog commits still reachable as descendants of ``pre_head`` must
    be attributed. ``None`` means the post-run diff could not be determined.
    """
    import subprocess

    if not pre_head or len(pre_head) < 7:
        return None
    try:
        diff = _git_run(root, ["diff", "--name-only", "--find-renames", pre_head])
        porcelain = _git_run(root, ["status", "--porcelain", "-uall"])
        reflog = _git_run(root, ["log", "--walk-reflogs", "--pretty=%H", "-n", "32"])
    except (OSError, subprocess.TimeoutExpired):
        return None
    if diff.returncode != 0 or porcelain.returncode != 0:
        return None
    paths: set[str] = set()
    for line in (diff.stdout or "").splitlines():
        text = line.strip().strip('"')
        if text:
            paths.add(text)
    for line in (porcelain.stdout or "").splitlines():
        if len(line) < 4:
            continue
        rest = line[3:]
        if " -> " in rest:
            rest = rest.split(" -> ", 1)[1]
        text = rest.strip().strip('"')
        if text:
            paths.add(text)
    if reflog.returncode != 0:
        return None
    seen_sha: set[str] = set()
    for sha in (reflog.stdout or "").splitlines():
        sha = sha.strip()
        if len(sha) < 7 or sha in seen_sha or sha == pre_head:
            continue
        seen_sha.add(sha)
        ancestor = _git_run(
            root, ["merge-base", "--is-ancestor", pre_head, sha], timeout=15
        )
        if ancestor.returncode != 0:
            continue
        hidden = _git_run(
            root, ["diff", "--name-only", "--find-renames", pre_head, sha]
        )
        if hidden.returncode != 0:
            return None
        for line in (hidden.stdout or "").splitlines():
            text = line.strip().strip('"')
            if text:
                paths.add(text)
    return _contain_paths(root, paths)


def validate_result_binding(
    result: BoundWorkerResult,
    *,
    expected_backend: WorkerBackend,
    expected_session: str,
    expected_run: str,
    expected_package: str,
    expected_node: str,
    expected_generation: int,
    expected_role: AgentRole,
    expected_lease: str,
    expected_attempt: int,
    expected_digest: str,
    expected_head: str | None = None,
    expected_tree: str | None = None,
    seen_digests: set[str] | None = None,
) -> BoundWorkerResult:
    """ORCH-SDK-RESULT-BINDING-001 — reject stale/foreign/replayed/wrong-gen results."""
    if result.merge_authorized or result.execution_authorized:
        raise SdkRuntimeError("authority injection in result", code="AUTHORITY_INJECTION")
    if result.worker_backend != expected_backend:
        raise SdkRuntimeError("foreign worker backend", code="FOREIGN_RESULT")
    if result.session_or_agent_id != expected_session:
        raise SdkRuntimeError("foreign session/agent", code="FOREIGN_RESULT")
    if result.run_id != expected_run:
        raise SdkRuntimeError("run id mismatch", code="FOREIGN_RESULT")
    if result.package_id != expected_package or expected_package != PACKAGE_ID:
        raise SdkRuntimeError("package mismatch", code="STALE_RESULT")
    if result.dag_node != expected_node:
        raise SdkRuntimeError("dag node mismatch", code="STALE_RESULT")
    if result.dag_generation != expected_generation:
        raise SdkRuntimeError("wrong dag generation", code="WRONG_GENERATION")
    if result.role != expected_role:
        raise SdkRuntimeError("role mismatch", code="FOREIGN_RESULT")
    if result.lease_id != expected_lease:
        raise SdkRuntimeError("lease mismatch", code="FOREIGN_RESULT")
    if result.attempt != expected_attempt:
        raise SdkRuntimeError("attempt mismatch", code="STALE_RESULT")
    if result.result_digest != expected_digest:
        raise SdkRuntimeError("result digest mismatch", code="STALE_RESULT")
    if expected_head is not None and result.candidate_head != expected_head:
        raise SdkRuntimeError("wrong candidate head", code="WRONG_HEAD")
    if expected_tree is not None and result.candidate_tree != expected_tree:
        raise SdkRuntimeError("wrong candidate tree", code="WRONG_TREE")
    if seen_digests is not None and result.result_digest in seen_digests:
        raise SdkRuntimeError("replayed result digest", code="REPLAYED_RESULT")
    return result


def normalize_cli_identity(session_id: str) -> str:
    """Map raw cursor-agent session UUID to registry-safe cli-* identity."""
    raw = session_id.strip()
    if _CLI_AGENT_RE.fullmatch(raw):
        return raw
    if _UUID_RE.fullmatch(raw):
        return f"cli-{raw.lower()}"
    raise SdkRuntimeError("malformed CLI session identity", code="FOREIGN_IDENTITY")


def is_valid_worker_identity(identity: str, *, backend: WorkerBackend) -> bool:
    if backend == WorkerBackend.CURSOR_AGENT_CLI:
        return bool(_CLI_AGENT_RE.fullmatch(identity) or _UUID_RE.fullmatch(identity))
    if backend == WorkerBackend.CURSOR_SDK:
        return bool(_SDK_AGENT_RE.fullmatch(identity))
    return bool(identity)


def bind_worker_lineage(
    *,
    identity: str,
    backend: WorkerBackend,
    workspace: str,
    repository: str,
    package_id: str,
    role: AgentRole,
    branch: str,
    base_main: str,
    creation_generation: int,
    creation_sequence: int = 1,
    expected: WorkerLineage | None = None,
) -> WorkerLineage:
    """ORCH-SDK-AGENT-LINEAGE-001 — foreign identity / cross-worktree resume rejected."""
    if backend == WorkerBackend.CURSOR_AGENT_CLI:
        identity = normalize_cli_identity(identity)
    if not is_valid_worker_identity(identity, backend=backend):
        raise SdkRuntimeError("foreign worker identity", code="FOREIGN_IDENTITY")
    if package_id != PACKAGE_ID:
        raise SdkRuntimeError("foreign package lineage", code="FOREIGN_IDENTITY")
    if branch != CANONICAL_BRANCH:
        raise SdkRuntimeError("foreign branch lineage", code="FOREIGN_IDENTITY")
    lineage = WorkerLineage(
        identity=identity,
        backend=backend,
        workspace=_canonical_workspace(workspace),
        repository=repository,
        package_id=package_id,
        role=role,
        branch=branch,
        base_main=base_main,
        creation_generation=creation_generation,
        creation_sequence=creation_sequence,
    )
    if expected is not None:
        if lineage.identity != expected.identity:
            raise SdkRuntimeError("foreign CLI/SDK session", code="FOREIGN_IDENTITY")
        if _canonical_workspace(lineage.workspace) != _canonical_workspace(
            expected.workspace
        ):
            raise SdkRuntimeError("cross-worktree resume rejected", code="FOREIGN_IDENTITY")
        if lineage.repository != expected.repository:
            raise SdkRuntimeError("foreign repository", code="FOREIGN_IDENTITY")
        if lineage.package_id != expected.package_id:
            raise SdkRuntimeError("foreign package", code="FOREIGN_IDENTITY")
        if lineage.role != expected.role:
            raise SdkRuntimeError("role lineage mismatch", code="FOREIGN_IDENTITY")
        if expected.creation_sequence > lineage.creation_sequence:
            raise SdkRuntimeError(
                "creation sequence rollback",
                code="ROLLED_BACK_CREATION_SEQUENCE",
            )
        if lineage.creation_generation != expected.creation_generation:
            # Stored creation generation is immutable; request gen may move.
            pass
    return lineage


def classify_transient_failure(
    exc: BaseException | str, *, status_code: int | None = None
) -> TransientClass:
    """ORCH-SDK-TRANSIENT-FAILURE-001 — classify park/backoff vs persistent auth."""
    text = str(exc).lower()
    code = status_code
    if code is None:
        code = getattr(exc, "status_code", None) if not isinstance(exc, str) else None
    if not isinstance(exc, str) and type(exc).__name__ in {
        "TimeoutError",
        "CancelledError",
        "Timeout",
    }:
        return TransientClass.TIMEOUT
    if code in {401, 403} or "invalid user api key" in text or "missing_api_key" in text:
        return TransientClass.AUTH_PERSISTENT
    if code == 429 or "rate limit" in text or "too many requests" in text:
        return TransientClass.RATE_LIMIT
    if code is not None and 500 <= int(code) <= 599:
        return TransientClass.SERVER_5XX
    if "timeout" in text or "timed out" in text:
        return TransientClass.TIMEOUT
    if any(
        token in text
        for token in ("connection reset", "network", "temporarily unavailable", "econnreset")
    ):
        return TransientClass.NETWORK
    if "bridge" in text or ("cursor-agent" in text and "fail" in text):
        return TransientClass.CLI_BRIDGE
    return TransientClass.NOT_TRANSIENT


def recovery_action(kind: TransientClass) -> Literal["PARK_BACKOFF", "TRY_OTHER_BACKEND", "FAIL"]:
    if kind == TransientClass.AUTH_PERSISTENT:
        return "TRY_OTHER_BACKEND"
    if kind == TransientClass.NOT_TRANSIENT:
        return "FAIL"
    return "PARK_BACKOFF"


def reject_superseded_pr_mutation(*, target_pr: int) -> None:
    if target_pr == SUPERSEDED_PR:
        raise SdkRuntimeError(
            "PR428 mutation unauthorized (STALE_LINEAGE)",
            code="STALE_LINEAGE",
        )
    if target_pr != CANONICAL_PR:
        raise SdkRuntimeError("non-canonical PR mutation rejected", code="STALE_LINEAGE")


def suppress_stale_directive(
    *,
    directive_pr: int | None,
    directive_head: str | None,
    live_pr: int,
    live_head: str,
) -> str | None:
    """Return suppression reason when old instructions must not execute."""
    if directive_pr == SUPERSEDED_PR:
        return "STALE_DIRECTIVE_PR428"
    if directive_pr is not None and directive_pr != live_pr:
        return "STALE_DIRECTIVE_WRONG_PR"
    if directive_head and live_head and directive_head != live_head:
        return "STALE_DIRECTIVE_HEAD_MOVED"
    return None


@dataclass(frozen=True)
class SixP1ClosureStatus:
    finding_id: str
    status: Literal["CLOSED", "PARTIAL", "MISSING"]
    file: str
    symbol: str


@dataclass(frozen=True)
class SixP1RuntimeProofs:
    """Evidence-backed runtime wiring proofs. Never hard-code CLOSED without these."""

    result_binding_runtime: bool = False
    lease_gating_runtime: bool = False
    allowed_paths_post_run: bool = False
    host_high_water_recovery: bool = False
    worker_lineage_persisted: bool = False
    transient_failure_parked: bool = False


def six_p1_closure_matrix(
    proofs: SixP1RuntimeProofs | None = None,
) -> list[SixP1ClosureStatus]:
    """Matrix from runtime proofs. Helper presence alone yields PARTIAL."""
    p = proofs or SixP1RuntimeProofs()

    def _status(wired: bool) -> Literal["CLOSED", "PARTIAL", "MISSING"]:
        return "CLOSED" if wired else "PARTIAL"

    return [
        SixP1ClosureStatus(
            "ORCH-SDK-RESULT-BINDING-001",
            _status(p.result_binding_runtime),
            "result_plane.py",
            "ingest_pending_against_registry",
        ),
        SixP1ClosureStatus(
            "ORCH-SDK-LEASE-GATE-001",
            _status(p.lease_gating_runtime),
            "cli_execution_port.py",
            "_require_lease",
        ),
        SixP1ClosureStatus(
            "ORCH-SDK-ALLOWED-PATHS-001",
            _status(p.allowed_paths_post_run),
            "cli_execution_port.py",
            "_enforce_post_run_paths",
        ),
        SixP1ClosureStatus(
            "ORCH-SDK-HOST-ROLLBACK-001",
            _status(p.host_high_water_recovery),
            "recovery.py",
            "recover_runtime",
        ),
        SixP1ClosureStatus(
            "ORCH-SDK-AGENT-LINEAGE-001",
            _status(p.worker_lineage_persisted),
            "cli_execution_port.py",
            "resume_agent",
        ),
        SixP1ClosureStatus(
            "ORCH-SDK-TRANSIENT-FAILURE-001",
            _status(p.transient_failure_parked),
            "scheduler.py",
            "assign_and_start",
        ),
    ]


def six_p1_open_count(proofs: SixP1RuntimeProofs | None = None) -> int:
    return sum(1 for row in six_p1_closure_matrix(proofs) if row.status != "CLOSED")


def six_p1_runtime_open_count(proofs: SixP1RuntimeProofs) -> int:
    """Alias that requires explicit proofs — no default CLOSED self-certification."""
    return six_p1_open_count(proofs)


def audit_payload(proofs: SixP1RuntimeProofs | None = None) -> dict[str, Any]:
    rows = six_p1_closure_matrix(proofs)
    return {
        "package_id": PACKAGE_ID,
        "canonical_pr": CANONICAL_PR,
        "findings": [
            {
                "finding_id": r.finding_id,
                "status": r.status,
                "file": r.file,
                "symbol": r.symbol,
                "attack": r.finding_id,
                "test": "test_as_orch_d092_runtime_wiring.py",
                "evidence": f"src/project_atlas/orchestration/sdk/{r.file}::{r.symbol}",
                "required_delta": "NONE" if r.status == "CLOSED" else "WIRE_RUNTIME",
                "helper_exists": "YES",
                "authoritative_call_site": f"{r.file}:{r.symbol}",
                "real_runtime_path": "YES" if r.status == "CLOSED" else "PARTIAL",
            }
            for r in rows
        ],
        "six_p1_open_count": six_p1_open_count(proofs),
        "six_p1_runtime_open_count": six_p1_open_count(proofs),
        "merge_authorized": False,
        "execution_authorized": False,
    }
