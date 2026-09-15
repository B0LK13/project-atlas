"""AS-DOGFOOD-SEMANTIC-OWNER-001 — semantic sources are not an owner bypass."""

from __future__ import annotations

import json
from pathlib import Path

from project_atlas.dogfood_compiler_coverage import compile_dogfood_coverage


def _write_manifest(vault: Path, sources: list[dict[str, object]]) -> None:
    path = vault / "generated" / "ops" / "connect-manifest.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"source_root": str(vault / "src"), "sources": sources}, indent=2),
        encoding="utf-8",
    )


def _write_imported(vault: Path, source_id: str, text: str, suffix: str) -> None:
    imported = vault / "sources" / "imported-documents"
    imported.mkdir(parents=True, exist_ok=True)
    (imported / f"{source_id}{suffix}").write_text(text, encoding="utf-8")


def test_semantic_record_sibling_sources_do_not_enter_scope(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    _write_manifest(
        vault,
        [{"path": "README.md", "source_id": "harbor-readme", "likely_project": "harbor"}],
    )
    _write_imported(vault, "harbor-readme", "# Harbor\n", ".md")
    _write_imported(
        vault,
        "sibling-pyproject",
        '[project]\nrequires-python="==3.11"\ndescription="SIBLING PORTAL BRAIN"\n',
        ".toml",
    )
    _write_imported(
        vault,
        "sibling-adr",
        "# ADR-999 — Sibling secret decision\n",
        ".md",
    )
    semantic = {
        "project_id": "harbor",
        "sources": [
            {"path": "README.md", "source_id": "harbor-readme"},
            {
                "path": "pyproject.toml",
                "source_id": "sibling-pyproject",
                "likely_project": "portal",
            },
            {
                "path": "docs/adr/ADR-999.md",
                "source_id": "sibling-adr",
                "likely_project": "portal",
            },
        ],
        "coverage": [],
    }
    note = vault / "projects" / "harbor" / "project.md"
    note.parent.mkdir(parents=True)
    note.write_text(
        "---\ntype: Project\ntitle: harbor\n---\n\n# harbor\n\n"
        "<!-- atlas:generated:start -->\n## Semantic record\n\n```json\n"
        + json.dumps(semantic)
        + "\n```\n",
        encoding="utf-8",
    )
    coverage = compile_dogfood_coverage(vault, "harbor")
    payload = json.dumps(coverage)
    assert "3.11" not in str(coverage["tech_stack"])
    assert "SIBLING PORTAL" not in payload
    assert "ADR-999" not in payload
    assert coverage["cross_project_leak_count"] == 0


def test_semantic_project_id_spoof_does_not_enter_scope(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    _write_manifest(
        vault,
        [{"path": "README.md", "source_id": "harbor-readme", "likely_project": "harbor"}],
    )
    _write_imported(vault, "harbor-readme", "# Harbor\n", ".md")
    _write_imported(
        vault,
        "sibling-pyproject",
        '[project]\nrequires-python="==3.11"\ndescription="SIBLING PORTAL BRAIN"\n',
        ".toml",
    )
    _write_imported(
        vault,
        "sibling-adr",
        "# ADR-999 — Sibling secret decision\n",
        ".md",
    )
    semantic = {
        "project_id": "harbor",
        "sources": [
            {"path": "README.md", "source_id": "harbor-readme"},
            {
                "path": "pyproject.toml",
                "source_id": "sibling-pyproject",
                "project_id": "harbor",
            },
            {
                "path": "docs/adr/ADR-999.md",
                "source_id": "sibling-adr",
                "project_id": "harbor",
            },
        ],
        "coverage": [],
    }
    note = vault / "projects" / "harbor" / "project.md"
    note.parent.mkdir(parents=True)
    note.write_text(
        "---\ntype: Project\ntitle: harbor\n---\n\n# harbor\n\n"
        "<!-- atlas:generated:start -->\n## Semantic record\n\n```json\n"
        + json.dumps(semantic)
        + "\n```\n",
        encoding="utf-8",
    )
    coverage = compile_dogfood_coverage(vault, "harbor")
    payload = json.dumps(coverage)
    assert "3.11" not in str(coverage["tech_stack"])
    assert "SIBLING PORTAL" not in payload
    assert "ADR-999" not in payload
    assert coverage["cross_project_leak_count"] == 0
