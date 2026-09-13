"""Contain yaml.safe_load constructor KeyError in project-marker readers.

D-057 promised a controlled ``INVALID_PROJECT_MARKER`` (discover / connect)
rather than a raw YAML traceback. Origination marker/contract loaders promised
the same fail-closed shape via their own structured errors.

PyYAML ``!!bool nope`` raises a bare ``KeyError``, not ``yaml.YAMLError``.
On live main ``b87b4a22`` those four readers leaked the constructor error.

This package does not widen acceptance: each site still refuses the input
through its existing structured path. Does not touch ``ingestion.py``.
Sibling of #819 / #820 / #822 (same constructor class, different public
surfaces).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from project_atlas.connect import ConnectError, _read_project_marker, connect_project
from project_atlas.discovery import _project_context, discover
from project_atlas.orchestration.origination.acceptance_contracts import (
    AcceptanceContractConfigError,
    load_acceptance_contracts,
)
from project_atlas.orchestration.origination.sources import (
    OriginationSourceConfigError,
    load_origination_sources,
)

MALFORMED = "atlas: !!bool nope\n"


def _project(tmp_path: Path) -> Path:
    root = tmp_path / "proj"
    root.mkdir()
    (root / "README.md").write_text("# fixture\n", encoding="utf-8")
    (root / ".atlas-project.yaml").write_text(MALFORMED, encoding="utf-8")
    return root


def test_discovery_project_context_constructor_tag_is_invalid_marker(tmp_path: Path) -> None:
    root = _project(tmp_path)
    with pytest.raises(ValueError, match="INVALID_PROJECT_MARKER"):
        _project_context(root / "README.md", root)


def test_discover_constructor_tag_is_invalid_marker(tmp_path: Path) -> None:
    root = _project(tmp_path)
    with pytest.raises(ValueError, match="INVALID_PROJECT_MARKER"):
        discover(root)


def test_connect_read_marker_constructor_tag_is_invalid_marker(tmp_path: Path) -> None:
    root = _project(tmp_path)
    with pytest.raises(ConnectError, match="INVALID_PROJECT_MARKER"):
        _read_project_marker(root)


def test_connect_project_constructor_tag_is_invalid_marker(tmp_path: Path) -> None:
    root = _project(tmp_path)
    with pytest.raises(ConnectError, match="INVALID_PROJECT_MARKER"):
        connect_project(root, vault=tmp_path / "vault")


def test_origination_sources_constructor_tag_fails_closed(tmp_path: Path) -> None:
    root = _project(tmp_path)
    with pytest.raises(OriginationSourceConfigError, match="unreadable project marker"):
        load_origination_sources(root)


def test_acceptance_contracts_marker_constructor_tag_fails_closed(tmp_path: Path) -> None:
    root = _project(tmp_path)
    with pytest.raises(AcceptanceContractConfigError, match="unreadable project marker"):
        load_acceptance_contracts(root)


def test_acceptance_contracts_file_constructor_tag_fails_closed(tmp_path: Path) -> None:
    root = tmp_path / "proj"
    root.mkdir()
    (root / ".atlas-project.yaml").write_text(
        "schema_version: 1\n"
        "project:\n  id: fixture-proj\n"
        "origination_acceptance_contracts: contracts.yaml\n",
        encoding="utf-8",
    )
    (root / "contracts.yaml").write_text(MALFORMED, encoding="utf-8")
    with pytest.raises(
        AcceptanceContractConfigError, match="unreadable acceptance-contracts file"
    ):
        load_acceptance_contracts(root)
