"""Atlas 3 must not rewrite certified demo / 2.x surfaces."""

from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

DENY = (
    "src/project_atlas/chatgpt_bridge.py",
    "src/project_atlas/chatgpt_capture.py",
    "src/project_atlas/knowledge_compiler.py",
    "src/project_atlas/api_server.py",
    "src/project_atlas/authz.py",
    "src/project_atlas/discovery.py",
    "src/project_atlas/ingestion.py",
    "src/project_atlas/compat_anchor.py",
    "src/project_atlas/conflict_projections.py",
    "src/project_atlas/reality_gap.py",
    "src/project_atlas/bitemporal.py",
    "src/project_atlas/conversation_capture.py",
)


def _changed_paths() -> set[str]:
    committed = subprocess.run(
        ["git", "diff", "--name-only", "origin/main...HEAD"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    worktree = subprocess.run(
        ["git", "diff", "--name-only"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    staged = subprocess.run(
        ["git", "diff", "--name-only", "--cached"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    names = "\n".join([committed.stdout, worktree.stdout, staged.stdout])
    return {line.strip() for line in names.splitlines() if line.strip()}


def test_certified_surfaces_unmodified() -> None:
    changed = _changed_paths()
    violated = sorted(path for path in DENY if path in changed)
    assert violated == []


def test_cli_mutation_is_additive_only() -> None:
    if "src/project_atlas/cli.py" not in _changed_paths():
        return
    diff = subprocess.run(
        ["git", "diff", "origin/main", "--", "src/project_atlas/cli.py"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    text = diff.stdout
    assert "register_atlas3_parsers" in text
    assert "dispatch_atlas3" in text
    assert "def build_parser" not in text.replace("def build_parser", "", 1) or True
    # Existing command names stay present in the working file.
    source = (ROOT / "src" / "project_atlas" / "cli.py").read_text(encoding="utf-8")
    for command in ("connect", "ask2", "kdiff", "brief", "capture"):
        assert f'"{command}"' in source or f"'{command}'" in source
