"""Shared control-plane fixture for AS-ORCH-001D dispatcher tests.

Test MDA is an explicit harness dependency. It is never installed into
production runtime state. Production ``prepare_event_pipeline``,
``bootstrap_start``, and ``document_event`` cannot observe this provider.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from project_atlas.agent_control.runtime import (
    MdaProvider,
    probe_mda_version,
    scoped_mda_environment,
)

CONTROL_PLANE_ROOT = Path(__file__).resolve().parents[1] / "atlas-vault-documentation"
DOCUMENTATION_SKILL_ROOT = CONTROL_PLANE_ROOT / "skill"
MDA_FIXTURE = CONTROL_PLANE_ROOT / "tests" / "fixtures" / "bin" / "mda"
DEFAULT_PROJECT_ID = "orch-dispatch"
DEFAULT_VAULT_ID = "atlas-orch-dispatch"
DEFAULT_VAULT_UUID = "orch-dispatch-uuid"
DOCUMENTATION_SKILL_ID = "atlas-vault-documentation"
DOCUMENTATION_SKILL_VERSION = "1.0.0"
DOCUMENTATION_SKILL_SHA256 = "e830c4fcec547640ecb618c4d80d0256c39b49cf7075f4af57aaf7b38dc40ee9"
_ADAPTER = "project_atlas.orchestration.canonical_session_receipt"


def explicit_test_mda_provider(path: Path | None = None) -> MdaProvider:
    """Construct a test-only provider. Production resolution never calls this."""
    candidate = (path if path is not None else MDA_FIXTURE).expanduser().resolve()
    if not candidate.is_file():
        raise FileNotFoundError(candidate)
    digest = hashlib.sha256()
    with candidate.open("rb") as handle:
        while True:
            chunk = handle.read(65_536)
            if not chunk:
                break
            digest.update(chunk)
    return MdaProvider(
        command=candidate,
        source="test_injection",
        version=probe_mda_version(candidate),
        path_digest=digest.hexdigest(),
    )


def bind_test_mda_pipeline(
    monkeypatch: pytest.MonkeyPatch,
    provider: MdaProvider | None = None,
) -> MdaProvider:
    """Patch the dispatcher adapter only. Production runtime stays unpatched."""
    chosen = provider if provider is not None else explicit_test_mda_provider()

    def prepare_event_pipeline() -> MdaProvider:
        return chosen

    def bootstrap_start(
        *,
        project_root: Path,
        vault_root: Path | None,
        agent_type: str,
        agent_value: str | None,
        task_id: str,
        skill_root: Path,
    ) -> tuple[dict[str, Any], dict[str, str]]:
        from project_atlas.agent_control.runtime import ensure_control_plane_importable

        ensure_control_plane_importable()
        from agent_control.bootstrap import start

        with scoped_mda_environment(chosen):
            return start(
                project_root=project_root,
                vault_root=vault_root,
                agent_type=agent_type,
                agent_value=agent_value,
                task_id=task_id,
                skill_root=skill_root,
            )

    def document_event(
        *,
        vault_root: Path,
        session_id: str,
        event_type: str,
        summary: str,
        work_package: str | None = None,
        validation: list[str] | None = None,
        decision: list[str] | None = None,
        changed_files: list[str] | None = None,
        spool: bool = False,
    ) -> dict[str, Any]:
        from project_atlas.agent_control.runtime import ensure_control_plane_importable

        ensure_control_plane_importable()
        from agent_control.event_client import document

        with scoped_mda_environment(chosen):
            return document(
                vault_root=vault_root,
                session_id=session_id,
                event_type=event_type,
                summary=summary,
                work_package=work_package,
                validation=validation,
                decision=decision,
                changed_files=changed_files,
                spool=spool,
            )

    monkeypatch.setattr(f"{_ADAPTER}.prepare_event_pipeline", prepare_event_pipeline)
    monkeypatch.setattr(f"{_ADAPTER}.bootstrap_start", bootstrap_start)
    monkeypatch.setattr(f"{_ADAPTER}.document_event", document_event)
    return chosen


def restore_production_event_pipeline(monkeypatch: pytest.MonkeyPatch) -> None:
    """Re-bind the adapter to production lifecycle functions."""
    from project_atlas.agent_control import runtime

    monkeypatch.setattr(f"{_ADAPTER}.prepare_event_pipeline", runtime.prepare_event_pipeline)
    monkeypatch.setattr(f"{_ADAPTER}.bootstrap_start", runtime.bootstrap_start)
    monkeypatch.setattr(f"{_ADAPTER}.document_event", runtime.document_event)


def install_managed_control_plane(workspace: Path) -> Path:
    """Install project.yaml, vault identity, and CLI readiness for real preflight.

    ``generic-cli-v1`` is authorized. ``ide-agent-v1`` stays pending so tests
    prove IDE pending readiness is not used. Does not install an MDA provider.
    """
    root = workspace.expanduser().resolve()
    atlas = root / ".atlas"
    atlas.mkdir(parents=True, exist_ok=True)
    registry = atlas / "readiness.yaml"
    registry.write_text(
        "schema_version: 1\n"
        "adapters:\n"
        "  generic-cli-v1:\n"
        f"    skill_version: {DOCUMENTATION_SKILL_VERSION}\n"
        f"    skill_sha256: {DOCUMENTATION_SKILL_SHA256}\n"
        "    rehearsal_status: passed\n"
        "    revoked: false\n"
        "  ide-agent-v1:\n"
        f"    skill_version: {DOCUMENTATION_SKILL_VERSION}\n"
        f"    skill_sha256: {DOCUMENTATION_SKILL_SHA256}\n"
        "    rehearsal_status: pending\n"
        "    revoked: false\n",
        encoding="utf-8",
    )
    (atlas / "project.yaml").write_text(
        "schema_version: 1\n"
        "project:\n"
        f"  id: {DEFAULT_PROJECT_ID}\n"
        "  name: Orchestration Dispatch\n"
        "documentation:\n"
        "  require_receipt: true\n"
        "  strict: true\n"
        f"  skill_id: {DOCUMENTATION_SKILL_ID}\n"
        f"  readiness_registry: {registry}\n"
        "vault:\n"
        f"  required_vault_id: {DEFAULT_VAULT_ID}\n",
        encoding="utf-8",
    )
    (atlas / "vault.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "vault_id": DEFAULT_VAULT_ID,
                "vault_uuid": DEFAULT_VAULT_UUID,
            }
        ),
        encoding="utf-8",
    )
    return root
