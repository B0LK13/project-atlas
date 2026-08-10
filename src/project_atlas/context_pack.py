"""AS-2.0-CTX-001 — fixture-safe context assembly packs.

Context packs carry provenance pointers and never invent estate/PILOT facts.
Bound to the Atlas 1.0 compatibility anchor (AS-2.0-COMPAT-001).
"""

from __future__ import annotations

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
from project_atlas.schema import SchemaValidationError, validate_record

PACKAGE_ID = "AS-2.0-CTX-001"
TRUTH_BOUNDARY = "CONTEXT PACK ≠ ESTATE FACTS / ≠ PILOT"
_ID_RE = re.compile(r"^[a-z][a-z0-9-]{0,63}$")
_REF_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,255}$")

ProvenanceKind = Literal["source", "receipt", "index", "claim", "concept", "other"]


class ContextPackError(ValueError):
    """Fail-closed context-pack contract error."""


@dataclass(frozen=True, slots=True)
class ProvenancePointer:
    ref: str
    kind: ProvenanceKind

    def as_dict(self) -> dict[str, str]:
        return {"ref": self.ref, "kind": self.kind}


@dataclass(frozen=True, slots=True)
class ContextEntry:
    entry_id: str
    ref: str
    label: str | None = None

    def as_dict(self) -> dict[str, str]:
        payload: dict[str, str] = {"entry_id": self.entry_id, "ref": self.ref}
        if self.label:
            payload["label"] = self.label
        return payload


def _validate_id(token: str, *, label: str) -> str:
    value = token.strip()
    if not _ID_RE.fullmatch(value):
        raise ContextPackError(f"context-{label}-invalid")
    return value


def _validate_ref(token: str, *, label: str) -> str:
    value = token.strip()
    if not value or not _REF_RE.fullmatch(value):
        raise ContextPackError(f"context-{label}-invalid")
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


def build_context_pack(
    *,
    pack_id: str,
    provenance_pointers: list[ProvenancePointer],
    output_vault: Path,
    entries: list[ContextEntry] | None = None,
    notes: str | None = None,
    invent_estate_facts: bool = False,
    anchor: CompatibilityAnchor | None = None,
) -> dict[str, Any]:
    """Build a fixture-safe context pack with mandatory provenance pointers."""
    _ = anchor or require_compatibility_anchor()
    pid = _validate_id(pack_id, label="pack-id")

    if invent_estate_facts:
        raise ContextPackError("context-estate-facts-invent-forbidden")
    if not provenance_pointers:
        raise ContextPackError("context-provenance-pointers-empty")

    pointers: list[dict[str, str]] = []
    seen_refs: set[str] = set()
    for pointer in provenance_pointers:
        ref = _validate_ref(pointer.ref, label="provenance-ref")
        if ref in seen_refs:
            raise ContextPackError(f"context-provenance-ref-duplicate:{ref}")
        seen_refs.add(ref)
        pointers.append(ProvenancePointer(ref=ref, kind=pointer.kind).as_dict())

    entry_payloads: list[dict[str, str]] = []
    seen_entries: set[str] = set()
    for entry in entries or []:
        eid = _validate_id(entry.entry_id, label="entry-id")
        if eid in seen_entries:
            raise ContextPackError(f"context-entry-id-duplicate:{eid}")
        seen_entries.add(eid)
        ref = _validate_ref(entry.ref, label="entry-ref")
        label = entry.label.strip()[:120] if entry.label else None
        entry_payloads.append(
            ContextEntry(entry_id=eid, ref=ref, label=label).as_dict()
        )

    payload: dict[str, Any] = {
        "schema_version": 1,
        "package_id": PACKAGE_ID,
        "compat_snapshot_id": SNAPSHOT_ID,
        "pack_id": pid,
        "fixture_safe": True,
        "estate_facts_invented": False,
        "provenance_pointers": sorted(pointers, key=lambda item: item["ref"]),
        "authority": {
            "level": "derived",
            "note": "Context pack is fixture-safe; never invents estate facts",
        },
        "truth_boundary": TRUTH_BOUNDARY,
        "generated": {"by": "project-atlas"},
    }
    if entry_payloads:
        payload["entries"] = sorted(entry_payloads, key=lambda item: item["entry_id"])
    if notes:
        payload["notes"] = notes.strip()[:240]

    try:
        validate_record(payload, "context-pack")
    except SchemaValidationError as exc:
        raise ContextPackError(f"context-pack-schema:{exc}") from exc

    out = (
        output_vault.resolve()
        / "generated"
        / "context"
        / f"{pid}-context-pack.json"
    )
    _atomic_write_json(out, payload)
    return payload
