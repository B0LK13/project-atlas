import json
from pathlib import Path
import pytest
from project_atlas.migrations.claim_v2_migration import migrate_v2

def test_migrate_v2_creates_alias_map_and_receipt(tmp_path: Path):
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "sources").mkdir()
    (vault / ".atlas").mkdir()

    # Just test that it can run without errors when the git history is empty or not a repo
    # The current implementation fails gracefully if not a git repo, or if git fails.
    result = migrate_v2(vault, "test-project")

    assert result["status"] == "success"
    assert "receipt" in result
    
    alias_map_path = vault / "state" / "claim-alias-map.json"
    assert alias_map_path.exists()
    
    with alias_map_path.open() as f:
        alias_map = json.load(f)
        assert isinstance(alias_map, dict)

def test_migrate_v2_idempotent(tmp_path: Path):
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "sources").mkdir()
    (vault / ".atlas").mkdir()

    result1 = migrate_v2(vault, "test-project")
    assert result1["status"] == "success"

    result2 = migrate_v2(vault, "test-project")
    assert result2["status"] == "idempotent"

def test_migrate_v2_lockfile(tmp_path: Path):
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / ".atlas").mkdir()

    lockfile = vault / ".atlas" / "test-project-v2-migration.lock"
    lockfile.touch()

    with pytest.raises(RuntimeError, match="Migration locked"):
        migrate_v2(vault, "test-project")
