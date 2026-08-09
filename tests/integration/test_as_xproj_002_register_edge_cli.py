"""AS-XPROJ-002 — CLI register-global-edge smoke (integration)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from project_atlas.cli import main


def _seed_vault(vault: Path) -> None:
    regs = vault / "regs.json"
    regs.write_text(
        json.dumps(
            {
                "registrations": [
                    {
                        "kind": "entity",
                        "global_entity_id": "ge-svc-billing",
                        "entity_class": "service",
                        "display_name": "Billing",
                    },
                    {
                        "kind": "entity",
                        "global_entity_id": "ge-tech-postgres-v1",
                        "entity_class": "technology",
                        "display_name": "Postgres",
                    },
                    {
                        "kind": "join",
                        "project_id": "proj-a",
                        "project_local_entity_id": "proj-a:svc:billing",
                        "global_entity_id": "ge-svc-billing",
                        "evidence_refs": [
                            {"relative_path": "sources/a.md", "sha256": "a" * 64}
                        ],
                    },
                    {
                        "kind": "join",
                        "project_id": "proj-b",
                        "project_local_entity_id": "proj-b:tech:postgres",
                        "global_entity_id": "ge-tech-postgres-v1",
                        "evidence_refs": [
                            {"relative_path": "sources/b.md", "sha256": "b" * 64}
                        ],
                    },
                ]
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    code = main(
        [
            "register-global-entity",
            "--registrations",
            str(regs),
            "--vault",
            str(vault),
            "--write",
        ]
    )
    assert code == 0


def test_register_global_edge_cli_write(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    _seed_vault(vault)
    edges = tmp_path / "edges.json"
    edges.write_text(
        json.dumps(
            {
                "edges": [
                    {
                        "kind": "edge",
                        "edge_id": "xe-dep-billing-postgres-v1",
                        "relationship_type": "depends-on",
                        "source_global_entity_id": "ge-svc-billing",
                        "target_global_entity_id": "ge-tech-postgres-v1",
                        "evidence_refs": [
                            {"relative_path": "sources/a.md", "sha256": "a" * 64}
                        ],
                    }
                ]
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    code = main(
        [
            "register-global-edge",
            "--edges",
            str(edges),
            "--vault",
            str(vault),
            "--write",
        ]
    )
    assert code == 0
    out = capsys.readouterr().out
    assert "authority: derived" in out
    assert "registered: 1" in out
    assert list((vault / "state" / "global-entities" / "edges").glob("*.json"))


def test_register_global_edge_cli_requires_vault(tmp_path: Path) -> None:
    edges = tmp_path / "edges.json"
    edges.write_text(
        json.dumps({"edges": []}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    code = main(["register-global-edge", "--edges", str(edges)])
    assert code == 1
