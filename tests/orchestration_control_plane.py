"""Shared control-plane fixture for AS-ORCH-001D-R3 dispatcher tests."""

from __future__ import annotations

import json
from pathlib import Path

CONTROL_PLANE_ROOT = Path(__file__).resolve().parents[1] / "atlas-vault-documentation"
DOCUMENTATION_SKILL_ROOT = CONTROL_PLANE_ROOT / "skill"
MDA_FIXTURE = CONTROL_PLANE_ROOT / "tests" / "fixtures" / "bin" / "mda"
DEFAULT_PROJECT_ID = "orch-dispatch"
DEFAULT_VAULT_ID = "atlas-orch-dispatch"
DEFAULT_VAULT_UUID = "orch-dispatch-uuid"
DOCUMENTATION_SKILL_ID = "atlas-vault-documentation"
DOCUMENTATION_SKILL_VERSION = "1.0.0"
DOCUMENTATION_SKILL_SHA256 = "e830c4fcec547640ecb618c4d80d0256c39b49cf7075f4af57aaf7b38dc40ee9"


def install_managed_control_plane(workspace: Path) -> Path:
    """Install project.yaml, vault identity, and readiness for real preflight."""
    root = workspace.expanduser().resolve()
    atlas = root / ".atlas"
    atlas.mkdir(parents=True, exist_ok=True)
    registry = atlas / "readiness.yaml"
    adapters = ("ide-agent-v1", "generic-cli-v1")
    lines = ["schema_version: 1", "adapters:"]
    for adapter_id in adapters:
        lines.extend(
            [
                f"  {adapter_id}:",
                f"    skill_version: {DOCUMENTATION_SKILL_VERSION}",
                f"    skill_sha256: {DOCUMENTATION_SKILL_SHA256}",
                "    rehearsal_status: passed",
                "    revoked: false",
            ]
        )
    registry.write_text("\n".join(lines) + "\n", encoding="utf-8")
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
