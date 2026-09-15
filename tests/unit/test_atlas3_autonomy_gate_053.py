"""AT3-053 — isolated autonomy gate reuse."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from project_atlas.atlas3.autonomy_gate import PACKAGE_ID, compile_autonomy_gate_reuse
from project_atlas.atlas3.contracts import Atlas3Error


def _vault(tmp_path: Path) -> Path:
    vault = tmp_path / "vault"
    (vault / "projects" / "harbor-api").mkdir(parents=True)
    return vault


def _write_declared(vault: Path, payload: dict[str, object]) -> None:
    path = vault / "generated" / "ops" / "atlas3" / "autonomy-gate" / "harbor-api" / "declared.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")


def test_missing_stays_unknown(tmp_path: Path) -> None:
    report = compile_autonomy_gate_reuse(_vault(tmp_path), "harbor-api")
    assert report["package_id"] == PACKAGE_ID
    assert report["status"] == "UNKNOWN"
    assert report["execution_authorized"] is False
    assert report["self_dispatch"] is False
    assert report["lease_is_merge_authority"] is False
    assert report["new_cli_command"] is False
    assert report["merge_authorization"] == "NOT_GRANTED"
    assert report["write_applied"] is False


def test_composes_declared_gates(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    _write_declared(
        vault,
        {
            "project_id": "harbor-api",
            "leases": [{"lease_id": "lease-1"}],
            "dag": [{"node_id": "AT3-053", "state": "READY"}],
            "owner_gates": ["MERGE", "RELEASE"],
        },
    )
    report = compile_autonomy_gate_reuse(vault, "harbor-api")
    assert report["status"] == "derived"
    assert report["counts"]["leases"] == 1
    assert report["counts"]["nodes"] == 1
    assert report["owner_gates"] == ["MERGE", "RELEASE"]
    assert report["nodes"][0]["execution_authorized"] is False


def test_execution_authorized_fails_closed(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    _write_declared(
        vault,
        {"project_id": "harbor-api", "execution_authorized": True, "leases": []},
    )
    with pytest.raises(Atlas3Error) as exc:
        compile_autonomy_gate_reuse(vault, "harbor-api")
    assert exc.value.code == "EXECUTION_AUTHORIZED"


def test_self_dispatch_fails_closed(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    _write_declared(vault, {"project_id": "harbor-api", "self_dispatch": True, "leases": []})
    with pytest.raises(Atlas3Error) as exc:
        compile_autonomy_gate_reuse(vault, "harbor-api")
    assert exc.value.code == "SELF_DISPATCH"


def test_merge_grant_fails_closed(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    _write_declared(
        vault,
        {"project_id": "harbor-api", "merge_authorization": "GRANTED", "leases": []},
    )
    with pytest.raises(Atlas3Error) as exc:
        compile_autonomy_gate_reuse(vault, "harbor-api")
    assert exc.value.code == "MERGE_CLAIM_FORBIDDEN"


def test_owner_authority_fails_closed(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    _write_declared(
        vault,
        {"project_id": "harbor-api", "owner_authority": True, "owner_gates": ["MERGE"]},
    )
    with pytest.raises(Atlas3Error) as exc:
        compile_autonomy_gate_reuse(vault, "harbor-api")
    assert exc.value.code == "OWNER_AUTHORITY_INVENTED"


def test_cross_project_fails_closed(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    _write_declared(vault, {"project_id": "foreign-api", "leases": []})
    with pytest.raises(Atlas3Error) as exc:
        compile_autonomy_gate_reuse(vault, "harbor-api")
    assert exc.value.code == "CROSS_PROJECT"


def test_corrupt_fails_closed(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    path = vault / "generated" / "ops" / "atlas3" / "autonomy-gate" / "harbor-api" / "declared.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{not-json\n", encoding="utf-8")
    with pytest.raises(Atlas3Error) as exc:
        compile_autonomy_gate_reuse(vault, "harbor-api")
    assert exc.value.code == "AUTONOMY_GATE_CORRUPT"


def test_unknown_project_fails_closed(tmp_path: Path) -> None:
    vault = tmp_path / "empty"
    vault.mkdir()
    with pytest.raises(Atlas3Error) as exc:
        compile_autonomy_gate_reuse(vault, "harbor-api")
    assert exc.value.code == "UNKNOWN_PROJECT"


def test_module_does_not_write() -> None:
    root = Path(__file__).resolve().parents[2]
    source = (root / "src/project_atlas/atlas3/autonomy_gate.py").read_text(encoding="utf-8")
    for name in (
        "write_json_atomic",
        "write_text(",
        "chatgpt_bridge",
        "add_parser",
        "atlas.query.read",
        "from project_atlas.ingestion",
    ):
        assert name not in source
