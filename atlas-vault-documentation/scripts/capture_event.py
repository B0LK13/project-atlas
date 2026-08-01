#!/usr/bin/env python3
"""Capture an immutable Project Atlas agent work event."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import secrets
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Sequence

import atlas_config

EVENT_KINDS = {
    "session-start", "plan", "implementation", "refactor", "decision",
    "validation", "issue", "finding", "risk", "research", "deployment",
    "rollback", "migration", "recovery", "documentation", "handoff",
    "completion", "blocked",
}

SECRET_PATTERNS = [
    re.compile(r"(?i)\b(sk-(?:proj-)?[A-Za-z0-9_-]{12,})\b"),
    re.compile(r"(?i)\b(gh[pousr]_[A-Za-z0-9]{20,})\b"),
    re.compile(r"(?i)\b(AKIA[0-9A-Z]{16})\b"),
    re.compile(r"(?i)((?:api[_-]?key|token|password|secret)\s*[=:]\s*)(\S+)"),
    re.compile(
        r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----.*?"
        r"-----END (?:RSA |EC |OPENSSH )?PRIVATE KEY-----",
        re.S,
    ),
]

SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,159}$")
SAFE_SLUG = re.compile(r"^[a-z0-9][a-z0-9-]{0,99}$")


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def redact(value: str) -> str:
    result = value
    for pattern in SECRET_PATTERNS:
        if pattern.groups >= 2:
            result = pattern.sub(lambda match: f"{match.group(1)}[REDACTED SECRET]", result)
        else:
            result = pattern.sub("[REDACTED SECRET]", result)
    return result


def yaml_scalar(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def bullet_lines(values: Iterable[str], empty: str = "- None recorded.") -> str:
    items = [redact(value.strip()) for value in values if value and value.strip()]
    return "\n".join(f"- {item}" for item in items) if items else empty


def build_event_id(now: datetime, project_slug: str, summary: str) -> str:
    entropy = secrets.token_hex(4)
    digest = hashlib.sha256(f"{summary}|{entropy}".encode()).hexdigest()[:8]
    return f"AE-{now.strftime('%Y%m%dT%H%M%SZ')}-{project_slug}-{digest}"


def ensure_descendant(root: Path, candidate: Path) -> None:
    resolved_root = root.resolve()
    resolved_candidate = candidate.resolve()
    try:
        resolved_candidate.relative_to(resolved_root)
    except ValueError as exc:
        raise ValueError(f"unsafe output path outside root: {resolved_candidate}") from exc


def atomic_write_new(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise FileExistsError(f"event already exists: {path}")
    fd, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        if path.exists():
            raise FileExistsError(f"event already exists: {path}")
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def parse_time(raw: str | None) -> datetime:
    if not raw:
        return utc_now()
    parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("--occurred-at must include a timezone")
    return parsed.astimezone(timezone.utc)


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument(
        "--config",
        type=Path,
        help="Configuration file (default: discover atlas-agent.yaml upward).",
    )
    target = result.add_mutually_exclusive_group()
    target.add_argument("--vault", type=Path)
    target.add_argument("--spool", type=Path)
    result.add_argument("--project-id")
    result.add_argument("--project-slug")
    result.add_argument("--event-kind", required=True, choices=sorted(EVENT_KINDS))
    result.add_argument("--summary", required=True)
    result.add_argument("--agent")
    result.add_argument("--event-id")
    result.add_argument("--occurred-at")
    result.add_argument("--session-id")
    result.add_argument("--work-package")
    result.add_argument("--repository")
    result.add_argument("--branch")
    result.add_argument("--commit")
    result.add_argument("--adapter-id", default="unknown")
    result.add_argument("--skill-id", default="unknown")
    result.add_argument("--skill-version", default="unknown")
    result.add_argument("--skill-sha256", default="unknown")
    result.add_argument("--objective", default="Not recorded.")
    result.add_argument("--outcome", default="Not recorded.")
    result.add_argument("--changed-file", action="append", default=[])
    result.add_argument("--command", action="append", default=[])
    result.add_argument("--result", action="append", default=[])
    result.add_argument("--validation", action="append", default=[])
    result.add_argument("--decision", action="append", default=[])
    result.add_argument("--risk", action="append", default=[])
    result.add_argument("--evidence", action="append", default=[])
    result.add_argument("--next-action", action="append", default=[])
    result.add_argument("--atlas-target", action="append", default=[])
    result.add_argument("--json", action="store_true", dest="json_output")
    return result


def render(
    args: argparse.Namespace,
    event_id: str,
    occurred: datetime,
    captured: datetime,
    sync_state: str,
) -> str:
    commands = []
    for index in range(max(len(args.command), len(args.result))):
        command = args.command[index] if index < len(args.command) else "[MISSING: command]"
        observed = args.result[index] if index < len(args.result) else "[MISSING: observed result]"
        commands.append(
            f"**Command:** `{redact(command)}`\n"
            f"  - **Observed result:** {redact(observed)}"
        )

    return f"""---
type: Agent Work Event Source
id: source:agent-event:{event_id}
event_id: {yaml_scalar(event_id)}
event_kind: {yaml_scalar(args.event_kind)}
occurred_at: {yaml_scalar(occurred.isoformat().replace("+00:00", "Z"))}
captured_at: {yaml_scalar(captured.isoformat().replace("+00:00", "Z"))}
agent: {yaml_scalar(redact(args.agent))}
project_id: {yaml_scalar(redact(args.project_id))}
project_slug: {yaml_scalar(args.project_slug)}
session_id: {yaml_scalar(redact(args.session_id))}
work_package: {yaml_scalar(redact(args.work_package))}
repository: {yaml_scalar(redact(args.repository))}
branch: {yaml_scalar(redact(args.branch))}
commit: {yaml_scalar(redact(args.commit))}
adapter_id: {yaml_scalar(redact(args.adapter_id))}
skill_id: {yaml_scalar(redact(args.skill_id))}
skill_version: {yaml_scalar(redact(args.skill_version))}
skill_sha256: {yaml_scalar(redact(args.skill_sha256))}
sync_state: {sync_state}
normalization_state: pending
knowledge_state: source
review_state: generated
tags:
  - agent-event-source
  - {args.event_kind}
---

# {redact(args.summary)}

## Objective or trigger

{redact(args.objective)}

## Outcome

{redact(args.outcome)}

## Changed files or systems

{bullet_lines(args.changed_file)}

## Commands and observed results

{bullet_lines(commands)}

## Validation

{bullet_lines(args.validation)}

## Decisions and rationale

{bullet_lines(args.decision)}

## Risks, blockers, and uncertainty

{bullet_lines(args.risk)}

## Evidence

{bullet_lines(args.evidence)}

## Next actions

{bullet_lines(args.next_action)}

## Intended Atlas routing

{bullet_lines(args.atlas_target)}
"""


def _resolve_settings(args: argparse.Namespace) -> dict[str, object]:
    """Apply CLI > environment > config file > default to every setting."""
    config, _ = atlas_config.load_config(args.config)
    vault = atlas_config.resolve(args.vault, "ATLAS_VAULT", config, "atlas", "vault")
    spool = atlas_config.resolve(args.spool, "ATLAS_SPOOL", config, "atlas", "spool")
    settings: dict[str, object] = {
        "vault": Path(vault).expanduser() if vault else None,
        "spool": Path(spool).expanduser() if spool else None,
        "project_id": atlas_config.resolve(
            args.project_id, "ATLAS_PROJECT_ID", config, "atlas", "project_id"
        ),
        "project_slug": atlas_config.resolve(
            args.project_slug, "ATLAS_PROJECT_SLUG", config, "atlas", "project_slug"
        ),
        "agent": atlas_config.resolve(
            args.agent, ("ATLAS_AGENT", "ATLAS_AGENT_ID"), config, "agent", "id"
        ),
        "session_id": atlas_config.resolve(
            args.session_id, "ATLAS_SESSION_ID", config, "agent", "session_id", "unknown"
        ),
        "work_package": atlas_config.resolve(
            args.work_package, "ATLAS_WORK_PACKAGE", config, "agent", "work_package", "unknown"
        ),
        "repository": atlas_config.resolve(
            args.repository, "ATLAS_REPOSITORY", config, "agent", "repository", "unknown"
        ),
        "branch": atlas_config.resolve(
            args.branch, "ATLAS_BRANCH", config, "agent", "branch", "unknown"
        ),
        "commit": atlas_config.resolve(args.commit, "ATLAS_COMMIT", config, "agent", "commit", "unknown"),
    }
    return settings


def main(argv: Sequence[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        settings = _resolve_settings(args)
    except atlas_config.ConfigError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    # The vault is the preferred destination; the spool is the fallback.
    if args.vault is not None or args.spool is not None:
        root_path = settings["vault"] if args.vault is not None else settings["spool"]
    else:
        root_path = settings["vault"] or settings["spool"]
    use_vault = root_path is not None and root_path == settings["vault"]

    missing = [
        name
        for name in ("project_id", "project_slug", "agent")
        if not settings[name]
    ]
    if root_path is None:
        missing.append("vault or spool")
    if missing:
        print(
            "ERROR: missing required setting(s): "
            + ", ".join(missing)
            + " (use CLI arguments, ATLAS_* environment variables, or a config file)",
            file=sys.stderr,
        )
        return 2
    root_path = str(root_path)

    project_slug = str(settings["project_slug"])
    if not SAFE_SLUG.fullmatch(project_slug):
        print("ERROR: --project-slug must be lowercase kebab-case", file=sys.stderr)
        return 2
    if args.event_id and not SAFE_ID.fullmatch(args.event_id):
        print("ERROR: unsafe --event-id", file=sys.stderr)
        return 2

    args.project_id = settings["project_id"]
    args.project_slug = project_slug
    args.agent = settings["agent"]
    args.session_id = settings["session_id"]
    args.work_package = settings["work_package"]
    args.repository = settings["repository"]
    args.branch = settings["branch"]
    args.commit = settings["commit"]

    try:
        occurred = parse_time(args.occurred_at)
        captured = utc_now()
        event_id = args.event_id or build_event_id(occurred, project_slug, args.summary)

        if use_vault:
            root = Path(root_path).expanduser().resolve()
            relative = (
                Path("sources")
                / "agent-events"
                / occurred.strftime("%Y")
                / occurred.strftime("%m")
                / occurred.strftime("%d")
            )
            sync_state = "captured"
        else:
            root = Path(root_path).expanduser().resolve()
            relative = Path(".atlas-spool")
            sync_state = "pending"

        output = root / relative / f"{event_id}.md"
        ensure_descendant(root, output)
        content = render(args, event_id, occurred, captured, sync_state)
        atomic_write_new(output, content)

        payload = {
            "ok": True,
            "event_id": event_id,
            "path": str(output),
            "sync_state": sync_state,
            "normalization_state": "pending",
            "bytes": len(content.encode()),
        }
        print(
            json.dumps(payload, ensure_ascii=False)
            if args.json_output
            else f"Captured {event_id}: {output}"
        )
        return 0
    except (OSError, ValueError) as exc:
        message = redact(str(exc))
        if args.json_output:
            print(json.dumps({"ok": False, "error": message}))
        else:
            print(f"ERROR: {message}", file=sys.stderr)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
