"""Contain yaml.safe_load constructor KeyError at remaining public loaders.

AS-OBSIDIAN-CAPTURE-001-F7-R1 closed the same leak in the Obsidian ownership
probe. These three sites still used ``except yaml.YAMLError`` only, so
``atlas: !!bool nope`` escaped as a bare ``KeyError``.

This package does not widen acceptance: each site still refuses the input
through its existing structured path.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from project_atlas.estate_discovery import _parse_marker_file
from project_atlas.graph_acceptance import GraphAcceptanceError, _parse_artifact
from project_atlas.yaml_structured import MalformedYamlError, load_safe_yaml

MALFORMED = "atlas: !!bool nope\n"


def test_load_safe_yaml_does_not_raise_keyerror() -> None:
    with pytest.raises(MalformedYamlError):
        load_safe_yaml(MALFORMED)


def test_estate_marker_parse_treats_constructor_tag_as_invalid(tmp_path: Path) -> None:
    marker = tmp_path / ".atlas-project.yaml"
    marker.write_text(MALFORMED, encoding="utf-8")
    parsed = _parse_marker_file(marker, ".atlas-project.yaml")
    assert parsed["marker_status"] == "invalid"
    assert parsed["atlas_project_id"] is None


def test_graph_acceptance_metadata_constructor_tag_is_malformed(tmp_path: Path) -> None:
    path = tmp_path / "metadata.yaml"
    path.write_text(MALFORMED, encoding="utf-8")
    with pytest.raises(GraphAcceptanceError, match="malformed-metadata"):
        _parse_artifact(path, "metadata")
