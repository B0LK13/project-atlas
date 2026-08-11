#!/usr/bin/env python3
"""Configuration discovery and environment fallback for Atlas agent scripts.

Shared by ``capture_event.py`` and ``check_documentation.py``. Standard
library only: the capture path must stay dependency-free (FR-S003).

Resolution order for every setting (highest precedence first):

1. explicit CLI argument;
2. environment variable (``ATLAS_*``);
3. configuration file;
4. built-in default.

Configuration file discovery: unless ``--config`` is given, the current
working directory and its parents are searched for ``atlas-agent.yaml``
or ``.atlas-agent.yaml``. The file uses a deliberately small YAML subset
(two levels of ``key: value`` maps, scalar values, ``#`` comments) so it
can be parsed without PyYAML. Anything outside that subset raises a
clear error instead of being silently misread.
"""

from __future__ import annotations

import os
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any

CONFIG_FILENAMES = ("atlas-agent.yaml", ".atlas-agent.yaml", ".atlas/agent.yaml")

#: Environment variable pointing at an explicit configuration file.
CONFIG_ENV_VAR = "ATLAS_AGENT_CONFIG"

#: Config load provenance. Only ``explicit`` / ``env`` grant execution authority
#: for normalizer executable selection (CODEX-SEC-021).
CONFIG_SOURCE_EXPLICIT = "explicit"
CONFIG_SOURCE_ENV = "env"
CONFIG_SOURCE_DISCOVERED = "discovered"
CONFIG_SOURCE_NONE = "none"


class ConfigError(ValueError):
    """Raised when a configuration file cannot be found or parsed."""


def config_grants_execution_authority(explicit: Path | None = None) -> bool:
    """True when the operator named the config (CLI ``--config`` or env).

    Upward-discovered repository configuration never grants execution
    authority for selecting a normalizer executable (CODEX-SEC-021).
    """
    if explicit is not None:
        return True
    return bool(str(os.environ.get(CONFIG_ENV_VAR, "")).strip())


def find_config(start: Path) -> Path | None:
    """Search ``start`` and its parents for a configuration file."""
    current = start.expanduser().resolve()
    if current.is_file():
        current = current.parent
    for directory in (current, *current.parents):
        for name in CONFIG_FILENAMES:
            candidate = directory / name
            if candidate.is_file():
                return candidate
    return None


def _parse_scalar(raw: str) -> Any:
    value = raw.strip()
    if value == "":
        return ""
    lowered = value.lower()
    if lowered in ("null", "~"):
        return None
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    if re.fullmatch(r"-?\d+", value):
        return int(value)
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
        return value[1:-1]
    return value


def parse_config_text(text: str) -> dict[str, dict[str, Any]]:
    """Parse the supported YAML subset into ``{section: {key: value}}``.

    Supported: top-level ``key: value`` or ``section:`` headers, one
    level of indented ``key: value`` pairs, scalars (string, integer,
    boolean, null), and comments. Lists, deeper nesting, anchors, and
    multi-line values are rejected with :class:`ConfigError`.
    """
    result: dict[str, dict[str, Any]] = {}
    current_section: str | None = None
    for number, raw_line in enumerate(text.splitlines(), start=1):
        if not raw_line.strip() or raw_line.strip().startswith("#"):
            continue
        if "\t" in raw_line[: len(raw_line) - len(raw_line.lstrip())]:
            raise ConfigError(f"line {number}: tabs are not supported")
        indented = raw_line[0] in (" ",)
        line = raw_line.strip()
        if " #" in line:
            line = line.split(" #", 1)[0].rstrip()
        if not line:
            continue
        if line.startswith("- "):
            raise ConfigError(f"line {number}: lists are not supported")
        if ":" not in line:
            raise ConfigError(f"line {number}: expected 'key: value'")
        key, _, value = line.partition(":")
        key = key.strip()
        value = value.strip()
        if not indented:
            current_section = None
            if value == "":
                result.setdefault(key, {})
                current_section = key
            else:
                result[key] = {"": _parse_scalar(value)}
        else:
            if current_section is None:
                raise ConfigError(f"line {number}: indented key without a section")
            section = result[current_section]
            if not isinstance(section, dict):
                raise ConfigError(f"line {number}: cannot nest under a scalar")
            section[key] = _parse_scalar(value)
    return result


def load_config(
    explicit: Path | None = None, *, start: Path | None = None
) -> tuple[dict[str, dict[str, Any]], Path | None, str]:
    """Load configuration; returns ``(config, path_used, source)``.

    Resolution order: ``explicit`` argument, then the
    ``ATLAS_AGENT_CONFIG`` environment variable, then upward discovery
    from ``start`` (default: current working directory). An explicitly
    named file (argument or environment) must exist; a missing
    discovered file simply yields an empty configuration.

    ``source`` is one of ``explicit``, ``env``, ``discovered``, or ``none``.
    Only ``explicit`` / ``env`` are execution-authoritative for selecting a
    normalizer executable (CODEX-SEC-021); ``discovered`` must not grant
    ``normalization.command`` authority.
    """
    if explicit is not None:
        path = explicit.expanduser()
        if not path.is_file():
            raise ConfigError(f"configuration file not found: {path}")
        return (
            parse_config_text(path.read_text(encoding="utf-8")),
            path,
            CONFIG_SOURCE_EXPLICIT,
        )

    env_named = os.environ.get(CONFIG_ENV_VAR)
    if env_named:
        path = Path(env_named).expanduser()
        if not path.is_file():
            raise ConfigError(f"configuration file not found: {path}")
        return (
            parse_config_text(path.read_text(encoding="utf-8")),
            path,
            CONFIG_SOURCE_ENV,
        )

    discovered = find_config(start or Path.cwd())
    if discovered is None:
        return {}, None, CONFIG_SOURCE_NONE
    return (
        parse_config_text(discovered.read_text(encoding="utf-8")),
        discovered,
        CONFIG_SOURCE_DISCOVERED,
    )


def config_value(
    config: Mapping[str, Mapping[str, Any]], section: str, key: str
) -> Any:
    """Fetch one configuration value, tolerating missing sections."""
    section_map = config.get(section)
    if not isinstance(section_map, Mapping):
        return None
    value = section_map.get(key)
    return None if value in (None, "") else value


def resolve(
    cli_value: Any,
    env_var: str | tuple[str, ...],
    config: Mapping[str, Mapping[str, Any]],
    section: str,
    key: str,
    default: Any = None,
) -> Any:
    """Resolve one setting: CLI > environment > config file > default.

    ``env_var`` may be a tuple of variable names; the first set variable
    wins, so deprecated names can be kept as aliases.
    """
    if cli_value is not None:
        return cli_value
    names = (env_var,) if isinstance(env_var, str) else env_var
    for name in names:
        env_value = os.environ.get(name)
        if env_value:
            return env_value
    file_value = config_value(config, section, key)
    if file_value is not None:
        return file_value
    return default
