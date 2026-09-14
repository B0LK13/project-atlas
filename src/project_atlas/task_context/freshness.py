"""Source freshness diagnosis for stored packets.

A stored packet is a snapshot, not a guarantee the environment still matches.
No permanent background monitor — recheck is tied to prepare/handoff.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from project_atlas.task_context.adapters import contract_digest, load_contract
from project_atlas.task_context.models import (
    FreshnessKind,
    FreshnessStatus,
    TaskContextPacket,
    sha256_bytes,
)
from project_atlas.task_context.paths import resolve_source_file


def diagnose_freshness(
    packet: TaskContextPacket,
    *,
    workspace_root: Path,
    contract_path: Path | None = None,
) -> dict[str, Any]:
    """Compare packet bindings to the live workspace/contract."""
    findings: list[dict[str, Any]] = []
    status = FreshnessStatus.UNCHANGED

    if contract_path is not None and contract_path.is_file():
        live = load_contract(contract_path, prefer_live=False)
        live_digest = contract_digest(live)
        if live_digest != packet.contract.contract_digest:
            status = FreshnessStatus.MUST_REBUILD
            findings.append(
                {
                    "kind": "contract_changed",
                    "previous": packet.contract.contract_digest,
                    "current": live_digest,
                    "contract_id": live.contract_id,
                }
            )
        if live.contract_id != packet.contract.contract_id:
            status = FreshnessStatus.MUST_REBUILD
            findings.append(
                {
                    "kind": "contract_id_changed",
                    "previous": packet.contract.contract_id,
                    "current": live.contract_id,
                }
            )

    for frag in packet.fragments:
        if frag.source_identity is None or not frag.source_path:
            if frag.trust_layer.value == "retrieved" and frag.included:
                findings.append(
                    {
                        "kind": "unverifiable",
                        "fragment_id": frag.fragment_id,
                        "path": frag.source_path,
                    }
                )
                if status == FreshnessStatus.UNCHANGED:
                    status = FreshnessStatus.MISSING_OR_UNVERIFIABLE
            continue
        identity = frag.source_identity
        if identity.kind == FreshnessKind.UNKNOWN:
            findings.append(
                {
                    "kind": "unknown_freshness",
                    "fragment_id": frag.fragment_id,
                    "path": frag.source_path,
                }
            )
            if status == FreshnessStatus.UNCHANGED:
                status = FreshnessStatus.MISSING_OR_UNVERIFIABLE
            continue
        if identity.kind == FreshnessKind.CONTENT_DIGEST:
            try:
                path = resolve_source_file(workspace_root, frag.source_path)
                if not path.is_file():
                    raise FileNotFoundError(frag.source_path)
                live_digest = sha256_bytes(path.read_bytes())
            except (OSError, ValueError, FileNotFoundError):
                findings.append(
                    {
                        "kind": "missing_source",
                        "fragment_id": frag.fragment_id,
                        "path": frag.source_path,
                    }
                )
                status = FreshnessStatus.MISSING_OR_UNVERIFIABLE
                continue
            if live_digest != identity.identity:
                findings.append(
                    {
                        "kind": "source_changed",
                        "fragment_id": frag.fragment_id,
                        "path": frag.source_path,
                        "previous": identity.identity,
                        "current": live_digest,
                    }
                )
                status = FreshnessStatus.MUST_REBUILD

    return {
        "status": status.value,
        "packet_id": packet.packet_id,
        "content_digest": packet.content_digest,
        "findings": findings,
        "notes": [
            "PACKET_SNAPSHOT != LIVE_ENVIRONMENT",
            "recheck is for prepare/handoff; no background monitor",
        ],
    }


def git_head_identity(workspace_root: Path) -> str | None:
    """Best-effort git object identity; UNKNOWN when unavailable."""
    head = workspace_root / ".git" / "HEAD"
    if not head.is_file():
        return None
    try:
        text = head.read_text(encoding="utf-8").strip()
        if text.startswith("ref:"):
            ref = text.split(" ", 1)[1].strip()
            ref_path = workspace_root / ".git" / ref
            if ref_path.is_file():
                return ref_path.read_text(encoding="utf-8").strip()
        if len(text) >= 40:
            return text[:40]
    except OSError:
        return None
    return None
