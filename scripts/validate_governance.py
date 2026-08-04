#!/usr/bin/env python3
"""AS-GH-001 governance validation script.

Validates the GitHub-facing governance surface added by AS-GH-001
without inventing new infrastructure: duplicate-key-sensitive YAML
parsing for every workflow, Dependabot config, and evidence receipt;
required-section presence in the new governance documents; and a
sanity check that every `uses:` reference in a workflow is pinned to a
commit SHA rather than a floating tag/branch.

This script is intentionally standalone (callable locally or from a
future CI job) rather than assumed as an already-required branch
protection check -- per ADR-006's "no required check before a
successful real run" rule, it is added here as an available command
first.

Exit code 0 on success, 1 on any validation failure.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parent.parent

REQUIRED_DOC_SECTIONS: dict[str, list[str]] = {
    "SECURITY.md": [
        "## Supported versions",
        "## Reporting a vulnerability",
        "## Response expectations",
    ],
    "CONTRIBUTING.md": [
        "## Workflow",
        "## Governed-agent sessions",
    ],
}

_SHA_PIN_RE = re.compile(r"^[0-9a-f]{40}$")


class _DuplicateKeyError(ValueError):
    pass


def _no_duplicate_keys_loader() -> type[yaml.SafeLoader]:
    class DupCheckLoader(yaml.SafeLoader):
        pass

    def _construct_mapping(loader: yaml.SafeLoader, node: yaml.MappingNode) -> dict[str, Any]:
        mapping: dict[str, Any] = {}
        for key_node, value_node in node.value:
            key = loader.construct_object(key_node, deep=True)
            if key in mapping:
                raise _DuplicateKeyError(f"duplicate key: {key!r}")
            mapping[key] = loader.construct_object(value_node, deep=True)
        return mapping

    DupCheckLoader.add_constructor(
        yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _construct_mapping
    )
    return DupCheckLoader


def _check_yaml_files(paths: list[Path]) -> list[str]:
    errors: list[str] = []
    loader = _no_duplicate_keys_loader()
    for path in paths:
        if not path.is_file():
            continue
        try:
            yaml.load(path.read_text(encoding="utf-8"), Loader=loader)
        except _DuplicateKeyError as exc:
            errors.append(f"{path}: {exc}")
        except yaml.YAMLError as exc:
            errors.append(f"{path}: YAML parse error: {exc}")
    return errors


def _check_required_sections() -> list[str]:
    errors: list[str] = []
    for name, sections in REQUIRED_DOC_SECTIONS.items():
        path = ROOT / name
        if not path.is_file():
            errors.append(f"{name}: file does not exist")
            continue
        text = path.read_text(encoding="utf-8")
        for section in sections:
            if section not in text:
                errors.append(f"{name}: missing required section {section!r}")
    return errors


def _check_action_pins() -> list[str]:
    errors: list[str] = []
    workflow_dir = ROOT / ".github" / "workflows"
    if not workflow_dir.is_dir():
        return errors
    for path in sorted(workflow_dir.glob("*.yml")):
        text = path.read_text(encoding="utf-8")
        for line_no, line in enumerate(text.splitlines(), start=1):
            match = re.search(r"uses:\s*([^\s#]+)", line)
            if not match:
                continue
            reference = match.group(1)
            if "@" not in reference:
                errors.append(f"{path}:{line_no}: action reference has no @ pin: {reference!r}")
                continue
            _, _, pin = reference.rpartition("@")
            if not _SHA_PIN_RE.match(pin):
                errors.append(
                    f"{path}:{line_no}: action not pinned to a 40-character commit SHA: "
                    f"{reference!r}"
                )
    return errors


def main() -> int:
    errors: list[str] = []

    yaml_targets = [
        ROOT / ".github" / "dependabot.yml",
        *sorted((ROOT / ".github" / "workflows").glob("*.yml")),
        *sorted((ROOT / ".github" / "ISSUE_TEMPLATE").glob("*.yml")),
        *sorted((ROOT / "docs" / "evidence").glob("*.yaml")),
    ]
    errors.extend(_check_yaml_files(yaml_targets))
    errors.extend(_check_required_sections())
    errors.extend(_check_action_pins())

    if errors:
        print(f"[governance] FAILED with {len(errors)} error(s):", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        return 1

    print(
        f"[governance] PASSED: {len(yaml_targets)} YAML target(s) checked, "
        f"{len(REQUIRED_DOC_SECTIONS)} document(s) checked, action pins verified."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
