"""Historical Claim Identity v2 completeness over real Vault evidence paths."""

import json
import subprocess
from pathlib import Path

import pytest

from project_atlas.migrations.claim_v2_migration import (
    _v1_claim_id,
    _v2_claim_id,
    migrate_v2,
)

pytestmark = pytest.mark.integration

PROJECT_UUID = "00000000-0000-4000-8000-000000000123"


def _run_git(args: list[str], cwd: Path) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True)


def test_historical_completeness_uses_ingested_source_identity(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    imported = vault / "sources" / "imported-documents"
    imported.mkdir(parents=True)
    (vault / "state").mkdir()

    _run_git(["init"], vault)
    _run_git(["config", "user.name", "Test"], vault)
    _run_git(["config", "user.email", "test@test.com"], vault)

    evidence = imported / "source-history.md"
    evidence.write_text(
        "# Decisions\n\n- decision: rename me {#rename-decision}\n",
        encoding="utf-8",
    )
    _run_git(["add", "sources/imported-documents/source-history.md"], vault)
    _run_git(["commit", "-m", "historical evidence"], vault)

    (vault / "state" / "sources.json").write_text(
        json.dumps(
            {
                "schema_version": 2,
                "sources": [
                    {
                        "source_id": "source-history",
                        "source_lineage_id": "sline-history",
                        "canonical_project_id": PROJECT_UUID,
                        "current_path": "docs/DECISIONS.md",
                        "path_history": [{"path": "docs/OLD-DECISIONS.md"}],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    manifests = vault / "sources" / "manifests"
    manifests.mkdir()
    (manifests / "source-manifest.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "sources": [
                    {
                        "source_id": "source-history",
                        "likely_project": "test-project",
                        "project_uuid": PROJECT_UUID,
                        "path": "docs/DECISIONS.md",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    result = migrate_v2(vault, "test-project")
    assert result["status"] == "success"
    alias_map = json.loads(Path(result["alias_map_path"]).read_text(encoding="utf-8"))

    v1_id = _v1_claim_id(
        PROJECT_UUID,
        "sline-history",
        "decision",
        "decision",
        "rename me {#rename-decision}",
    )
    v2_id = _v2_claim_id(
        PROJECT_UUID,
        "sline-history",
        "decision",
        "decision",
        "id:rename-decision",
    )
    by_v1 = {record["v1_claim_id"]: record for record in alias_map["aliases"]}
    assert by_v1[v1_id]["v2_claim_id"] == v2_id
    assert by_v1[v1_id]["source_lineage_id"] == "sline-history"
    assert by_v1[v1_id]["project_identity"] == PROJECT_UUID
    assert by_v1[v1_id]["source_path"] == (
        "sources/imported-documents/source-history.md"
    )


def test_historical_scan_includes_non_markdown_architecture_sources(
    tmp_path: Path,
) -> None:
    vault = tmp_path / "vault"
    imported = vault / "sources" / "imported-documents"
    imported.mkdir(parents=True)
    (vault / "state").mkdir()
    _run_git(["init"], vault)
    _run_git(["config", "user.name", "Test"], vault)
    _run_git(["config", "user.email", "test@test.com"], vault)
    (imported / "source-architecture.txt").write_text(
        "# System\n\nEvent-driven design {#system-design}\n", encoding="utf-8"
    )
    _run_git(["add", "sources/imported-documents/source-architecture.txt"], vault)
    _run_git(["commit", "-m", "text architecture"], vault)
    (vault / "state" / "sources.json").write_text(
        json.dumps(
            {
                "sources": [
                    {
                        "source_id": "source-architecture",
                        "source_lineage_id": "sline-architecture",
                        "canonical_project_id": PROJECT_UUID,
                        "current_path": "docs/ARCHITECTURE.txt",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    result = migrate_v2(vault, "test-project")
    alias_map = json.loads(Path(result["alias_map_path"]).read_text(encoding="utf-8"))
    assert alias_map["audit"]["input_claims"] == 1
    assert alias_map["aliases"][0]["claim_type"] == "architecture-statement"
