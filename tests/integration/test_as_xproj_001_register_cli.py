"""AS-XPROJ-001 — CLI register-global-entity smoke (integration)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from project_atlas.cli import main


def test_register_global_entity_cli_write(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    regs = tmp_path / "regs.json"
    vault = tmp_path / "vault"
    vault.mkdir()
    regs.write_text(
        json.dumps(
            {
                "registrations": [
                    {
                        "kind": "entity",
                        "global_entity_id": "ge-tech-kafka",
                        "entity_class": "technology",
                        "display_name": "Kafka",
                    },
                    {
                        "kind": "join",
                        "project_id": "demo",
                        "project_local_entity_id": "demo:unknown:kafka",
                        "global_entity_id": "ge-tech-kafka",
                        "evidence_refs": [
                            {"relative_path": "sources/a.md", "sha256": "b" * 64}
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
    out = capsys.readouterr().out
    assert "authority: derived" in out
    assert "registered: 1" in out
    entities = list((vault / "state" / "global-entities").glob("ge-tech-kafka--*.json"))
    assert len(entities) == 1
    assert list((vault / "state" / "global-entities" / "joins").glob("*.json"))


def test_register_global_entity_cli_requires_vault_for_write(tmp_path: Path) -> None:
    regs = tmp_path / "regs.json"
    regs.write_text(
        json.dumps({"registrations": []}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    code = main(
        [
            "register-global-entity",
            "--registrations",
            str(regs),
            "--write",
        ]
    )
    assert code == 1
