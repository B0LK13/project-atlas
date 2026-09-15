"""AT3-112 — isolated federation reuse honesty."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from project_atlas.atlas3.contracts import Atlas3Error
from project_atlas.atlas3.federation_reuse import PACKAGE_ID, compile_federation_reuse


def _vault(tmp_path: Path) -> Path:
    vault = tmp_path / "vault"
    (vault / "projects" / "harbor-api").mkdir(parents=True)
    (vault / "projects" / "pilot-web").mkdir(parents=True)
    return vault


def _write_declared(vault: Path, payload: dict[str, object]) -> None:
    path = vault / "generated" / "ops" / "atlas3" / "federation" / "declared.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")


def test_missing_stays_unknown(tmp_path: Path) -> None:
    report = compile_federation_reuse(_vault(tmp_path))
    assert report["package_id"] == PACKAGE_ID
    assert report["status"] == "UNKNOWN"
    assert report["federation_is_authority"] is False
    assert report["cross_vault_promote"] is False
    assert report["new_cli_command"] is False
    assert report["merge_authorization"] == "NOT_GRANTED"
    assert report["write_applied"] is False


def test_composes_declared_members(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    _write_declared(
        vault,
        {
            "federation_id": "harbor-estate",
            "members": [
                {"member_id": "harbor-api", "project_id": "harbor-api"},
                {"member_id": "pilot-web", "project_id": "pilot-web"},
            ],
        },
    )
    report = compile_federation_reuse(vault)
    assert report["status"] == "derived"
    assert report["counts"]["members"] == 2
    assert report["federation_id"] == "harbor-estate"
    assert report["federation_is_authority"] is False


def test_scopes_requested_project(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    _write_declared(
        vault,
        {
            "federation_id": "harbor-estate",
            "members": [
                {"member_id": "harbor-api", "project_id": "harbor-api"},
                {"member_id": "pilot-web", "project_id": "pilot-web"},
            ],
        },
    )
    report = compile_federation_reuse(vault, "harbor-api")
    assert report["project_id"] == "harbor-api"
    assert report["counts"]["members"] == 1
    assert report["members"][0]["project_id"] == "harbor-api"


def test_foreign_request_fails_closed(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    _write_declared(
        vault,
        {
            "federation_id": "harbor-estate",
            "members": [{"member_id": "harbor-api", "project_id": "harbor-api"}],
        },
    )
    with pytest.raises(Atlas3Error) as exc:
        compile_federation_reuse(vault, "pilot-web")
    assert exc.value.code == "PROJECT_NOT_IN_FEDERATION"


def test_cross_promote_fails_closed(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    _write_declared(
        vault,
        {
            "federation_id": "harbor-estate",
            "allow_cross_promote": True,
            "members": [{"member_id": "harbor-api", "project_id": "harbor-api"}],
        },
    )
    with pytest.raises(Atlas3Error) as exc:
        compile_federation_reuse(vault)
    assert exc.value.code == "CROSS_VAULT_PROMOTE"


def test_federation_authority_fails_closed(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    _write_declared(
        vault,
        {
            "federation_id": "harbor-estate",
            "federation_is_authority": True,
            "members": [{"member_id": "harbor-api", "project_id": "harbor-api"}],
        },
    )
    with pytest.raises(Atlas3Error) as exc:
        compile_federation_reuse(vault)
    assert exc.value.code == "FEDERATION_AUTHORITY"


def test_authoritative_level_fails_closed(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    _write_declared(
        vault,
        {
            "federation_id": "harbor-estate",
            "authority": {"level": "authoritative"},
            "members": [{"member_id": "harbor-api", "project_id": "harbor-api"}],
        },
    )
    with pytest.raises(Atlas3Error) as exc:
        compile_federation_reuse(vault)
    assert exc.value.code == "FEDERATION_AUTHORITY"


def test_unknown_project_fails_closed(tmp_path: Path) -> None:
    vault = tmp_path / "empty"
    vault.mkdir()
    with pytest.raises(Atlas3Error) as exc:
        compile_federation_reuse(vault, "harbor-api")
    assert exc.value.code == "UNKNOWN_PROJECT"


def test_corrupt_fails_closed(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    path = vault / "generated" / "ops" / "atlas3" / "federation" / "declared.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{not-json\n", encoding="utf-8")
    with pytest.raises(Atlas3Error) as exc:
        compile_federation_reuse(vault)
    assert exc.value.code == "FEDERATION_CORRUPT"


def test_module_does_not_write() -> None:
    root = Path(__file__).resolve().parents[2]
    source = (root / "src/project_atlas/atlas3/federation_reuse.py").read_text(encoding="utf-8")
    for name in (
        "write_json_atomic",
        "write_text(",
        "from project_atlas.federation",
        "from project_atlas.federation_lens",
        "build_federation_read_lens",
        "chatgpt_bridge",
        "add_parser",
        "atlas.query.read",
    ):
        assert name not in source
