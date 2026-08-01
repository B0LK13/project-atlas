#!/usr/bin/env python3
"""Normalize one raw Atlas agent event through mda-cli (AS-WP-002).

Pipeline: validate raw event → build a deterministic mda-cli command →
execute with timeout and redaction → discover the output → verify it →
inject verifiable provenance. Raw evidence is never modified and
``--in-place`` is never used (AS-009).

Exit codes:

- 0: normalized (or normalization disabled by configuration);
- 2: usage error (invalid arguments, unsafe names, configuration);
- 3: operational error (unsafe path, pre-existing output, I/O);
- 4: normalization failure (executable missing, timeout, provider
  failure, missing output, invalid raw event);
- 5: verification failure (output exists but failed verification).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from collections.abc import Sequence
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import atlas_config  # noqa: E402
import capture_event  # noqa: E402
import check_documentation  # noqa: E402
from internal import normalization  # noqa: E402

EXIT_OK = 0
EXIT_USAGE = 2
EXIT_OPERATIONAL = 3
EXIT_NORMALIZATION_FAILED = 4
EXIT_VERIFICATION_FAILED = 5

DEFAULT_SKILL_DIR = Path(__file__).resolve().parent.parent


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--event", type=Path, required=True, help="Raw event Markdown file.")
    result.add_argument("--root", type=Path, help="Allowed root containing raw and output.")
    result.add_argument("--config", type=Path, help="Configuration file.")
    result.add_argument("--mda-command", help="mda-cli executable (default: mda).")
    result.add_argument("--skill", help="Installed skill name.")
    result.add_argument("--skill-dir", type=Path, help="Repository-local skill directory.")
    result.add_argument("--provider", help="Configured provider name (recorded, not forwarded).")
    result.add_argument("--timeout", type=float, help="Per-attempt timeout in seconds.")
    result.add_argument("--retries", type=int, help="Retries for transient failures.")
    result.add_argument("--output-mode", choices=["sibling", "directory"])
    result.add_argument("--output-dir", type=Path, help="Required for directory mode.")
    result.add_argument("--no-verify", action="store_true", help="Skip output verification.")
    result.add_argument("--dry-run", action="store_true", help="Print the plan; do not execute.")
    result.add_argument("--json", action="store_true", dest="json_output")
    return result


def _bool(value: object, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in ("1", "true", "yes", "on")


def _resolve_settings(
    args: argparse.Namespace,
) -> tuple[normalization.NormalizationSettings, dict[str, Any]]:
    config, _ = atlas_config.load_config(args.config)
    section = "normalization"

    skill_dir_value = atlas_config.resolve(
        args.skill_dir, "ATLAS_SKILL_DIR", config, section, "skill_dir"
    )
    skill = atlas_config.resolve(
        args.skill, "ATLAS_SKILL", config, section, "skill_id", "atlas-vault-documentation"
    )
    output_mode = atlas_config.resolve(
        args.output_mode, "ATLAS_OUTPUT_MODE", config, section, "output_mode", "sibling"
    )
    output_dir_value = atlas_config.resolve(
        args.output_dir, "ATLAS_OUTPUT_DIR", config, section, "output_directory"
    )
    provider = atlas_config.resolve(
        args.provider, "ATLAS_PROVIDER", config, section, "provider", "unknown"
    )
    timeout = atlas_config.resolve(
        args.timeout, "ATLAS_NORMALIZATION_TIMEOUT", config, section, "timeout", 120
    )
    retries = atlas_config.resolve(
        args.retries, "ATLAS_NORMALIZATION_RETRIES", config, section, "retries", 0
    )

    if output_mode not in ("sibling", "directory"):
        raise atlas_config.ConfigError(f"invalid output_mode: {output_mode!r}")
    if not normalization.SAFE_NAME.fullmatch(str(provider)):
        raise atlas_config.ConfigError(f"unsafe provider name: {provider!r}")
    if skill_dir_value is None and not normalization.SAFE_NAME.fullmatch(str(skill)):
        raise atlas_config.ConfigError(f"unsafe skill name: {skill!r}")
    try:
        timeout_value = float(timeout)
        retries_value = int(retries)
    except (TypeError, ValueError) as exc:
        raise atlas_config.ConfigError(f"invalid timeout/retries: {exc}") from exc
    if timeout_value <= 0:
        raise atlas_config.ConfigError("timeout must be positive")
    if retries_value < 0:
        raise atlas_config.ConfigError("retries must not be negative")

    verify = not args.no_verify and _bool(
        atlas_config.config_value(config, section, "verify"), True
    )
    enabled = _bool(atlas_config.config_value(config, section, "enabled"), True)
    record_command = _bool(
        atlas_config.config_value(config, section, "record_command"), True
    )

    return (
        normalization.NormalizationSettings(
            mda_command=str(
                atlas_config.resolve(
                    args.mda_command, "ATLAS_MDA_COMMAND", config, section, "command", "mda"
                )
            ),
            skill=str(skill),
            skill_dir=Path(skill_dir_value).expanduser() if skill_dir_value else DEFAULT_SKILL_DIR,
            provider=str(provider),
            timeout_seconds=timeout_value,
            retries=retries_value,
            output_mode=str(output_mode),
            output_dir=Path(output_dir_value).expanduser() if output_dir_value else None,
            verify=verify,
            record_command=record_command,
            enabled=enabled,
        ),
        config,
    )


def _event_id_of(raw_event: Path) -> str:
    metadata = check_documentation.parse_frontmatter(
        raw_event.read_text(encoding="utf-8")
    )
    event_id = metadata.get("event_id", "")
    if not event_id:
        raise ValueError(f"raw event has no event_id: {raw_event}")
    return event_id


def _emit(payload: dict[str, Any], args: argparse.Namespace, human: str) -> None:
    if args.json_output:
        print(json.dumps(payload, ensure_ascii=False))
    else:
        print(human)


def main(argv: Sequence[str] | None = None) -> int:
    args = parser().parse_args(argv)

    try:
        settings, config = _resolve_settings(args)
    except atlas_config.ConfigError as exc:
        print(f"ERROR: {capture_event.redact(str(exc))}", file=sys.stderr)
        return EXIT_USAGE

    raw_event = args.event.expanduser()
    try:
        event_id = _event_id_of(raw_event)
    except OSError as exc:
        print(f"ERROR: {capture_event.redact(str(exc))}", file=sys.stderr)
        return EXIT_OPERATIONAL
    except (ValueError, UnicodeError) as exc:
        print(f"ERROR: {capture_event.redact(str(exc))}", file=sys.stderr)
        return EXIT_USAGE

    root_value = atlas_config.resolve(
        args.root, "ATLAS_VAULT", config, "atlas", "vault"
    )
    if root_value is None:
        # Default allowed root: derive from the raw event's *unresolved*
        # path so symlink escapes cannot smuggle in a wider root. Use the
        # vault marker directory "sources" when present, else the
        # spool/repository root (grandparent of the raw event).
        marker_path = raw_event.expanduser().absolute()
        parts = marker_path.parts
        root = (
            Path(*parts[: parts.index("sources")])
            if "sources" in parts
            else marker_path.parent.parent
        )
    else:
        root = Path(root_value).expanduser()

    if not settings.enabled:
        payload = {
            "ok": True,
            "event_id": event_id,
            "status": "disabled",
            "raw_event": str(raw_event),
            "normalized_event": None,
            "category": "disabled",
            "message": "normalization disabled by configuration",
        }
        _emit(payload, args, f"Normalization disabled: {event_id}")
        return EXIT_OK

    try:
        plan_command = normalization.build_command(settings, raw_event.resolve())
        plan_output = normalization.expected_output(settings, raw_event.resolve())
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return EXIT_USAGE

    if args.dry_run:
        payload = {
            "ok": True,
            "event_id": event_id,
            "status": "dry-run",
            "command": plan_command,
            "expected_output": str(plan_output),
            "root": str(root),
            "verify": settings.verify,
            "provider": settings.provider,
        }
        _emit(payload, args, "Dry run: " + " ".join(plan_command))
        return EXIT_OK

    try:
        result = normalization.normalize(
            settings,
            raw_event=raw_event,
            root=root,
            event_id=event_id,
            redact=capture_event.redact,
            verify_raw=check_documentation.validate_event,
        )
    except ValueError as exc:
        print(f"ERROR: {capture_event.redact(str(exc))}", file=sys.stderr)
        return EXIT_OPERATIONAL
    except OSError as exc:
        print(f"ERROR: {capture_event.redact(str(exc))}", file=sys.stderr)
        return EXIT_OPERATIONAL

    payload = result.as_dict()
    if result.ok:
        _emit(payload, args, f"Normalized {event_id}: {result.normalized_event}")
        return EXIT_OK
    _emit(payload, args, f"FAILED {event_id}: {result.message}")
    if not args.json_output:
        print(f"ERROR: {result.message}", file=sys.stderr)
    if result.category == normalization.CATEGORY_OUTPUT_EXISTS:
        return EXIT_OPERATIONAL
    if result.category == normalization.CATEGORY_VERIFICATION_FAILED:
        return EXIT_VERIFICATION_FAILED
    return EXIT_NORMALIZATION_FAILED


if __name__ == "__main__":
    raise SystemExit(main())
