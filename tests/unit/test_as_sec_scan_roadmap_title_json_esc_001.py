"""AS-SEC-SCAN-ROADMAP-TITLE-JSON-ESC-001 — decoded roadmap titles must not persist."""

from __future__ import annotations

from pathlib import Path

from project_atlas.project_roadmap import materialize_roadmap_lenses
from project_atlas.secrets import scan_text

TOKEN = "AKIAAAAAAAAAAAAAAAAA"
ESC = r"\u0041KIAAAAAAAAAAAAAAAAA"


def test_json_unicode_escape_roadmap_title_is_not_persisted(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    proj = vault / "projects" / "harbor-api"
    proj.mkdir(parents=True)
    raw = (
        "# Roadmap\n\n## Roadmap record\n```json\n"
        "{\n"
        '  "items": [{\n'
        '    "id": "wp-1",\n'
        f'    "title": "{ESC}",\n'
        '    "status": "IN_PROGRESS"\n'
        "  }]\n"
        "}\n"
        "```\n"
    )
    (proj / "roadmap.md").write_text(raw, encoding="utf-8")
    assert scan_text(raw) == []
    materialize_roadmap_lenses(vault, project_ids=["harbor-api"])
    written = (vault / "generated" / "answers" / "ans-roadmap-harbor-api.json").read_text(
        encoding="utf-8"
    )
    assert TOKEN not in written
    assert scan_text(written) == []


def test_json_unicode_escape_roadmap_item_id_is_not_persisted(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    proj = vault / "projects" / "harbor-api"
    proj.mkdir(parents=True)
    raw = (
        "# Roadmap\n\n## Roadmap record\n```json\n"
        "{\n"
        '  "items": [{\n'
        f'    "id": "{ESC}",\n'
        '    "title": "safe title",\n'
        '    "status": "IN_PROGRESS"\n'
        "  }]\n"
        "}\n"
        "```\n"
    )
    (proj / "roadmap.md").write_text(raw, encoding="utf-8")
    assert scan_text(raw) == []
    materialize_roadmap_lenses(vault, project_ids=["harbor-api"])
    written = (vault / "generated" / "answers" / "ans-roadmap-harbor-api.json").read_text(
        encoding="utf-8"
    )
    assert TOKEN not in written
    assert scan_text(written) == []
