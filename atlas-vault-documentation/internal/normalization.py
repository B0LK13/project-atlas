"""Normalization orchestration (AS-WP-002, Priority 1).

Composes process execution, provenance, and verification into one
fail-closed pipeline:

    validate input → build command → snapshot → run mda-cli →
    discover output → verify → inject provenance → report

mda-cli is treated as untrusted: success is only accepted after
verification. Every failure becomes a structured, redacted record.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from internal import process_runner, provenance, verification
from internal.process_runner import resolve_executable_argv

#: Provider/executable-adjacent names must be simple identifiers.
SAFE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")

OUTPUT_SUFFIX = ".normalized.md"

#: Normalization-phase failure categories (exit 4).
CATEGORY_MISSING_OUTPUT = "missing-output"
CATEGORY_INVALID_RAW_EVENT = "invalid-raw-event"
CATEGORY_DISABLED = "disabled"
#: Verification-phase failure category (exit 5).
CATEGORY_VERIFICATION_FAILED = "verification-failed"
#: Operational failure categories (exit 3).
CATEGORY_OUTPUT_EXISTS = "output-exists"
CATEGORY_UNSAFE_PATH = "unsafe-path"


@dataclass(frozen=True)
class NormalizationSettings:
    """Fully resolved normalization settings."""

    mda_command: str
    skill: str
    skill_dir: Path | None
    provider: str
    timeout_seconds: float
    retries: int
    output_mode: str  # "sibling" | "directory"
    output_dir: Path | None
    verify: bool
    record_command: bool
    enabled: bool


@dataclass(frozen=True)
class NormalizationResult:
    """Structured outcome; also the JSON contract payload shape."""

    ok: bool
    event_id: str
    status: str  # normalized | disabled | failed | verification-failed
    raw_event: str
    normalized_event: str | None
    category: str | None
    message: str
    attempts: int = 0
    duration_seconds: float = 0.0
    provenance: dict[str, Any] | None = field(default=None)
    problems: tuple[str, ...] = field(default_factory=tuple)

    def as_dict(self) -> dict[str, Any]:
        data = {
            "ok": self.ok,
            "event_id": self.event_id,
            "status": self.status,
            "raw_event": self.raw_event,
            "normalized_event": self.normalized_event,
            "category": self.category,
            "message": self.message,
            "attempts": self.attempts,
            "duration_seconds": round(self.duration_seconds, 3),
            "problems": list(self.problems),
        }
        if self.provenance is not None:
            data["provenance"] = self.provenance
        return data


def build_command(settings: NormalizationSettings, raw_event: Path) -> list[str]:
    """Construct the mda-cli argument array (never a shell string)."""
    argv = list(resolve_executable_argv(settings.mda_command))
    if settings.skill_dir is not None:
        argv.extend(["--skill-dir", str(settings.skill_dir)])
    else:
        argv.extend(["--skill", settings.skill])
    if settings.output_mode == "directory":
        if settings.output_dir is None:
            raise ValueError("output_mode 'directory' requires output_dir")
        argv.extend(["--output-folder", str(settings.output_dir)])
    # Raw evidence is immutable: --in-place is never emitted (AS-009).
    argv.append(str(raw_event))
    return argv


def _stem(path: Path) -> str:
    return path.name[: -len(".md")] if path.name.endswith(".md") else path.name


def expected_output(settings: NormalizationSettings, raw_event: Path) -> Path:
    """Deterministic expected output path for the configured mode."""
    name = _stem(raw_event) + OUTPUT_SUFFIX
    if settings.output_mode == "sibling":
        return raw_event.parent / name
    if settings.output_dir is None:
        raise ValueError("output_mode 'directory' requires output_dir")
    return settings.output_dir / name


def write_failure_record(
    raw_event: Path,
    *,
    event_id: str,
    category: str,
    message: str,
    command: Sequence[str] | None,
) -> Path:
    """Persist a structured, redacted failure record next to the raw event."""
    record = {
        "type": "normalization-failure",
        "event_id": event_id,
        "category": category,
        "message": message,
        "command": list(command) if command else None,
        "recorded_at": provenance.utc_timestamp(),
    }
    target = raw_event.with_name(_stem(raw_event) + ".normalization-failed.json")
    provenance.atomic_replace(target, json.dumps(record, ensure_ascii=False, indent=2) + "\n")
    return target


def _fail(
    raw_event: Path,
    event_id: str,
    *,
    status: str,
    category: str,
    message: str,
    command: Sequence[str] | None = None,
    attempts: int = 0,
    duration: float = 0.0,
    problems: tuple[str, ...] = (),
) -> NormalizationResult:
    write_failure_record(
        raw_event, event_id=event_id, category=category, message=message, command=command
    )
    return NormalizationResult(
        ok=False,
        event_id=event_id,
        status=status,
        raw_event=str(raw_event),
        normalized_event=None,
        category=category,
        message=message,
        attempts=attempts,
        duration_seconds=duration,
        problems=problems,
    )


def normalize(
    settings: NormalizationSettings,
    *,
    raw_event: Path,
    root: Path,
    event_id: str,
    redact: Callable[[str], str],
    verify_raw: Callable[[Path], list[str]],
) -> NormalizationResult:
    """Run the full normalization pipeline for one raw event.

    ``redact`` is the shared secret redactor; ``verify_raw`` validates
    the raw event file and returns a list of problems (empty = valid).
    """
    raw_event = raw_event.resolve()
    root = root.resolve()

    # --- input validation -------------------------------------------------
    verification.ensure_inside_root(root, raw_event)
    if not raw_event.is_file():
        raise FileNotFoundError(f"raw event not found: {raw_event}")
    raw_problems = verify_raw(raw_event)
    if raw_problems:
        return _fail(
            raw_event, event_id,
            status="failed", category=CATEGORY_INVALID_RAW_EVENT,
            message="raw event failed validation",
            problems=tuple(raw_problems),
        )

    output = expected_output(settings, raw_event)
    verification.ensure_inside_root(root, output)
    watch_directory = output.parent
    if output.exists():
        return _fail(
            raw_event, event_id,
            status="failed", category=CATEGORY_OUTPUT_EXISTS,
            message=f"expected output already exists: {output}",
        )

    argv = build_command(settings, raw_event)

    # --- execution ---------------------------------------------------------
    before = verification.snapshot(watch_directory)
    version = process_runner.command_version(
        settings.mda_command, timeout_seconds=min(settings.timeout_seconds, 30),
        redact=redact,
    )
    result = process_runner.run_command(
        argv,
        timeout_seconds=settings.timeout_seconds,
        redact=redact,
        retries=settings.retries,
    )
    if not result.ok:
        detail = result.stderr.strip() or result.category or "unknown error"
        return _fail(
            raw_event, event_id,
            status="failed", category=result.category or "unknown",
            message=f"mda-cli {result.category}: {detail}",
            command=argv if settings.record_command else None,
            attempts=result.attempts, duration=result.duration_seconds,
        )

    # --- discovery ----------------------------------------------------------
    if not output.exists():
        return _fail(
            raw_event, event_id,
            status="failed", category=CATEGORY_MISSING_OUTPUT,
            message=f"mda-cli exited 0 but produced no output at {output}",
            command=argv if settings.record_command else None,
            attempts=result.attempts, duration=result.duration_seconds,
        )

    # --- verification --------------------------------------------------------
    verification_status = "skipped"
    verified_at = None
    problems: tuple[str, ...] = ()
    if settings.verify:
        check = verification.verify_output(
            output,
            root=root,
            raw_event_id=event_id,
            watch_directory=watch_directory,
            before=before,
        )
        if not check.verified:
            return _fail(
                raw_event, event_id,
                status="verification-failed",
                category=CATEGORY_VERIFICATION_FAILED,
                message="normalized output failed verification",
                command=argv if settings.record_command else None,
                attempts=result.attempts,
                duration=result.duration_seconds,
                problems=check.problems,
            )
        verification_status = "verified"
        verified_at = provenance.utc_timestamp()

    # --- provenance injection -------------------------------------------------
    prov = provenance.Provenance(
        raw_event_id=event_id,
        raw_event_hash=provenance.sha256_file(raw_event),
        normalized_at=provenance.utc_timestamp(),
        tool=settings.mda_command,
        command_version=version,
        command_arguments=tuple(argv) if settings.record_command else None,
        skill=settings.skill if settings.skill_dir is None else str(settings.skill_dir),
        provider=settings.provider,
        output_mode=settings.output_mode,
        verification_status=verification_status,
        verified_at=verified_at,
    )
    original_text = output.read_text(encoding="utf-8")
    injected = provenance.inject_provenance(original_text, prov)
    provenance.atomic_replace(output, injected)

    return NormalizationResult(
        ok=True,
        event_id=event_id,
        status="normalized",
        raw_event=str(raw_event),
        normalized_event=str(output),
        category=None,
        message="normalized and verified" if settings.verify else "normalized (verification skipped)",
        attempts=result.attempts,
        duration_seconds=result.duration_seconds,
        provenance=prov.as_dict(),
    )
