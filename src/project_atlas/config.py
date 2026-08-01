"""Configuration loading for Project Atlas (roadmap Phase 0).

Configuration is read from TOML using the stdlib ``tomllib`` (offline,
no dependency). Sources, in increasing precedence:

1. built-in defaults (this module);
2. ``[tool.atlas]`` in ``pyproject.toml``;
3. an explicit ``atlas.toml`` (or other TOML file) passed by the user.

All fields have safe defaults so the CLI works with no configuration file
at all.
"""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from project_atlas.logging import get_logger

_log = get_logger("config")


class DiscoveryConfig(BaseModel):
    """Discovery-related settings (used from WP-002 onward)."""

    model_config = ConfigDict(extra="forbid")

    include_globs: list[str] = Field(
        default_factory=lambda: [
            "**/*.md", "**/*.txt", "**/*.yaml", "**/*.yml",
            "**/*.json", "**/*.toml", "**/*.html",
        ]
    )
    exclude_globs: list[str] = Field(
        default_factory=lambda: [".git/**", ".venv/**", "node_modules/**", "__pycache__/**"]
    )
    max_file_size_bytes: int = Field(default=10 * 1024 * 1024, ge=1)


class LoggingConfig(BaseModel):
    """Logging settings for :mod:`project_atlas.logging`."""

    model_config = ConfigDict(extra="forbid")

    level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    format: Literal["console", "json"] = "console"


class AtlasConfig(BaseModel):
    """Top-level Project Atlas configuration."""

    model_config = ConfigDict(extra="forbid")

    discovery: DiscoveryConfig = Field(default_factory=DiscoveryConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)


def _read_toml(path: Path) -> dict[str, Any]:
    with path.open("rb") as handle:
        data = tomllib.load(handle)
    if not isinstance(data, dict):  # tomllib always returns dict; guard for typing
        raise ValueError(f"configuration root must be a table: {path}")
    return data


def load_config(path: Path | None = None, *, search_from: Path | None = None) -> AtlasConfig:
    """Load configuration, falling back to defaults.

    - If ``path`` is given, it must exist and contain a valid config table
      (either the whole document or its ``[tool.atlas]`` section).
    - Otherwise ``atlas.toml`` then ``pyproject.toml`` are probed in
      ``search_from`` (default: current working directory).
    - If nothing is found, defaults are returned.
    """
    if path is not None:
        if not path.is_file():
            raise FileNotFoundError(f"configuration file not found: {path}")
        data = _read_toml(path)
        section = data.get("tool", {}).get("atlas", data)
        config = AtlasConfig.model_validate(section)
        _log.info("loaded configuration", extra={"context": {"path": str(path)}})
        return config

    root = search_from or Path.cwd()
    for candidate in (root / "atlas.toml", root / "pyproject.toml"):
        if not candidate.is_file():
            continue
        data = _read_toml(candidate)
        if candidate.name == "atlas.toml":
            # An atlas.toml may use [tool.atlas] or a bare top-level table.
            section = data.get("tool", {}).get("atlas", data)
        else:
            # pyproject.toml is only consulted for its [tool.atlas] section.
            section = data.get("tool", {}).get("atlas")
        if section is None:
            continue
        config = AtlasConfig.model_validate(section)
        _log.info("loaded configuration", extra={"context": {"path": str(candidate)}})
        return config

    _log.debug("no configuration file found; using defaults")
    return AtlasConfig()
