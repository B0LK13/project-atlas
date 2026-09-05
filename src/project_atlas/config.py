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


class GraphifyConfig(BaseModel):
    """Graphify acceptance settings (AS-GRAPH-001).

    ``semantic_ingestion`` defaults to False. Enabling it before AS-GRAPH-003
    fails closed with ``semantic_ingestion_unsupported``.
    """

    model_config = ConfigDict(extra="forbid")

    enabled: bool = True
    semantic_ingestion: bool = False


class ObsidianRoutingConfig(BaseModel):
    """Logical Obsidian destinations (AS-OBSIDIAN-CAPTURE-001, architecture §14).

    Values are vault-relative paths. Each segment is validated with the
    canonical containment primitives before any write, so a traversal-shaped
    value fails closed rather than escaping the configured root.
    """

    model_config = ConfigDict(extra="forbid")

    inbox: str = "00 Inbox/Atlas Captures"
    projects: str = "10 Projects"
    decisions: str = "20 Decisions"
    research: str = "30 Research"
    directives: str = "40 Directives"


class ObsidianConfig(BaseModel):
    """Obsidian projection settings for captures (AS-OBSIDIAN-CAPTURE-001).

    ``vault_path`` is an opt-in external Obsidian vault root. When unset the
    projection stays inside the Atlas vault under
    ``generated/obsidian/captures/`` — Atlas never writes outside ``--vault``
    unless an operator explicitly configures it to.
    """

    model_config = ConfigDict(extra="forbid")

    enabled: bool = True
    vault_path: str | None = None
    include_content: bool = True
    routing: ObsidianRoutingConfig = Field(default_factory=ObsidianRoutingConfig)


class CaptureProcessingConfig(BaseModel):
    """Capture processing switches (architecture §30, §37).

    ``ai_enrichment`` stays False: AS-OBSIDIAN-CAPTURE-001 is
    deterministic-only and no enrichment processor exists yet. Enabling it
    fails closed rather than silently doing nothing.
    """

    model_config = ConfigDict(extra="forbid")

    ai_enrichment: bool = False


class CaptureClipboardConfig(BaseModel):
    """Clipboard acquisition settings (architecture §22)."""

    model_config = ConfigDict(extra="forbid")

    enabled: bool = True


class CaptureConfig(BaseModel):
    """Capture subsystem settings (AS-OBSIDIAN-CAPTURE-001)."""

    model_config = ConfigDict(extra="forbid")

    deduplication: bool = True
    default_source_application: str = "unknown"
    clipboard: CaptureClipboardConfig = Field(default_factory=CaptureClipboardConfig)
    processing: CaptureProcessingConfig = Field(default_factory=CaptureProcessingConfig)


class AtlasConfig(BaseModel):
    """Top-level Project Atlas configuration."""

    model_config = ConfigDict(extra="forbid")

    discovery: DiscoveryConfig = Field(default_factory=DiscoveryConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    graphify: GraphifyConfig = Field(default_factory=GraphifyConfig)
    capture: CaptureConfig = Field(default_factory=CaptureConfig)
    obsidian: ObsidianConfig = Field(default_factory=ObsidianConfig)


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
