"""AS-OBSIDIAN-CAPTURE-001 — capture service and raw evidence repository.

Single convergence boundary for every capture entry point (CLI today, a
localhost API or browser extension later): CLI/API/extension adapters build a
:class:`~project_atlas.capture_sources.CaptureRequest` and call
:func:`capture`. Nothing above this boundary owns persistence, identity, or
deduplication (architecture §6.3, §53).

Ordering is preserve-first (architecture §68): raw evidence is written and
schema-validated before any projection is attempted, so a failure in
rendering can never destroy accepted evidence (INV-001, INV-007).

Boundary against the existing conversational plane
--------------------------------------------------
:mod:`project_atlas.conversation_capture` (D-042 / CAPTURE-002) deliberately
refuses raw transcripts: structured ``atlas.conversation-capture.v1``
envelopes may carry only human-structured items, and that prohibition is
**not** relaxed here. This module owns a separate, explicitly quarantined
*evidence* plane. Raw captures are never promoted into the Knowledge Inbox
or the Truth Core; turning captured evidence into structured knowledge stays
an explicit human step through ``atlas capture conversation``.

CAPTURE != AUTHORITY. PROJECTION != SOURCE. INBOX != AUTHORITY.
"""

from __future__ import annotations

import hashlib
import json
import os
import unicodedata
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from atlas_contracts.identity import (
    ensure_under_root,
    safe_relative_component,
    safe_relative_path,
)
from project_atlas.capture_sources import CaptureRequest
from project_atlas.logging import get_logger
from project_atlas.obsidian_capture_note import ObsidianNoteError, write_note
from project_atlas.schema import SchemaValidationError, validate_record
from project_atlas.secrets import redact_text, scan_text

_log = get_logger("obsidian_capture")

PACKAGE_ID = "AS-OBSIDIAN-CAPTURE-001"
GENERATOR_ID = "atlas-obsidian-capture-001"
SCHEMA_NAME = "atlas.raw-capture.v1"
SCHEMA_KIND = "raw-capture"
CAPTURE_DIR = Path("generated") / "ops" / "raw-captures"
DEFAULT_OBSIDIAN_DIR = Path("generated") / "obsidian" / "captures"
TRUTH_BOUNDARY = "CAPTURE != AUTHORITY / PROJECTION != SOURCE / RAW != TRUTH CORE"

CLASSIFICATIONS = ("conversation", "decision", "research", "directive", "note")

#: Deterministic ``source_type`` -> classification map (architecture §10.1).
#: No model, no heuristic scoring: same input, same classification.
_CLASSIFICATION_BY_SOURCE_TYPE = {
    "conversation": "conversation",
    "agent_output": "conversation",
    "web": "research",
    "document": "research",
    "email": "research",
    "terminal": "note",
    "text": "note",
}

#: Per-classification subfolder inside a project (architecture §14).
_PROJECT_SUBFOLDER = {
    "conversation": "Conversations",
    "decision": "Decisions",
    "research": "Research",
    "directive": "Directives",
    "note": "Notes",
}

MAX_TITLE_CHARS = 120


class CaptureError(ValueError):
    """Fail-closed capture error carrying a stable code."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


@dataclass(frozen=True)
class RoutingPolicy:
    """Logical destinations for the Obsidian projection (architecture §14/§15).

    Every value is a vault-relative path resolved under the Obsidian root
    with per-segment containment checks; a traversal-shaped value fails
    closed rather than escaping.
    """

    inbox: str = "00 Inbox/Atlas Captures"
    projects: str = "10 Projects"
    decisions: str = "20 Decisions"
    research: str = "30 Research"
    directives: str = "40 Directives"

    def validate(self) -> None:
        for label, value in (
            ("inbox", self.inbox),
            ("projects", self.projects),
            ("decisions", self.decisions),
            ("research", self.research),
            ("directives", self.directives),
        ):
            # ``safe_relative_path`` on the whole value, never a manual split:
            # splitting on "/" would quietly turn "/etc" into a relative "etc"
            # instead of rejecting an absolute destination.
            try:
                safe_relative_path(str(value), label=f"routing.{label}")
            except ValueError as exc:
                raise CaptureError("ROUTING_UNSAFE", str(exc)) from exc


def _write_atomic(path: Path, content: bytes, *, root: Path) -> None:
    try:
        ensure_under_root(root, path.parent, label="capture store")
    except ValueError as exc:
        raise CaptureError("PATH_ESCAPES_VAULT", str(exc)) from exc
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        ensure_under_root(root, path.parent, label="capture store")
    except ValueError as exc:
        raise CaptureError("PATH_ESCAPES_VAULT", str(exc)) from exc
    # A per-writer temp name, not a shared ``<name>.tmp``: two concurrent
    # writers of the same content-addressed path would otherwise race on one
    # temp file and the loser's ``os.replace`` would fail with ENOENT
    # (architecture §49). ``os.replace`` itself is atomic, so identical
    # concurrent captures converge instead of colliding.
    tmp = path.with_suffix(f"{path.suffix}.{os.getpid()}-{uuid.uuid4().hex}.tmp")
    try:
        tmp.write_bytes(content)
        os.replace(tmp, path)
    finally:
        if tmp.exists():
            tmp.unlink(missing_ok=True)


def canonical_content(content: str) -> str:
    """Canonical representation used **only** for identity (architecture §7.3).

    Conservative by design: Unicode NFC plus line-ending normalization to
    ``\\n``. No whitespace stripping, no case folding, no blank-line
    collapsing — a capture that differs only in transport line endings is the
    same content; a capture that differs in indentation is not.

    The stored raw evidence is the untouched original; this function never
    changes what is persisted.
    """
    normalized = content.replace("\r\n", "\n").replace("\r", "\n")
    return unicodedata.normalize("NFC", normalized)


def content_hash(content: str) -> str:
    """Deterministic content identity over the canonical representation."""
    digest = hashlib.sha256(canonical_content(content).encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def identity_hash(
    *,
    content: str,
    project_id: str | None,
    source_type: str,
    source_application: str,
) -> str:
    """Logical-capture identity (architecture §7, §8).

    Distinct from :func:`content_hash`: the same text captured into two
    projects, or from two applications, is two logical captures. Keeping the
    two hashes separate is what lets the dedupe scope widen later without a
    schema migration.
    """
    canonical = {
        "schema": SCHEMA_NAME,
        "schema_version": 1,
        "project_id": project_id,
        "source_type": source_type,
        "source_application": source_application,
        "content_hash": content_hash(content),
    }
    digest = hashlib.sha256(
        json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return f"sha256:{digest}"


def capture_id_for(identity: str) -> str:
    """Content-addressed capture id.

    Deriving the id from the identity hash makes the filesystem itself the
    dedupe index: the lookup is an O(1) ``is_file()`` on a deterministic
    path, and two concurrent identical captures resolve to the same path with
    identical bytes, so the duplicate race in architecture §49 cannot occur
    and no lock or mutable index is needed.
    """
    return "rcap-" + hashlib.sha256(identity.encode("utf-8")).hexdigest()[:16]


def _existing_project_ids(vault: Path) -> list[str]:
    root = vault / "projects"
    if not root.is_dir():
        return []
    return sorted(
        path.name
        for path in root.iterdir()
        if path.is_dir() and not path.name.startswith(".")
    )


def resolve_project(vault: Path, requested: str | None) -> str | None:
    """Resolve an explicit project reference against governed vault identity.

    An explicit-but-unknown project fails closed (Atlas never invents project
    attribution). An *omitted* project is not guessed either: the capture is
    routed to the Inbox with ``project_id = None`` so content is never
    discarded for want of routing (architecture §15).
    """
    token = (requested or "").strip()
    if not token:
        return None
    try:
        project_id = safe_relative_component(token, label="project id")
    except ValueError as exc:
        raise CaptureError("PATH_SHAPED_PROJECT_ID", str(exc)) from exc
    existing = _existing_project_ids(vault)
    if project_id not in existing:
        known = ", ".join(existing) if existing else "none"
        raise CaptureError(
            "UNMATCHED_PROJECT",
            f"project {project_id!r} is not an existing governed identity (known: {known})",
        )
    return project_id


def classify(request: CaptureRequest, *, explicit: str | None = None) -> str:
    """Deterministic classification (architecture §10.1). No model involved."""
    if explicit:
        token = str(explicit).strip().lower()
        if token not in CLASSIFICATIONS:
            raise CaptureError(
                "UNSUPPORTED_CLASSIFICATION",
                f"unsupported classification {token!r}; "
                f"allowed: {', '.join(CLASSIFICATIONS)}",
            )
        return token
    return _CLASSIFICATION_BY_SOURCE_TYPE.get(request.source_type, "note")


def route(
    *,
    project_id: str | None,
    classification: str,
    policy: RoutingPolicy,
) -> dict[str, Any]:
    """Resolve a logical destination. Routing never discards content (§15).

    Priority is explicit project identity, then deterministic classification,
    then the Inbox fallback.
    """
    policy.validate()
    if project_id:
        subfolder = _PROJECT_SUBFOLDER[classification]
        return {
            "destination": f"{policy.projects}/{project_id}/{subfolder}",
            "reason": "explicit-project",
            "fallback": False,
        }
    by_classification = {
        "decision": policy.decisions,
        "research": policy.research,
        "directive": policy.directives,
    }
    destination = by_classification.get(classification)
    if destination is not None:
        return {
            "destination": destination,
            "reason": "deterministic-classification",
            "fallback": False,
        }
    return {"destination": policy.inbox, "reason": "inbox-fallback", "fallback": True}


def derive_title(request: CaptureRequest, *, capture_id: str) -> str:
    """Safe deterministic title heuristic (architecture §10.1).

    The title is *derived metadata*, not preserved evidence: it is written
    into the capture record, the note frontmatter, and the note filename on
    disk. Secret-shaped material is therefore redacted out of it (NFR-004 /
    CODEX-SEC-006) while the raw evidence keeps the original bytes — the
    same preserve-raw / redact-derived split as the projection (§38).
    """

    def _finalize(candidate: str) -> str:
        safe = redact_text(candidate)[:MAX_TITLE_CHARS].strip()
        return safe or f"Atlas capture {capture_id}"

    if request.title_hint:
        hint = unicodedata.normalize("NFC", request.title_hint).strip()
        if hint:
            return _finalize(hint)
    for line in canonical_content(request.content).split("\n"):
        candidate = line.strip().lstrip("#").strip()
        if candidate:
            return _finalize(candidate)
    return f"Atlas capture {capture_id}"


def _resolve_vault(vault: Path) -> Path:
    resolved = vault.expanduser().resolve()
    if not resolved.is_dir():
        raise CaptureError("VAULT_NOT_FOUND", f"vault is not a directory: {resolved}")
    return resolved


def _resolve_obsidian_root(vault: Path, obsidian_root: Path | None) -> Path:
    """Default the projection inside the Atlas vault.

    Writing into an external Obsidian vault is real but must be an explicit
    operator decision, so the default target stays under ``--vault`` beside
    the existing ``generated/obsidian/projects`` projection.
    """
    if obsidian_root is None:
        root = vault / DEFAULT_OBSIDIAN_DIR
        root.mkdir(parents=True, exist_ok=True)
        return root
    root = obsidian_root.expanduser().resolve()
    if not root.is_dir():
        raise CaptureError(
            "OBSIDIAN_CONFIGURATION_ERROR",
            f"configured obsidian vault is not a directory: {root}",
        )
    return root


def _record_path(vault: Path, capture_id: str) -> Path:
    return vault / CAPTURE_DIR / f"{capture_id}.json"


def _content_path(vault: Path, capture_id: str) -> Path:
    return vault / CAPTURE_DIR / f"{capture_id}.txt"


def _load_record(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise CaptureError("CAPTURE_UNREADABLE", f"capture record is unreadable: {exc}") from exc
    if not isinstance(payload, dict):
        raise CaptureError("CAPTURE_UNREADABLE", "capture record is not an object")
    return payload


def _persist_record(vault: Path, record: dict[str, Any]) -> None:
    try:
        validate_record(record, SCHEMA_KIND)
    except SchemaValidationError as exc:
        raise CaptureError("MALFORMED_SCHEMA", f"raw-capture schema invalid: {exc}") from exc
    _write_atomic(
        _record_path(vault, record["capture_id"]),
        (json.dumps(record, indent=2, sort_keys=True) + "\n").encode("utf-8"),
        root=vault,
    )


def _write_latest(vault: Path, record: dict[str, Any]) -> None:
    payload = {
        "schema_version": 1,
        "capture_id": record["capture_id"],
        "project_id": record["project_id"],
        "path": f"{CAPTURE_DIR.as_posix()}/{record['capture_id']}.json",
        "generated": {"by": GENERATOR_ID},
    }
    _write_atomic(
        vault / CAPTURE_DIR / "latest.json",
        (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8"),
        root=vault,
    )


def _result(
    record: dict[str, Any],
    *,
    status: str,
    duplicate: bool,
    errors: list[dict[str, str]] | None = None,
    warnings: list[str] | None = None,
) -> dict[str, Any]:
    """Machine result contract (architecture §51) shared by CLI and API."""
    return {
        "schema_version": 1,
        "package": PACKAGE_ID,
        "status": status,
        "capture_id": record["capture_id"],
        "duplicate": duplicate,
        "existing_capture_id": record["capture_id"] if duplicate else None,
        "lifecycle_state": record["lifecycle_state"],
        "content_hash": record["content_hash"],
        "identity_hash": record["identity_hash"],
        "project_id": record["project_id"],
        "classification": record["classification"],
        "title": record["title"],
        "raw_path": record["content_path"],
        "record_path": f"{CAPTURE_DIR.as_posix()}/{record['capture_id']}.json",
        "outputs": list(record.get("derived_artifacts") or []),
        "errors": list(errors or []),
        "warnings": list(warnings or []),
        "secret_findings": list(record["secret_scan"]["findings"]),
        "truth_boundary": TRUTH_BOUNDARY,
        "generated": {"by": GENERATOR_ID},
    }


def _render_stage(
    vault: Path,
    record: dict[str, Any],
    *,
    content: str,
    obsidian_root: Path | None,
    include_content: bool,
) -> tuple[dict[str, Any], list[dict[str, str]]]:
    """Attempt the projection. Failure is isolated, never fatal (INV-007).

    The raw evidence is already durable when this runs; a rendering failure
    is recorded on the capture so ``atlas capture retry`` can resume it.
    """
    try:
        root = _resolve_obsidian_root(vault, obsidian_root)
        artifact = write_note(
            record,
            content=content,
            obsidian_root=root,
            include_content=include_content,
        )
    except (CaptureError, ObsidianNoteError, OSError, ValueError) as exc:
        code = getattr(exc, "code", "OBSIDIAN_WRITE_FAILED")
        failure = {
            "stage": "render",
            "code": str(code)[:64],
            "message": str(exc)[:512],
        }
        updated = dict(record)
        updated["lifecycle_state"] = "persisted"
        updated["stage_failures"] = [
            item for item in record.get("stage_failures") or [] if item.get("stage") != "render"
        ] + [failure]
        _persist_record(vault, updated)
        _log.warning(
            "obsidian projection failed; raw capture preserved",
            extra={"context": {"capture_id": record["capture_id"], "code": failure["code"]}},
        )
        return updated, [failure]

    updated = dict(record)
    updated["lifecycle_state"] = "rendered"
    updated["stage_failures"] = [
        item for item in record.get("stage_failures") or [] if item.get("stage") != "render"
    ]
    updated["derived_artifacts"] = [
        item
        for item in record.get("derived_artifacts") or []
        if item.get("artifact_id") != artifact["artifact_id"]
    ] + [artifact]
    _persist_record(vault, updated)
    return updated, []


def capture(
    vault: Path,
    request: CaptureRequest,
    *,
    classification: str | None = None,
    routing: RoutingPolicy | None = None,
    obsidian_root: Path | None = None,
    render: bool = True,
    include_content: bool = True,
) -> dict[str, Any]:
    """Accept a capture: validate, identify, deduplicate, persist, project.

    Returns the machine result contract of architecture §51. Raw persistence
    is the only mandatory stage; every later stage is best-effort and its
    failure is reported without discarding evidence.
    """
    resolved_vault = _resolve_vault(vault)
    if not isinstance(request, CaptureRequest):
        raise CaptureError("MALFORMED_REQUEST", "request must be a CaptureRequest")
    policy = routing or RoutingPolicy()
    policy.validate()

    project_id = resolve_project(resolved_vault, request.project_reference)
    kind = classify(request, explicit=classification)
    identity = identity_hash(
        content=request.content,
        project_id=project_id,
        source_type=request.source_type,
        source_application=request.source_application,
    )
    capture_id = capture_id_for(identity)

    record_path = _record_path(resolved_vault, capture_id)
    if record_path.is_file():
        # Deduplication (architecture §8): the deterministic path *is* the
        # index. No new note is produced (INV-006).
        existing = _load_record(record_path)
        if existing.get("identity_hash") != identity:
            raise CaptureError(
                "CAPTURE_ID_COLLISION",
                "existing capture id does not match this payload",
            )
        _log.info(
            "duplicate capture ignored",
            extra={"context": {"capture_id": capture_id, "project_id": project_id}},
        )
        return _result(existing, status="duplicate", duplicate=True)

    title = derive_title(request, capture_id=capture_id)
    findings = sorted({item.pattern for item in scan_text(request.content)})
    content_rel = f"{CAPTURE_DIR.as_posix()}/{capture_id}.txt"

    record: dict[str, Any] = {
        "schema_version": 1,
        "schema": SCHEMA_NAME,
        "package": PACKAGE_ID,
        "capture_id": capture_id,
        "project_id": project_id,
        "source_type": request.source_type,
        "source_application": request.source_application,
        "source_adapter": request.source_adapter,
        "source_locator": request.source_locator,
        "source_metadata": dict(sorted(request.source_metadata.items())),
        # Never machine-generated: a wall-clock value here would break
        # NFR-001 determinism. Preserved verbatim when a caller supplies it.
        "captured_at": request.captured_at,
        "captured_at_source": (
            "operator-supplied" if request.captured_at else "not-provided"
        ),
        "content_hash": content_hash(request.content),
        "identity_hash": identity,
        "canonicalization": {
            "unicode": "NFC",
            "line_endings": "lf",
            "whitespace_stripped": False,
        },
        "content_bytes": len(request.content.encode("utf-8")),
        "content_path": content_rel,
        "title": title,
        "classification": kind,
        "routing": route(project_id=project_id, classification=kind, policy=policy),
        "secret_scan": {"findings": findings, "projection_redacted": bool(findings)},
        "lifecycle_state": "persisted",
        "stage_failures": [],
        "derived_artifacts": [],
        "provenance": {
            "capture_id": capture_id,
            "content_hash": content_hash(request.content),
            "raw_content_persisted": True,
            "extraction_method": "verbatim_raw_capture",
            "derived_from": f"{request.source_adapter}:{request.source_application}",
        },
        "authority": {
            "level": "quarantined-evidence",
            "classification": "NON_CANONICAL",
            "note": TRUTH_BOUNDARY,
        },
        "honesty": {
            "authentic_pilot": False,
            "lens_is_authority": False,
            "invented_facts": False,
            "capture_is_authority": False,
            "projection_is_canonical": False,
            "external_transmission": False,
        },
        "truth_boundary": TRUTH_BOUNDARY,
        "generated": {"by": GENERATOR_ID},
    }

    # PRESERVE FIRST (architecture §68): the verbatim payload and its
    # schema-valid record are durable before any projection is attempted.
    _write_atomic(
        _content_path(resolved_vault, capture_id),
        request.content.encode("utf-8"),
        root=resolved_vault,
    )
    _persist_record(resolved_vault, record)
    _write_latest(resolved_vault, record)
    _log.info(
        "capture persisted",
        extra={
            "context": {
                "capture_id": capture_id,
                "bytes": record["content_bytes"],
                "source": request.source_application,
                "secret_findings": len(findings),
            }
        },
    )

    warnings: list[str] = []
    if findings:
        warnings.append(
            "secret-shaped content detected; raw evidence preserved, projection redacted"
        )
    if not render:
        return _result(record, status="ok", duplicate=False, warnings=warnings)

    record, errors = _render_stage(
        resolved_vault,
        record,
        content=request.content,
        obsidian_root=obsidian_root,
        include_content=include_content,
    )
    status = "partial" if errors else "ok"
    return _result(record, status=status, duplicate=False, errors=errors, warnings=warnings)


def read_raw_content(vault: Path, capture_id: str) -> str:
    """Return the verbatim persisted evidence for a capture (INV-001)."""
    resolved_vault = _resolve_vault(vault)
    cid = _safe_capture_id(capture_id)
    path = _content_path(resolved_vault, cid)
    if path.is_symlink() or not path.is_file():
        raise CaptureError("UNMATCHED_CAPTURE", f"raw content for {cid} does not exist")
    try:
        # Bytes, not ``read_text``: text mode applies universal-newline
        # translation and would silently rewrite CRLF evidence, breaking
        # INV-001 and the retry content-hash check.
        return path.read_bytes().decode("utf-8")
    except (OSError, UnicodeError) as exc:
        raise CaptureError("CAPTURE_UNREADABLE", f"raw content unreadable: {exc}") from exc


def _safe_capture_id(capture_id: str) -> str:
    token = str(capture_id or "").strip().lower()
    if not token.startswith("rcap-") or len(token) != 21:
        raise CaptureError("MALFORMED_CAPTURE_ID", f"capture id is invalid: {capture_id!r}")
    try:
        return safe_relative_component(token, label="capture id")
    except ValueError as exc:
        raise CaptureError("MALFORMED_CAPTURE_ID", str(exc)) from exc


def retry(
    vault: Path,
    capture_id: str,
    *,
    obsidian_root: Path | None = None,
    include_content: bool = True,
) -> dict[str, Any]:
    """Resume a capture whose projection failed (architecture §20).

    The raw evidence is reloaded from the store, so a retry never depends on
    the original source still being available.
    """
    resolved_vault = _resolve_vault(vault)
    cid = _safe_capture_id(capture_id)
    path = _record_path(resolved_vault, cid)
    if path.is_symlink() or not path.is_file():
        raise CaptureError("UNMATCHED_CAPTURE", f"capture {cid} does not exist")
    record = _load_record(path)
    content = read_raw_content(resolved_vault, cid)
    if content_hash(content) != record.get("content_hash"):
        raise CaptureError(
            "CONTENT_HASH_MISMATCH",
            f"stored evidence for {cid} does not match its recorded content hash",
        )
    record, errors = _render_stage(
        resolved_vault,
        record,
        content=content,
        obsidian_root=obsidian_root,
        include_content=include_content,
    )
    return _result(
        record,
        status="partial" if errors else "ok",
        duplicate=False,
        errors=errors,
    )


def list_captures(
    vault: Path,
    *,
    project_id: str | None = None,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """List raw captures in deterministic reverse ``capture_id`` order.

    Ordering is lexicographic on content-addressed ids, matching the existing
    session/conversation capture lenses — never wall-clock recency.
    """
    resolved_vault = _resolve_vault(vault)
    if limit < 1:
        raise CaptureError("MALFORMED_INPUT", "limit must be >= 1")
    token: str | None = None
    if project_id is not None:
        try:
            token = safe_relative_component(project_id, label="project id")
        except ValueError as exc:
            raise CaptureError("PATH_SHAPED_PROJECT_ID", str(exc)) from exc
    root = resolved_vault / CAPTURE_DIR
    if not root.is_dir():
        return []
    rows: list[dict[str, Any]] = []
    for path in sorted(root.glob("rcap-*.json"), reverse=True):
        if path.is_symlink() or not path.is_file():
            continue
        try:
            payload = _load_record(path)
        except CaptureError:
            continue
        if token is not None and payload.get("project_id") != token:
            continue
        rows.append(
            {
                "capture_id": payload.get("capture_id"),
                "project_id": payload.get("project_id"),
                "source_type": payload.get("source_type"),
                "source_application": payload.get("source_application"),
                "classification": payload.get("classification"),
                "title": payload.get("title"),
                "content_hash": payload.get("content_hash"),
                "content_bytes": payload.get("content_bytes"),
                "lifecycle_state": payload.get("lifecycle_state"),
                "stage_failures": payload.get("stage_failures") or [],
                "notes": [
                    item.get("relative_path")
                    for item in payload.get("derived_artifacts") or []
                ],
                "path": path.relative_to(resolved_vault).as_posix(),
                "authority": False,
                "status": "quarantined-evidence",
            }
        )
        if len(rows) >= limit:
            break
    return rows


__all__ = [
    "CAPTURE_DIR",
    "DEFAULT_OBSIDIAN_DIR",
    "GENERATOR_ID",
    "PACKAGE_ID",
    "SCHEMA_NAME",
    "TRUTH_BOUNDARY",
    "CaptureError",
    "RoutingPolicy",
    "canonical_content",
    "capture",
    "capture_id_for",
    "classify",
    "content_hash",
    "derive_title",
    "identity_hash",
    "list_captures",
    "read_raw_content",
    "resolve_project",
    "retry",
    "route",
]
