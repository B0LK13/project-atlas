import json
import subprocess
from pathlib import Path

import pytest

from project_atlas.migrations.claim_v2_migration import _v1_claim_id, _v2_claim_id, migrate_v2

pytestmark = pytest.mark.integration
def run_git(args: list[str], cwd: Path) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True)

def test_historical_completeness(tmp_path: Path):
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "sources").mkdir()
    (vault / "state").mkdir()
    
    run_git(["init"], vault)
    run_git(["config", "user.name", "Test"], vault)
    run_git(["config", "user.email", "test@test.com"], vault)
    
    old_file = vault / "sources" / "old-doc.md"
    old_file.write_text("# Old Doc {#doc}\n\n- decision: rename me\n", encoding="utf-8")
    run_git(["add", "sources/old-doc.md"], vault)
    run_git(["commit", "-m", "first"], vault)
    
    run_git(["mv", "sources/old-doc.md", "sources/new-doc.md"], vault)
    run_git(["commit", "-m", "second"], vault)
    
    sources_json = vault / "state" / "sources.json"
    sources_json.write_text(json.dumps({
        "schema_version": 1,
        "sources": [
            {
                "source_id": "new-doc",
                "source_lineage_id": "lineage-123",
                "current_path": "sources/new-doc.md",
                "path_history": [
                    {"path": "sources/old-doc.md"}
                ]
            }
        ]
    }), encoding="utf-8")
    
    result = migrate_v2(vault, "test-project")
    assert result["status"] == "success"

    alias_map_path = vault / "state" / "claim-alias-map.json"
    alias_map = json.loads(alias_map_path.read_text(encoding="utf-8"))

    v1_id = _v1_claim_id("test-project", "old-doc", "decision", "decision", "rename me")
    v2_id = _v2_claim_id("test-project", "lineage-123", "decision", "decision", "heading:doc")

    by_v1 = {record["v1_claim_id"]: record for record in alias_map["aliases"]}
    assert v1_id in by_v1
    assert by_v1[v1_id]["v2_claim_id"] == v2_id
    assert by_v1[v1_id]["source_lineage_id"] == "lineage-123"
    assert by_v1[v1_id]["stable_semantic_locator"] == "heading:doc"
    assert by_v1[v1_id]["source_path"] == "sources/old-doc.md"
