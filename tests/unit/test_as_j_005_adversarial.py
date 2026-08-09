"""AS-J-005 adversarial surface — Graph≠authority firewall."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from project_atlas.impact_graph import (
    ImpactGraphError,
    promote_impact_path_forbidden,
)

_MODULE = Path(__file__).resolve().parents[2] / "src" / "project_atlas" / "impact_graph.py"


def test_j5_adv_module_does_not_import_authority_or_web() -> None:
    tree = ast.parse(_MODULE.read_text(encoding="utf-8"))
    forbidden_modules = {
        "project_atlas.authority_evaluator",
        "project_atlas.authority_registry",
        "project_atlas.knowledge_compiler",
        "project_atlas.web_api",
    }
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module in forbidden_modules:
            pytest.fail(f"forbidden import: {node.module}")
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name in forbidden_modules:
                    pytest.fail(f"forbidden import: {alias.name}")


def test_j5_adv_source_text_excludes_forbidden_surfaces() -> None:
    text = _MODULE.read_text(encoding="utf-8")
    assert "recover_promote_orphans" not in text
    assert "apps/web" in text  # listed as forbidden write prefix
    assert "trust_score" in text  # listed in forbidden payload keys
    assert "authority_winner" in text


def test_j5_adv_cp_relationships_prefix_blocked() -> None:
    with pytest.raises(ImpactGraphError):
        promote_impact_path_forbidden("relationships/foo.json")


def test_j5_adv_no_cli_dual_own_indexes_module() -> None:
    """J-005 owns impact_graph.py only — does not mutate indexes.py."""
    indexes = _MODULE.parent / "indexes.py"
    text = indexes.read_text(encoding="utf-8")
    assert "AS-J-005" not in text
    assert "impact-graph" not in text
    assert "impact_graph" not in text
