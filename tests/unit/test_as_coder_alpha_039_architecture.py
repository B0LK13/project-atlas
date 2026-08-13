"""AS-CODER-ALPHA-ARCH-001 (D-039) — architecture summary != purpose echo."""

from __future__ import annotations

import json
from pathlib import Path

from project_atlas.connect import connect_project
from project_atlas.project_brief import build_project_brief


def test_architecture_prefers_plan_over_readme_purpose(tmp_path: Path) -> None:
    root = tmp_path / "project-atlas"
    (root / "docs").mkdir(parents=True)
    (root / "README.md").write_text(
        "# Project Atlas\n\nPersistent brain for AI-native projects.\n",
        encoding="utf-8",
    )
    (root / "AGENTS.md").write_text(
        "# Agents\n\n"
        "- **Three-layer vault model** — Layer A evidence, Layer B OKF, Layer C synthesis.\n"
        "- Core pipeline: discover → ingest → build-indexes → validate.\n",
        encoding="utf-8",
    )
    (root / "docs" / "plan.md").write_text(
        "# Plan\n\n## 2. Core architectural decision\n\n"
        "I recommend a **three-layer vault**.\n\n"
        "### Layer A — Source evidence\n\nOriginal documentation.\n",
        encoding="utf-8",
    )
    vault = Path(connect_project(root)["vault"])
    brief = build_project_brief(vault, "project-atlas", refresh=True)
    assert brief["purpose"].startswith("Project Atlas")
    assert brief["architecture_summary"] != brief["purpose"]
    assert "three-layer" in brief["architecture_summary"].lower()
    assert brief["architecture_summary"] != "UNKNOWN"


def test_architecture_unknown_without_plan_or_agents(tmp_path: Path) -> None:
    root = tmp_path / "readme-only"
    root.mkdir()
    (root / "README.md").write_text(
        "# Readme Only\n\nPurpose prose must not become architecture.\n",
        encoding="utf-8",
    )
    vault = Path(connect_project(root)["vault"])
    brief = json.loads(
        (vault / "generated" / "ops" / "project-brief-readme-only.json").read_text(
            encoding="utf-8"
        )
    )
    assert brief["purpose"] != "UNKNOWN"
    assert brief["architecture_summary"] == "UNKNOWN"


def test_architecture_evidence_path_and_subsection_capture(tmp_path: Path) -> None:
    root = tmp_path / "arch-ev"
    (root / "docs").mkdir(parents=True)
    (root / "README.md").write_text("# Arch Ev\n\nPurpose only.\n", encoding="utf-8")
    (root / "docs" / "plan.md").write_text(
        "# Plan\n\n## Architecture\n\n### Components\n\n"
        "Core CLI and Truth Core compile pipeline.\n\n"
        "## Operations\n\nRun the OKF validator nightly.\n",
        encoding="utf-8",
    )
    vault = Path(connect_project(root)["vault"])
    brief = build_project_brief(vault, "arch-ev", refresh=True)
    assert brief["architecture_summary"] != "UNKNOWN"
    assert "Components" in brief["architecture_summary"]
    assert "Core CLI" in brief["architecture_summary"]
    assert "docs/plan.md" in (brief.get("evidence_links") or [])
    assert "OKF validator" not in brief["architecture_summary"]


def test_bare_okf_ops_line_is_not_architecture(tmp_path: Path) -> None:
    root = tmp_path / "okf-noise"
    root.mkdir()
    (root / "README.md").write_text("# OKF Noise\n\nPurpose.\n", encoding="utf-8")
    (root / "AGENTS.md").write_text(
        "# Agents\n\n- Run the OKF validator before merge.\n",
        encoding="utf-8",
    )
    vault = Path(connect_project(root)["vault"])
    brief = build_project_brief(vault, "okf-noise", refresh=True)
    assert brief["architecture_summary"] == "UNKNOWN"
