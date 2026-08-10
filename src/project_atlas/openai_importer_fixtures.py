"""AS-2.0-OAI-IMPORT-001 — OpenAI importer fixture harness (no live API).

Parses synthetic chat-export fixtures under docs/atlas-2.0/fixtures/openai-importer
into a structured fixture receipt and optionally feeds text into the existing
AS-2.0-PROV-001 quarantine helper (consume-only; this package does not own PROV).
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from project_atlas.compat_anchor import (
    SNAPSHOT_ID,
    CompatibilityAnchor,
    require_compatibility_anchor,
)
from project_atlas.provider_adapters import quarantine_provider_output
from project_atlas.schema import SchemaValidationError, validate_record
from project_atlas.secrets import scan_text

PACKAGE_ID = "AS-2.0-OAI-IMPORT-001"
_ID_RE = re.compile(r"^[a-z][a-z0-9-]{0,63}$")
_ENV_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_TURN_RE = re.compile(
    r"^(User|Assistant)\s*:\s*(.+)$",
    re.IGNORECASE | re.MULTILINE,
)
_FENCE_RE = re.compile(r"```(?:text)?\s*\n(.*?)```", re.DOTALL | re.IGNORECASE)

DEFAULT_SAMPLE_REL = Path("docs") / "atlas-2.0" / "fixtures" / "openai-importer" / (
    "sample-chat-export.md"
)


class OpenAIImportFixtureError(ValueError):
    """Fail-closed OpenAI importer fixture error."""


@dataclass(frozen=True, slots=True)
class ChatTurn:
    role: Literal["user", "assistant"]
    text: str

    def as_dict(self) -> dict[str, Any]:
        return {"role": self.role, "text": self.text}


def _validate_id(token: str, *, label: str) -> str:
    value = token.strip()
    if not _ID_RE.fullmatch(value):
        raise OpenAIImportFixtureError(f"oai-import-{label}-invalid")
    return value


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    tmp.replace(path)


def default_sample_path(*, repo_root: Path | None = None) -> Path:
    """Resolve the shipped synthetic sample-chat-export.md path."""
    root = repo_root or Path(__file__).resolve().parents[2]
    return root / DEFAULT_SAMPLE_REL


def parse_chat_export(text: str) -> list[ChatTurn]:
    """Parse User/Assistant turns from a synthetic chat-export fixture."""
    body = text
    fence = _FENCE_RE.search(text)
    if fence:
        body = fence.group(1)
    turns: list[ChatTurn] = []
    for match in _TURN_RE.finditer(body):
        role_raw = match.group(1).lower()
        role: Literal["user", "assistant"] = (
            "user" if role_raw == "user" else "assistant"
        )
        content = match.group(2).strip()
        if not content:
            raise OpenAIImportFixtureError("oai-import-turn-empty")
        turns.append(ChatTurn(role=role, text=content))
    if not turns:
        raise OpenAIImportFixtureError("oai-import-turns-empty")
    return turns


def parse_chat_export_file(path: Path) -> list[ChatTurn]:
    """Load and parse a synthetic chat-export markdown fixture."""
    if not path.is_file():
        raise OpenAIImportFixtureError(f"oai-import-sample-missing:{path}")
    return parse_chat_export(path.read_text(encoding="utf-8"))


def build_openai_import_fixture_receipt(
    vault: Path,
    *,
    receipt_id: str,
    sample_path: Path | None = None,
    adapter_id: str = "openai-fixture",
    quarantine: bool = True,
    adapters_enabled: bool = True,
    anchor: CompatibilityAnchor | None = None,
) -> dict[str, Any]:
    """Parse sample → structured fixture receipt (+ optional PROV quarantine).

    Never calls a live OpenAI API. Quarantine uses AS-2.0-PROV-001 helpers only.
    """
    _ = anchor or require_compatibility_anchor()
    rid = receipt_id.strip()
    if not _ENV_RE.fullmatch(rid):
        raise OpenAIImportFixtureError("oai-import-receipt-id-invalid")
    aid = _validate_id(adapter_id, label="adapter-id")

    sample = sample_path or default_sample_path()
    turns = parse_chat_export_file(sample)
    payload_text = "\n".join(f"{turn.role}: {turn.text}" for turn in turns)
    digest = hashlib.sha256(payload_text.encode("utf-8")).hexdigest()

    findings = scan_text(payload_text)
    findings_count = len(findings)
    finding_kinds = sorted({item.pattern for item in findings})

    quarantine_envelope: dict[str, Any] | None = None
    if quarantine:
        # Consume AS-2.0-PROV-001 quarantine only — do not dual-own PROV surfaces.
        envelope = quarantine_provider_output(
            vault,
            envelope_id=f"oai-import-{rid}",
            adapter_id=aid,
            payload_text=payload_text,
            payload_kind="text",
            adapters_enabled=adapters_enabled,
            anchor=anchor,
        )
        quarantine_envelope = {
            "envelope_id": envelope["envelope_id"],
            "status": envelope["status"],
            "package_id": envelope["package_id"],
        }

    status: Literal[
        "parsed-quarantined",
        "parsed-rejected-secret",
        "parsed-only",
    ]
    if findings_count or (
        quarantine_envelope is not None
        and quarantine_envelope["status"] == "rejected-secret"
    ):
        status = "parsed-rejected-secret"
    elif (
        quarantine_envelope is not None
        and quarantine_envelope["status"] == "quarantined"
    ):
        status = "parsed-quarantined"
    else:
        status = "parsed-only"

    receipt: dict[str, Any] = {
        "schema_version": 1,
        "package_id": PACKAGE_ID,
        "compat_snapshot_id": SNAPSHOT_ID,
        "receipt_id": rid,
        "adapter_id": aid,
        "status": status,
        "live_api": False,
        "sample_path": str(sample.as_posix()),
        "turn_count": len(turns),
        "turns": [turn.as_dict() for turn in turns],
        "payload_sha256": digest,
        "secret_scan": {
            "findings_count": findings_count,
            "content_redacted": True,
            "finding_kinds": finding_kinds,
        },
        "authority": {
            "level": "derived",
            "note": (
                "OpenAI importer fixture receipt only; no live API; "
                "never Layer B authority"
            ),
        },
        "truth_boundary": "OAI IMPORT FIXTURE ≠ LIVE API / ≠ AUTHORITY / ≠ PILOT",
        "generated": {"by": "project-atlas"},
    }
    if quarantine_envelope is not None:
        receipt["quarantine_envelope"] = quarantine_envelope

    try:
        validate_record(receipt, "openai-import-fixture-receipt")
    except SchemaValidationError as exc:
        raise OpenAIImportFixtureError(f"oai-import-schema:{exc}") from exc

    out = (
        vault.resolve()
        / "generated"
        / "ops"
        / "openai-import-fixtures"
        / f"{rid}.json"
    )
    _atomic_write_json(out, receipt)
    return receipt
