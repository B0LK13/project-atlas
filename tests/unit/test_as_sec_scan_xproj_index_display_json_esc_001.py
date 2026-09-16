"""AS-SEC-SCAN-XPROJ-INDEX-DISPLAY-JSON-ESC-001 — decoded display names must not persist."""

from __future__ import annotations

from pathlib import Path

from project_atlas.secrets import scan_text
from project_atlas.xproj_indexes import build_xproj_indexes, write_xproj_index_outputs

TOKEN = "AKIAAAAAAAAAAAAAAAAA"
ESC = r"\u0041KIAAAAAAAAAAAAAAAAA"
SHA = "a" * 64


def _entity_json(*, gid: str, display: str) -> str:
    return (
        "{\n"
        '  "schema_version": 1,\n'
        '  "package_id": "AS-XPROJ-001",\n'
        f'  "global_entity_id": "{gid}",\n'
        '  "entity_class": "service",\n'
        f'  "display_name": "{display}",\n'
        '  "authority": {"level": "derived"},\n'
        '  "registration_kind": "explicit",\n'
        '  "status": "registered"\n'
        "}\n"
    )


def _join_json(*, project_id: str, local: str, gid: str) -> str:
    return (
        "{\n"
        '  "schema_version": 1,\n'
        '  "package_id": "AS-XPROJ-001",\n'
        f'  "project_id": "{project_id}",\n'
        f'  "project_local_entity_id": "{local}",\n'
        f'  "global_entity_id": "{gid}",\n'
        '  "evidence_refs": [{"relative_path": "docs/a.md", "sha256": "'
        + SHA
        + '"}],\n'
        '  "authority": {"level": "derived"},\n'
        '  "status": "joined"\n'
        "}\n"
    )


def test_json_unicode_escape_display_name_is_not_persisted(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    entity = vault / "state" / "global-entities" / "svc-harbor.json"
    join = vault / "state" / "global-entities" / "joins" / "harbor-join.json"
    entity.parent.mkdir(parents=True)
    join.parent.mkdir(parents=True)
    raw_entity = _entity_json(gid="svc-harbor", display=ESC)
    raw_join = _join_json(project_id="harbor-api", local="svc-local", gid="svc-harbor")
    entity.write_text(raw_entity, encoding="utf-8")
    join.write_text(raw_join, encoding="utf-8")
    assert scan_text(raw_entity) == []
    result = build_xproj_indexes(vault=vault)
    write_xproj_index_outputs(result, vault=vault)
    written = (vault / "generated" / "xproj" / "indexes" / "services" / "index.json").read_text(
        encoding="utf-8"
    )
    assert TOKEN not in written
    assert scan_text(written) == []
