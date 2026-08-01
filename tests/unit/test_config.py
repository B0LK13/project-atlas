"""Unit tests for configuration loading."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from project_atlas.config import AtlasConfig, load_config


def test_defaults_without_any_file(tmp_path: Path) -> None:
    config = load_config(search_from=tmp_path)
    assert config.logging.level == "INFO"
    assert config.logging.format == "console"
    assert "**/*.md" in config.discovery.include_globs


def test_explicit_toml_file(tmp_path: Path) -> None:
    config_file = tmp_path / "atlas.toml"
    config_file.write_text('[logging]\nlevel = "DEBUG"\nformat = "json"\n', encoding="utf-8")
    config = load_config(config_file)
    assert config.logging.level == "DEBUG"
    assert config.logging.format == "json"


def test_pyproject_tool_section(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        '[tool.atlas.logging]\nlevel = "WARNING"\n', encoding="utf-8"
    )
    config = load_config(search_from=tmp_path)
    assert config.logging.level == "WARNING"


def test_atlas_toml_wins_over_pyproject(tmp_path: Path) -> None:
    (tmp_path / "atlas.toml").write_text('[logging]\nlevel = "ERROR"\n', encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text(
        '[tool.atlas.logging]\nlevel = "WARNING"\n', encoding="utf-8"
    )
    config = load_config(search_from=tmp_path)
    assert config.logging.level == "ERROR"


def test_missing_explicit_file_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_config(tmp_path / "missing.toml")


def test_unknown_keys_rejected() -> None:
    with pytest.raises(ValidationError):
        AtlasConfig.model_validate({"surprise": True})


def test_invalid_toml_raises(tmp_path: Path) -> None:
    bad = tmp_path / "atlas.toml"
    bad.write_text("this is [ not toml", encoding="utf-8")
    with pytest.raises(ValueError):
        load_config(bad)
