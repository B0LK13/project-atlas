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
from internal.mda_output_contract import (
    MdaOutputContract,
    UnknownMdaContractError,
    expected_output_path,
    is_mda_output_artifact,
    resolve_output_contract,
)
from internal.process_runner import resolve_executable_argv

#: Provider/executable-adjacent names must be simple identifiers.
SAFE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")

#: Normalization-phase failure categories (exit 4).
CATEGORY_MISSING_OUTPUT = "missing-output"
CATEGORY_EMPTY_OUTPUT = "empty-output"
CATEGORY_STALE_OUTPUT = "stale-output"
CATEGORY_AMBIGUOUS_OUTPUT = "ambiguous-output"
CATEGORY_UNKNOWN_CONTRACT = "unknown-contract"
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


def probe_output_contract(
    settings: NormalizationSettings,
    *,
    redact: Callable[[str], str],
) -> tuple[process_runner.ProcessResult, MdaOutputContract | None]:
    """Probe ``mda --version`` and map it to a trusted output contract.

    Executable-missing and permission-denied stay those categories.
    A successful probe of an unrecognized version is ``unknown-contract``.
    """
    probe = process_runner.run_command(
        [*resolve_executable_argv(settings.mda_command), "--version"],
        timeout_seconds=min(settings.timeout_seconds, 30),
        redact=redact,
    )
    if not probe.ok:
        return probe, None
    version_line = (probe.stdout or "").strip().splitlines()
    line = version_line[0] if version_line else ""
    try:
        return probe, resolve_output_contract(line)
    except UnknownMdaContractError:
        return probe, None


def build_command(
    settings: NormalizationSettings,
    raw_event: Path,
    contract: MdaOutputContract | None = None,
) -> list[str]:
    """Construct the mda-cli argument array (never a shell string).

    Directory mode uses the version contract's flag (mda-cli 0.2.9: ``--out-dir``).
    ``--output-folder`` is not a mda-cli 0.2.9 flag and is never emitted.
    Unknown contracts cannot select a directory flag.
    """
    argv = list(resolve_executable_argv(settings.mda_command))
    if settings.skill_dir is not None:
        argv.extend(["--skill-dir", str(settings.skill_dir)])
    else:
        argv.extend(["--skill", settings.skill])
    if settings.output_mode == "directory":
        if settings.output_dir is None:
            raise ValueError("output_mode 'directory' requires output_dir")
        if contract is None:
            raise UnknownMdaContractError(
                "directory mode requires a recognized mda-cli output contract"
            )
        argv.extend([contract.directory_flag, str(settings.output_dir)])
    # Raw evidence is immutable: --in-place is never emitted (AS-009).
    argv.append(str(raw_event))
    return argv


def _stem(path: Path) -> str:
    return path.name[: -len(".md")] if path.name.endswith(".md") else path.name


def expected_output(
    settings: NormalizationSettings,
    raw_event: Path,
    contract: MdaOutputContract,
) -> Path:
    """Deterministic expected output path from the trusted version contract."""
    return expected_output_path(
        raw_event,
        contract,
        output_mode=settings.output_mode,
        output_dir=settings.output_dir,
    )


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

    probe, contract = probe_output_contract(settings, redact=redact)
    if contract is None:
        if probe.category == process_runner.CATEGORY_EXECUTABLE_MISSING:
            return _fail(
                raw_event, event_id,
                status="failed",
                category=process_runner.CATEGORY_EXECUTABLE_MISSING,
                message="mda-cli executable-missing: version probe failed",
            )
        if probe.category == process_runner.CATEGORY_PERMISSION_DENIED:
            return _fail(
                raw_event, event_id,
                status="failed",
                category=process_runner.CATEGORY_PERMISSION_DENIED,
                message="mda-cli permission-denied: version probe failed",
            )
        if probe.category is not None:
            detail = probe.stderr.strip() or probe.category
            return _fail(
                raw_event, event_id,
                status="failed",
                category=probe.category,
                message=f"mda-cli {probe.category}: {detail}",
                attempts=probe.attempts,
                duration=probe.duration_seconds,
            )
        version_line = (probe.stdout or "").strip().splitlines()
        line = version_line[0] if version_line else "unknown"
        return _fail(
            raw_event, event_id,
            status="failed",
            category=CATEGORY_UNKNOWN_CONTRACT,
            message=f"unrecognized mda-cli version contract: {line!r}",
        )
    version = (probe.stdout or "").strip().splitlines()[0][:200]

    output = expected_output(settings, raw_event, contract)
    verification.ensure_inside_root(root, output)
    watch_directory = output.parent
    if output.exists():
        return _fail(
            raw_event, event_id,
            status="failed", category=CATEGORY_OUTPUT_EXISTS,
            message=f"expected output already exists: {output}",
        )

    argv = build_command(settings, raw_event, contract)
    if "--output-folder" in argv:
        return _fail(
            raw_event, event_id,
            status="failed",
            category=CATEGORY_UNKNOWN_CONTRACT,
            message="refusing non-0.2.9 flag --output-folder",
        )

    # --- execution ---------------------------------------------------------
    before = verification.snapshot(watch_directory)
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

    # --- discovery: explicit contract path only, never newest-sibling scan
    after = verification.snapshot(watch_directory)
    new_files = after - before
    resolved_output = output.resolve() if output.exists() else output
    created_this_run = output in new_files or resolved_output in new_files

    if not output.exists():
        return _fail(
            raw_event, event_id,
            status="failed", category=CATEGORY_MISSING_OUTPUT,
            message=f"mda-cli exited 0 but produced no output at {output}",
            command=argv if settings.record_command else None,
            attempts=result.attempts, duration=result.duration_seconds,
        )
    if output.stat().st_size == 0:
        return _fail(
            raw_event, event_id,
            status="failed", category=CATEGORY_EMPTY_OUTPUT,
            message=f"mda-cli exited 0 but expected output is empty: {output}",
            command=argv if settings.record_command else None,
            attempts=result.attempts, duration=result.duration_seconds,
        )
    if not created_this_run:
        return _fail(
            raw_event, event_id,
            status="failed", category=CATEGORY_STALE_OUTPUT,
            message=f"stale output was not created by this invocation: {output}",
            command=argv if settings.record_command else None,
            attempts=result.attempts, duration=result.duration_seconds,
        )

    extra_contract_outputs = sorted(
        path
        for path in new_files
        if is_mda_output_artifact(path.name)
        and path != output
        and path != resolved_output
    )
    if extra_contract_outputs:
        return _fail(
            raw_event, event_id,
            status="failed",
            category=CATEGORY_AMBIGUOUS_OUTPUT,
            message="ambiguous mda output: multiple contract-shaped artifacts",
            command=argv if settings.record_command else None,
            attempts=result.attempts,
            duration=result.duration_seconds,
            problems=tuple(str(path) for path in extra_contract_outputs),
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
