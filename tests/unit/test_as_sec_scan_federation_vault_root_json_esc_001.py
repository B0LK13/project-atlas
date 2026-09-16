"""AS-SEC-SCAN-FEDERATION-VAULT-ROOT-JSON-ESC-001 — decoded roots must not persist.

``build_join_inventory`` wrote refused join inventories including
``vault_root`` after ``json.loads`` decoded ``\\u0041KI…`` into
``AKIAAAAAAAAAAAAAAAAA``. ``scan_text`` on raw JSON is empty; the
written file then matches ``cloud-access-key`` (NFR-004 / AT-014).

Synthetic token only. Distinct from #989 (Atlas 3 memory persist) and
listed P2 residuals.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from project_atlas.federation import FederationError, FederationMember, build_join_inventory
from project_atlas.secrets import scan_text

TOKEN = "AKIAAAAAAAAAAAAAAAAA"
ESC = r"\u0041KIAAAAAAAAAAAAAAAAA"


def test_json_escaped_vault_root_does_not_persist(tmp_path: Path) -> None:
    raw = f'{{"vault_root":"{ESC}","project_id":"harbor"}}'
    assert TOKEN not in raw
    assert scan_text(raw) == []
    row = json.loads(raw)
    assert row["vault_root"] == TOKEN
    vault = tmp_path / "out"
    vault.mkdir()
    with pytest.raises(FederationError, match="federation-vault-root-secret-findings"):
        build_join_inventory(
            federation_id="fed-esc",
            members=[
                FederationMember(
                    member_id="primary",
                    vault_root=str(row["vault_root"]),
                    role="primary",
                    project_id="harbor",
                )
            ],
            output_vault=vault,
        )
    generated = vault / "generated"
    assert not generated.exists()


def test_json_escaped_project_id_does_not_persist(tmp_path: Path) -> None:
    raw = f'{{"project_id":"{ESC}"}}'
    assert TOKEN not in raw
    assert scan_text(raw) == []
    row = json.loads(raw)
    vault = tmp_path / "out"
    vault.mkdir()
    primary = tmp_path / "primary-vault"
    primary.mkdir()
    with pytest.raises(FederationError, match="federation-project-id-secret-findings"):
        build_join_inventory(
            federation_id="fed-pid",
            members=[
                FederationMember(
                    member_id="primary",
                    vault_root=str(primary),
                    role="primary",
                    project_id=str(row["project_id"]),
                )
            ],
            output_vault=vault,
        )
    assert not (vault / "generated").exists()


def test_safe_join_still_persists(tmp_path: Path) -> None:
    vault = tmp_path / "out"
    vault.mkdir()
    primary = tmp_path / "primary-vault"
    primary.mkdir()
    report = build_join_inventory(
        federation_id="fed-ok",
        members=[
            FederationMember(
                member_id="primary",
                vault_root=str(primary),
                role="primary",
                project_id="harbor",
            )
        ],
        output_vault=vault,
    )
    assert report["status"] == "joined"
    written = (
        vault / "generated" / "federation" / "fed-ok-join-inventory.json"
    ).read_text(encoding="utf-8")
    assert TOKEN not in written
    assert scan_text(written) == []
