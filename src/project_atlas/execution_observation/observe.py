"""Compose live observations into a sealed ExecutionIdentity + ObservationReceipt.

``observe_execution`` is the single entry point. It never writes (see
``store.py``), never reads a clock, and seals only through the canonical
``seal_execution_identity`` / ``seal_observation_receipt`` mint paths.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

from pydantic import ValidationError

from atlas_contracts.execution_identity import ExecutionIdentity, seal_execution_identity
from atlas_contracts.identity import safe_relative_component
from atlas_contracts.observation_receipt import (
    ObservationReceipt,
    ObservationReceiptError,
    seal_observation_receipt,
)
from project_atlas.execution_observation.git import (
    DEFAULT_BASE_REF,
    GitObservation,
    observe_git,
)
from project_atlas.execution_observation.host import (
    EnvironmentObservation,
    ToolchainObservation,
    observe_environment,
    observe_observer_version,
    observe_toolchain,
)
from project_atlas.execution_observation.runner import (
    DEFAULT_TIMEOUT_SECONDS,
    CommandRunner,
    ObservationError,
    SubprocessRunner,
    resolve_executable,
)

OBSERVER_NAME: Final[str] = "atlas-execution-observer"
SLICE_ID: Final[str] = "ULT-01b-1"
# Owner decision O3: the dedicated capability name, registered in
# project_atlas.authz as privileged and default-off (owner-approved pinned
# exception OG-ULT-01B-1-AUTHZ-EXECUTION-OBSERVE-20260909). The CLI gate
# requires explicit elevation through ATLAS_CLI_ELEVATE_CAPS.
OBSERVE_CAPABILITY: Final[str] = "execution.observe"


@dataclass(frozen=True)
class ObservationOutcome:
    identity: ExecutionIdentity
    receipt: ObservationReceipt


def _string_values(payload: object) -> list[str]:
    found: list[str] = []
    if isinstance(payload, str):
        found.append(payload)
    elif isinstance(payload, Mapping):
        for key, value in payload.items():
            found.append(str(key))
            found.extend(_string_values(value))
    elif isinstance(payload, (list, tuple)):
        for item in payload:
            found.extend(_string_values(item))
    return found


def _scan_for_secrets(record: Mapping[str, Any]) -> None:
    from project_atlas.secrets import scan_text

    names: set[str] = set()
    for text in _string_values(record):
        names.update(finding.pattern for finding in scan_text(text))
    if names:
        raise ObservationError(
            "OBSERVATION_SECRET_FORBIDDEN",
            f"secret-shaped content in observation: {', '.join(sorted(names))}",
        )


def _identity_payload(
    project_id: str,
    git_obs: GitObservation,
    env: EnvironmentObservation,
    tools: ToolchainObservation,
) -> dict[str, Any]:
    environment: dict[str, Any] = {"status": env.status}
    if env.status == "OBSERVED":
        environment.update({"os": env.os, "arch": env.arch, "python": env.python})
    toolchain: dict[str, Any] = {"status": tools.status}
    if tools.status == "OBSERVED":
        toolchain["tools"] = [{"name": name, "version": version} for name, version in tools.tools]
    return {
        "project_id": project_id,
        "source": {
            "kind": "git",
            "repository": git_obs.repository,
            "base_head": git_obs.base_head,
            "base_tree": git_obs.base_tree,
            "candidate_head": git_obs.candidate_head,
            "candidate_tree": git_obs.candidate_tree,
        },
        "environment": environment,
        "toolchain": toolchain,
        "agent": {"status": "UNKNOWN"},
        "context": {"status": "UNKNOWN"},
        "capabilities": {"status": "UNKNOWN"},
    }


def _receipt_payload(
    project_id: str,
    identity: ExecutionIdentity,
    git_obs: GitObservation,
    env: EnvironmentObservation,
    tools: ToolchainObservation,
    observer_version: tuple[str, str],
) -> dict[str, Any]:
    env_dim: dict[str, Any] = {"status": env.status, "arch_raw": env.arch_raw}
    if env.status == "OBSERVED":
        env_dim["method"] = "platform+sys"
        env_dim["method_refs"] = ["platform.system", "platform.machine", "sys.version_info"]
    else:
        env_dim["reason"] = env.reason
    tool_dim: dict[str, Any] = {
        "status": tools.status,
        "declared": list(tools.declared),
        "absent": list(tools.absent),
    }
    if tools.status == "OBSERVED":
        tool_dim["method"] = "importlib.metadata+git"
        tool_dim["method_refs"] = ["importlib.metadata.version", "git --version"]
    else:
        tool_dim["reason"] = tools.reason
    return {
        "project_id": project_id,
        "identity": identity.to_record(),
        "identity_digest": identity.identity_digest,
        "observer": {
            "kind": "tool",
            "name": OBSERVER_NAME,
            "version": observer_version[0],
            "version_status": observer_version[1],
        },
        "observed": {
            "source": {
                "status": "OBSERVED",
                "method": "git",
                "method_refs": list(git_obs.method_refs),
                "base_ref": git_obs.base_ref,
                "remote_name": git_obs.remote_name,
                "worktree_clean": git_obs.worktree_clean,
                "shallow": git_obs.shallow,
                "git_version": git_obs.git_version,
                "git_executable_path_digest": git_obs.executable_path_digest,
            },
            "environment": env_dim,
            "toolchain": tool_dim,
            "agent": {"status": "UNKNOWN", "reason": "NOT_OBSERVABLE_IN_THIS_SLICE"},
            "context": {"status": "UNKNOWN", "reason": "NO_CONTEXT_DIGEST_SOURCE"},
            "capabilities": {"status": "UNKNOWN", "reason": "NOT_OBSERVABLE_IN_THIS_SLICE"},
        },
    }


def observe_execution(
    repo_root: Path | str,
    *,
    project_id: str,
    base_ref: str = DEFAULT_BASE_REF,
    remote_name: str | None = None,
    runner: CommandRunner | None = None,
    git_executable: Path | None = None,
    environ: Mapping[str, str] | None = None,
    environment: EnvironmentObservation | None = None,
    toolchain: ToolchainObservation | None = None,
    observer_version: tuple[str, str] | None = None,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
) -> ObservationOutcome:
    """Observe live state and seal it. Raises ``ObservationError``; writes nothing."""
    try:
        pid = safe_relative_component(project_id, label="project id")
    except ValueError as exc:
        raise ObservationError("UNSAFE_PROJECT_ID", "project id is not a safe component") from exc
    active_runner = runner if runner is not None else SubprocessRunner(environ=environ)
    git = git_executable if git_executable is not None else resolve_executable("git")
    git_obs = observe_git(
        repo_root,
        runner=active_runner,
        git=git,
        base_ref=base_ref,
        remote_name=remote_name,
        timeout=timeout,
    )
    env = environment if environment is not None else observe_environment()
    tools = (
        toolchain if toolchain is not None else observe_toolchain(git_version=git_obs.git_version)
    )
    version = observer_version if observer_version is not None else observe_observer_version()
    try:
        identity = seal_execution_identity(_identity_payload(pid, git_obs, env, tools))
    except (ValidationError, ValueError) as exc:
        raise ObservationError(
            "IDENTITY_UNSEALABLE", "observed values did not seal into an execution identity"
        ) from exc
    try:
        receipt = seal_observation_receipt(
            _receipt_payload(pid, identity, git_obs, env, tools, version)
        )
    except (ValidationError, ObservationReceiptError, ValueError) as exc:
        raise ObservationError(
            "RECEIPT_UNSEALABLE", "observation did not seal into a receipt"
        ) from exc
    _scan_for_secrets(receipt.to_record())
    return ObservationOutcome(identity=identity, receipt=receipt)


__all__ = [
    "OBSERVER_NAME",
    "OBSERVE_CAPABILITY",
    "SLICE_ID",
    "ObservationOutcome",
    "observe_execution",
]
