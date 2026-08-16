"""Shared control-plane fixture for AS-ORCH-001D dispatcher tests."""

from __future__ import annotations

import json
from pathlib import Path

from project_atlas.agent_control.runtime import (
    clear_test_mda_provider,
    inject_test_mda_provider,
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


def install_managed_control_plane(workspace: Path, *, inject_mda: bool = True) -> Path:
    """Install project.yaml, vault identity, and CLI readiness for real preflight.

    ``generic-cli-v1`` is authorized. ``ide-agent-v1`` stays pending so tests
    prove IDE pending readiness is not used. The repository MDA fixture is
    injected only when ``inject_mda`` is true.
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
    if inject_mda:
        inject_test_mda_provider(MDA_FIXTURE)
    else:
        clear_test_mda_provider()
    return root
