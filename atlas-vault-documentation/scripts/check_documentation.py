#!/usr/bin/env python3
"""Validate raw Atlas agent events and detect unsynchronized spool work."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Sequence

import atlas_config

REQUIRED_KEYS = {
    "type", "id", "event_id", "event_kind", "occurred_at", "captured_at",
    "agent", "project_id", "project_slug", "sync_state",
    "normalization_state", "knowledge_state", "review_state",
}
EVENT_KINDS = {
    "session-start", "plan", "implementation", "refactor", "decision",
    "validation", "issue", "finding", "risk", "research", "deployment",
    "rollback", "migration", "recovery", "documentation", "handoff",
    "completion", "blocked",
}
SECRET_PATTERNS = [
    re.compile(r"sk-(?:proj-)?[A-Za-z0-9_-]{12,}", re.I),
    re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}", re.I),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----", re.I),
]


def parse_frontmatter(text: str) -> dict[str, str]:
    if not text.startswith("---\n"):
        raise ValueError("missing YAML frontmatter")
    end = text.find("\n---\n", 4)
    if end < 0:
        raise ValueError("unterminated YAML frontmatter")
    result: dict[str, str] = {}
    for line in text[4:end].splitlines():
        if not line or line.startswith(" ") or ":" not in line:
            continue
        key, value = line.split(":", 1)
        result[key.strip()] = value.strip().strip('"')
    return result


def validate_event(path: Path) -> list[str]:
    try:
        text = path.read_text(encoding="utf-8")
        metadata = parse_frontmatter(text)
    except (OSError, UnicodeError, ValueError) as exc:
        return [f"{path}: {exc}"]

    errors = []
    missing = sorted(REQUIRED_KEYS - set(metadata))
    if missing:
        errors.append(f"{path}: missing keys: {', '.join(missing)}")
    if metadata.get("event_kind") not in EVENT_KINDS:
        errors.append(
            f"{path}: unsupported event_kind={metadata.get('event_kind')!r}"
        )
    if metadata.get("knowledge_state") != "source":
        errors.append(f"{path}: raw event knowledge_state must be source")
    if metadata.get("review_state") == "verified":
        errors.append(f"{path}: raw event cannot self-assert verified")
    if any(pattern.search(text) for pattern in SECRET_PATTERNS):
        errors.append(f"{path}: likely secret detected")
    return errors


NORMALIZED_SUFFIX = ".normalized.md"
NORMALIZED_REQUIRED_KEYS = {"type", "id", "project_id", "event_kind", "status"}


def validate_normalized_event(path: Path) -> list[str]:
    """Validate a normalized `Agent Work Event` (not raw-event rules).

    Checks the MDA-STANDARD output contract plus the AS-WP-002 provenance
    block. Raw and normalized events are distinct artifact classes and
    are never validated with each other's rules.
    """
    try:
        text = path.read_text(encoding="utf-8")
        metadata = parse_frontmatter(text)
    except (OSError, UnicodeError, ValueError) as exc:
        return [f"{path}: {exc}"]

    errors = []
    missing = sorted(NORMALIZED_REQUIRED_KEYS - set(metadata))
    if missing:
        errors.append(f"{path}: missing keys: {', '.join(missing)}")
    if metadata.get("type") != "Agent Work Event":
        errors.append(f"{path}: normalized type must be 'Agent Work Event'")
    if metadata.get("event_kind") not in EVENT_KINDS:
        errors.append(
            f"{path}: unsupported event_kind={metadata.get('event_kind')!r}"
        )
    if "source:agent-event:" not in text:
        errors.append(f"{path}: normalized event lacks raw source reference")
    if "atlas_provenance:" not in text:
        errors.append(f"{path}: normalized event lacks atlas_provenance block")
    else:
        for key in ("raw_event_id", "raw_event_hash", "verification_status"):
            if key not in text:
                errors.append(f"{path}: atlas_provenance missing {key}")
    if any(pattern.search(text) for pattern in SECRET_PATTERNS):
        errors.append(f"{path}: likely secret detected")
    return errors


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument(
        "--config",
        type=Path,
        help="Configuration file (default: discover atlas-agent.yaml upward).",
    )
    result.add_argument("--vault", type=Path)
    result.add_argument("--spool-root", type=Path)
    result.add_argument("--strict", action="store_true")
    result.add_argument("--json", action="store_true", dest="json_output")
    return result


def _as_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in ("1", "true", "yes", "on")


def main(argv: Sequence[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        config, _, _ = atlas_config.load_config(args.config)
    except atlas_config.ConfigError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    vault = atlas_config.resolve(args.vault, "ATLAS_VAULT", config, "atlas", "vault")
    spool_root = atlas_config.resolve(
        args.spool_root, "ATLAS_SPOOL_ROOT", config, "atlas", "spool_root"
    )
    strict = args.strict or _as_bool(
        atlas_config.resolve(
            None,
            "ATLAS_STRICT",
            config,
            "validation",
            "fail_completion_on_unsynced_spool",
            False,
        )
    )

    if not vault and not spool_root:
        print(
            "ERROR: provide --vault and/or --spool-root "
            "(or ATLAS_VAULT / ATLAS_SPOOL_ROOT / config atlas.vault)",
            file=sys.stderr,
        )
        return 2

    files: list[Path] = []
    pending_spool: list[Path] = []

    if vault:
        source_root = Path(vault).expanduser().resolve() / "sources" / "agent-events"
        if source_root.exists():
            files.extend(source_root.rglob("*.md"))

    if spool_root:
        spool = Path(spool_root).expanduser().resolve() / ".atlas-spool"
        if spool.exists():
            pending_spool.extend(spool.glob("*.md"))
            files.extend(pending_spool)

    errors: list[str] = []
    unique_files = sorted(set(files))
    raw_files = [p for p in unique_files if not p.name.endswith(NORMALIZED_SUFFIX)]
    normalized_files = [p for p in unique_files if p.name.endswith(NORMALIZED_SUFFIX)]
    for path in raw_files:
        errors.extend(validate_event(path))
    for path in normalized_files:
        errors.extend(validate_normalized_event(path))
    if strict and pending_spool:
        errors.append(f"{len(pending_spool)} unsynchronized spool event(s)")

    payload = {
        "ok": not errors,
        "files_checked": len(unique_files),
        "raw_checked": len(raw_files),
        "normalized_checked": len(normalized_files),
        "pending_spool": len(pending_spool),
        "errors": errors,
    }
    if args.json_output:
        print(json.dumps(payload, ensure_ascii=False))
    else:
        print(f"Checked {payload['files_checked']} event file(s) "
              f"({payload['raw_checked']} raw, {payload['normalized_checked']} normalized)")
        print(f"Pending spool: {payload['pending_spool']}")
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
