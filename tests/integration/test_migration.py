import json
import subprocess
from pathlib import Path

from project_atlas.cli import EXIT_OK, main
from project_atlas.migrations.claim_v2_migration import migrate_v2


def test_migrate_v2_cli_smoke(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "sources").mkdir()
    (vault / ".atlas").mkdir()

    assert main(["migrate-v2", "--vault", str(vault), "--project", "cli-project"]) == EXIT_OK

    alias_map_path = vault / "state" / "claim-alias-map.json"
    assert alias_map_path.exists()
    alias_map = json.loads(alias_map_path.read_text(encoding="utf-8"))
    assert alias_map["project_id"] == "cli-project"


def test_migrate_v2_creates_alias_map_and_receipt(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "sources").mkdir()
    (vault / ".atlas").mkdir()

    result = migrate_v2(vault, "test-project")

    assert result["status"] == "success"
    assert "receipt" in result

    alias_map_path = vault / "state" / "claim-alias-map.json"
    assert alias_map_path.exists()

    alias_map = json.loads(alias_map_path.read_text(encoding="utf-8"))
    assert alias_map["schema_version"] == 1
    assert alias_map["project_id"] == "test-project"
    assert isinstance(alias_map["aliases"], list)
    assert isinstance(alias_map["ambiguous"], list)
    assert alias_map["audit"]["source_commits_scanned"] == 0
    assert alias_map["audit"]["input_claims"] == 0
    assert alias_map["audit"]["output_aliases"] == 0


def test_migrate_v2_idempotent(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "sources").mkdir()
    (vault / ".atlas").mkdir()

    result1 = migrate_v2(vault, "test-project")
    assert result1["status"] == "success"

    result2 = migrate_v2(vault, "test-project")
    assert result2["status"] == "idempotent"
    assert result2["migrated_claims"] == 0


def _run_git(args: list[str], cwd: Path) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True)


def test_migrate_v2_records_ambiguous_locator_mappings(tmp_path: Path) -> None:
    """A v1 claim that resolves to two different v2 locators is recorded as ambiguous."""
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "sources").mkdir()
    (vault / ".atlas").mkdir()

    _run_git(["init"], vault)
    _run_git(["config", "user.name", "Test"], vault)
    _run_git(["config", "user.email", "test@test.com"], vault)

    doc = vault / "sources" / "doc.md"
    doc.write_text("# Heading A {#a}\n\n- decision: keep it\n", encoding="utf-8")
    _run_git(["add", "sources/doc.md"], vault)
    _run_git(["commit", "-m", "first"], vault)

    doc.write_text("# Heading B {#b}\n\n- decision: keep it\n", encoding="utf-8")
    _run_git(["add", "sources/doc.md"], vault)
    _run_git(["commit", "-m", "second"], vault)

    (vault / "state").mkdir(parents=True, exist_ok=True)
    (vault / "state" / "sources.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "sources": [
                    {
                        "source_id": "doc",
                        "source_lineage_id": "lineage-doc",
                        "current_path": "sources/doc.md",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    result = migrate_v2(vault, "ambig-project")
    assert result["status"] == "success"
    assert result["ambiguous_count"] == 1

    alias_map = json.loads((vault / "state" / "claim-alias-map.json").read_text(encoding="utf-8"))
    assert len(alias_map["ambiguous"]) == 1
    expected_reason = "single v1 identity maps to multiple v2 identities"
    assert alias_map["ambiguous"][0]["reason"] == expected_reason
