"""AS-CODER-ALPHA-DOGFOOD-COMPILER-COVERAGE-001 — imported-source recall."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from project_atlas.connect import connect_project
from project_atlas.dogfood_compiler_coverage import (
    PACKAGE_ID,
    UNKNOWN,
    CompilerCoverageError,
    attach_compiler_coverage,
    compile_dogfood_coverage,
)
from project_atlas.overview import build_overview_lens


def _write_manifest(vault: Path, sources: list[dict[str, object]]) -> None:
    path = vault / "generated" / "ops" / "connect-manifest.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"source_root": str(vault / "src"), "sources": sources}, indent=2),
        encoding="utf-8",
    )


def _write_imported(vault: Path, source_id: str, text: str, suffix: str = ".md") -> None:
    imported = vault / "sources" / "imported-documents"
    imported.mkdir(parents=True, exist_ok=True)
    (imported / f"{source_id}{suffix}").write_text(text, encoding="utf-8")


def _seed_project_note(vault: Path, project_id: str, sources: list[dict[str, object]]) -> None:
    note = vault / "projects" / project_id / "project.md"
    note.parent.mkdir(parents=True, exist_ok=True)
    semantic = {"project_id": project_id, "sources": sources, "coverage": []}
    note.write_text(
        "---\ntype: Project\ntitle: "
        + project_id
        + "\n---\n\n# "
        + project_id
        + "\n\n<!-- atlas:generated:start -->\n## Semantic record\n\n```json\n"
        + json.dumps(semantic)
        + "\n```\n",
        encoding="utf-8",
    )


def _dogfood_sources() -> list[dict[str, object]]:
    return [
        {
            "path": "README.md",
            "source_id": "source-readme",
            "likely_project": "harbor",
        },
        {
            "path": "pyproject.toml",
            "source_id": "source-pyproject",
            "likely_project": "harbor",
        },
        {
            "path": "AGENTS.md",
            "source_id": "source-agents",
            "likely_project": "harbor",
        },
        {
            "path": "docs/adr/ADR-001-local-first.md",
            "source_id": "source-adr",
            "likely_project": "harbor",
        },
        {
            "path": "docs/DECISIONS.md",
            "source_id": "source-decisions",
            "likely_project": "harbor",
        },
    ]


def _seed_dogfood_vault(vault: Path) -> None:
    _write_manifest(vault, _dogfood_sources())
    _seed_project_note(vault, "harbor", _dogfood_sources())
    _write_imported(
        vault,
        "source-readme",
        "# Harbor\n\nstatus: prototype\n",
    )
    _write_imported(
        vault,
        "source-pyproject",
        (
            "[build-system]\n"
            'requires = ["setuptools>=68"]\n\n'
            "[project]\n"
            'name = "harbor"\n'
            'description = "Local-first harbor brain."\n'
            'requires-python = ">=3.12"\n'
            "dependencies = [\n"
            '    "pydantic>=2.7",\n'
            '    "PyYAML>=6.0",\n'
            "]\n"
        ),
        suffix=".toml",
    )
    _write_imported(
        vault,
        "source-agents",
        (
            "# AGENTS.md — Harbor\n\n"
            "Guidance for agents.\n\n"
            "## Project overview\n\n"
            "Harbor is a local-first persistent brain for AI-native projects.\n"
        ),
    )
    _write_imported(
        vault,
        "source-adr",
        (
            "# ADR-001 — Local-first vault\n\n"
            "## Context\n\nOffline required.\n\n"
            "## Decision\n\nWe will keep the vault on disk.\n"
        ),
    )
    _write_imported(
        vault,
        "source-decisions",
        "# Decisions\n\n## Use OKF\nWe decided to use OKF.\n\n## Prefer local-first\nOffline.\n",
    )


def test_dogfood_fixture_recalls_stack_purpose_and_decisions(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    _seed_dogfood_vault(vault)
    coverage = compile_dogfood_coverage(vault, "harbor")
    assert coverage["package"] == PACKAGE_ID
    assert "Python" in coverage["tech_stack"]
    assert ">=3.12" in coverage["tech_stack"]
    assert "Harbor is a local-first" in coverage["purpose"]
    assert coverage["important_decisions"] != UNKNOWN
    assert "ADR-001" in coverage["important_decisions"]
    assert coverage["honesty"]["lens_is_authority"] is False
    assert coverage["honesty"]["fabricated_fields"] is False
    assert coverage["fabricated_field_count"] == 0
    assert coverage["cross_project_leak_count"] == 0


def test_readme_only_unsupported_stays_unknown(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    sources = [
        {
            "path": "README.md",
            "source_id": "source-readme",
            "likely_project": "harbor",
        }
    ]
    _write_manifest(vault, sources)
    _seed_project_note(vault, "harbor", sources)
    _write_imported(
        vault,
        "source-readme",
        "# Harbor\n\nThis Python app talks to Redis and decides everything.\n",
    )
    coverage = compile_dogfood_coverage(vault, "harbor")
    assert coverage["tech_stack"] == UNKNOWN
    assert coverage["important_decisions"] == UNKNOWN
    assert coverage["purpose"] == UNKNOWN
    assert coverage["honesty"]["fabricated_fields"] is False
    assert coverage["fabricated_field_count"] == 0


def test_sibling_and_excluded_sources_do_not_leak(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    _seed_dogfood_vault(vault)
    manifest = json.loads(
        (vault / "generated" / "ops" / "connect-manifest.json").read_text(encoding="utf-8")
    )
    manifest["sources"].extend(
        [
            {
                "path": "pyproject.toml",
                "source_id": "sibling-pyproject",
                "likely_project": "portal",
            },
            {
                "path": "docs/adr/ADR-999-sibling.md",
                "source_id": "sibling-adr",
                "likely_project": "portal",
            },
            {
                "path": "unowned.toml",
                "source_id": "unowned-pyproject",
            },
            {
                "path": "sentinel.toml",
                "source_id": "sentinel-pyproject",
                "likely_project": "unknown-project",
            },
            {
                "path": ".env",
                "source_id": "source-env",
                "likely_project": "harbor",
                "exclusion_reason": "sensitive-metadata-only",
            },
        ]
    )
    (vault / "generated" / "ops" / "connect-manifest.json").write_text(
        json.dumps(manifest, indent=2),
        encoding="utf-8",
    )
    _write_imported(
        vault,
        "sibling-pyproject",
        '[project]\nname = "portal"\nrequires-python = ">=3.11"\n',
        suffix=".toml",
    )
    _write_imported(
        vault,
        "sibling-adr",
        "# ADR-999 — Sibling only\n\nDo not leak this decision.\n",
    )
    _write_imported(
        vault,
        "unowned-pyproject",
        '[project]\nname = "unowned"\nrequires-python = "==3.10"\n',
        suffix=".toml",
    )
    _write_imported(
        vault,
        "sentinel-pyproject",
        '[project]\nname = "sentinel"\nrequires-python = "==3.9"\n',
        suffix=".toml",
    )
    _write_imported(vault, "source-env", "AKIAIOSFODNN7EXAMPLE\nSECRET_TOKEN=super-secret\n")

    coverage = compile_dogfood_coverage(vault, "harbor")
    payload = json.dumps(coverage)
    assert "Python >=3.12" in coverage["tech_stack"]
    assert "3.11" not in coverage["tech_stack"]
    assert "3.10" not in coverage["tech_stack"]
    assert "3.9" not in coverage["tech_stack"]
    assert "ADR-999" not in coverage["important_decisions"]
    assert "Sibling only" not in payload
    assert "AKIAIOSFODNN7EXAMPLE" not in payload
    assert "super-secret" not in payload
    assert coverage["cross_project_leak_count"] == 0


def test_secret_path_and_secret_body_are_not_echoed(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    sources = [
        {
            "path": "README.md",
            "source_id": "source-readme",
            "likely_project": "harbor",
        },
        {
            "path": "secrets.pem",
            "source_id": "source-pem",
            "likely_project": "harbor",
        },
        {
            "path": "docs/adr/ADR-001-keys.md",
            "source_id": "source-adr",
            "likely_project": "harbor",
        },
    ]
    _write_manifest(vault, sources)
    _seed_project_note(vault, "harbor", sources)
    _write_imported(vault, "source-readme", "# Harbor\n\nNo stack here.\n")
    _write_imported(
        vault,
        "source-pem",
        "-----BEGIN PRIVATE KEY-----\nMIISECRETKEYMATERIAL\n-----END PRIVATE KEY-----\n",
    )
    _write_imported(
        vault,
        "source-adr",
        "# ADR-001 — Adopt redaction\n\nAKIAIOSFODNN7EXAMPLE\n",
    )
    coverage = compile_dogfood_coverage(vault, "harbor")
    payload = json.dumps(coverage)
    assert "MIISECRETKEYMATERIAL" not in payload
    assert "AKIAIOSFODNN7EXAMPLE" not in payload
    assert coverage["important_decisions"] == UNKNOWN


def test_path_escape_source_id_is_ignored(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    outside = tmp_path / "outside.toml"
    outside.write_text('[project]\nrequires-python = ">=3.8"\n', encoding="utf-8")
    sources = [
        {
            "path": "../outside.toml",
            "source_id": "../outside",
            "likely_project": "harbor",
        },
        {
            "path": "C:/Windows/system32/config",
            "source_id": "abs-win",
            "likely_project": "harbor",
        },
    ]
    _write_manifest(vault, sources)
    _seed_project_note(vault, "harbor", sources)
    coverage = compile_dogfood_coverage(vault, "harbor")
    payload = json.dumps(coverage)
    assert coverage["tech_stack"] == UNKNOWN
    assert ">=3.8" not in payload
    with pytest.raises(CompilerCoverageError):
        compile_dogfood_coverage(vault, "../escape")


def test_overview_attaches_coverage_and_recalls_agents_purpose(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    sources = [
        {
            "path": "pyproject.toml",
            "source_id": "source-pyproject",
            "likely_project": "harbor",
        },
        {
            "path": "docs/adr/ADR-032-derived-intelligence-is-not-authority.md",
            "source_id": "source-adr",
            "likely_project": "harbor",
        },
    ]
    _write_manifest(vault, sources)
    _seed_project_note(vault, "harbor", sources)
    _write_imported(
        vault,
        "source-pyproject",
        (
            "[project]\n"
            'name = "harbor"\n'
            'description = "Persistent brain for the harbor estate."\n'
            'requires-python = ">=3.12"\n'
        ),
        suffix=".toml",
    )
    _write_imported(
        vault,
        "source-adr",
        "# ADR-032 — Derived intelligence is not authority\n\n## Context\nLens != authority.\n",
    )
    lens = build_overview_lens(vault, "harbor")
    assert lens["honesty"]["lens_is_authority"] is False
    assert lens["compiler_coverage"]["tech_stack"].startswith("Python")
    assert lens["compiler_coverage"]["important_decisions"] != UNKNOWN
    assert "Persistent brain" in (lens["summary"] or "")
    assert lens["status"] == "derived"
    assert lens["compiler_coverage"]["honesty"]["fabricated_fields"] is False


def test_attach_does_not_overwrite_existing_readme_summary(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    sources = [
        {
            "path": "README.md",
            "source_id": "source-readme",
            "likely_project": "harbor",
        },
        {
            "path": "AGENTS.md",
            "source_id": "source-agents",
            "likely_project": "harbor",
        },
    ]
    _write_manifest(vault, sources)
    _seed_project_note(vault, "harbor", sources)
    _write_imported(vault, "source-readme", "# Harbor Portal\n\nREADME purpose stays.\n")
    _write_imported(
        vault,
        "source-agents",
        "# AGENTS\n\n## Project overview\n\nAGENTS purpose must not replace README.\n",
    )
    lens = build_overview_lens(vault, "harbor")
    assert "Harbor Portal" in (lens["value"] or "")
    assert "AGENTS purpose must not replace README" not in (lens["value"] or "")
    assert "AGENTS purpose must not replace README" in lens["compiler_coverage"]["purpose"]


def test_attach_helper_sets_honesty_without_inventing(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    lens = attach_compiler_coverage(
        {
            "summary": None,
            "value": None,
            "status": "unknown",
            "inspected_artifacts": [],
            "notes": [],
        },
        vault,
        "harbor",
    )
    assert lens["compiler_coverage"]["tech_stack"] == UNKNOWN
    assert lens["compiler_coverage"]["important_decisions"] == UNKNOWN
    assert lens["honesty"]["lens_is_authority"] is False
    assert lens["status"] == "unknown"


def test_connect_dogfood_fixture_recalls_python_stack(tmp_path: Path) -> None:
    project = tmp_path / "harbor-brain"
    project.mkdir()
    (project / "README.md").write_text("# Harbor\n\nstatus: prototype\n", encoding="utf-8")
    (project / "pyproject.toml").write_text(
        '[project]\nname = "harbor-brain"\nrequires-python = ">=3.12"\n'
        'description = "Local-first harbor brain."\n',
        encoding="utf-8",
    )
    (project / "AGENTS.md").write_text(
        "# AGENTS\n\n## Project overview\n\nHarbor brain compiles imported evidence.\n",
        encoding="utf-8",
    )
    adr = project / "docs" / "adr"
    adr.mkdir(parents=True)
    (adr / "ADR-001-local-first.md").write_text(
        "# ADR-001 — Local-first vault\n\n## Context\nOffline.\n",
        encoding="utf-8",
    )
    report = connect_project(project)
    vault = Path(report["vault"])
    project_id = str(report["bound_project_id"])
    coverage = compile_dogfood_coverage(vault, project_id)
    assert "Python" in coverage["tech_stack"]
    assert coverage["important_decisions"] != UNKNOWN
    assert coverage["honesty"]["lens_is_authority"] is False
    assert coverage["honesty"]["fabricated_fields"] is False
    lens = json.loads(
        (vault / "generated" / "answers" / f"ans-overview-{project_id}.json").read_text(
            encoding="utf-8"
        )
    )
    assert lens["compiler_coverage"]["tech_stack"] != UNKNOWN
    assert "AKIA" not in json.dumps(lens)
