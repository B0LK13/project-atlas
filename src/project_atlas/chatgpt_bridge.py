"""AS-2.1-CHATGPT-BRIDGE-001 - ChatGPT export bridge into quarantine.

Bridges an on-disk ChatGPT/OpenAI-compatible export into PROV quarantine
plus a reconstructable bridge receipt. LLM output != authority.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from project_atlas.authz import OperatorProfile, default_operator
from project_atlas.compat_anchor import SNAPSHOT_ID, require_compatibility_anchor
from project_atlas.openai_importer_fixtures import parse_chat_export
from project_atlas.provider_adapters import quarantine_provider_output
from project_atlas.secrets import scan_text

PACKAGE_ID = "AS-2.1-CHATGPT-BRIDGE-001"
TRUTH_BOUNDARY = "CHATGPT BRIDGE != LIVE CHATGPT API / != AUTHORITY / LLM!=AUTHORITY"
_ID_RE = re.compile(r"^[a-z][a-z0-9-]{0,63}$")
# D-INTEGRATE-007A §12: bound the on-disk export read so an oversized file
# cannot exhaust memory. Mirrors the sibling openai_import_real.py ceiling:
# check st_size before read_text and re-check the decoded UTF-8 length after,
# failing closed on oversize. Read-only, bounded, project-scoped.
MAX_EXPORT_BYTES = 2_000_000


class ChatgptBridgeError(ValueError):
    """Fail-closed ChatGPT bridge error."""


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    tmp.replace(path)


def bridge_chatgpt_export(
    vault: Path,
    export_path: Path,
    *,
    bridge_id: str,
    operator: OperatorProfile | None = None,
) -> dict[str, Any]:
    """Bridge a ChatGPT export file into quarantine + receipt."""
    require_compatibility_anchor()
    op = operator or default_operator()
    op.require("chatgpt.bridge")
    bid = bridge_id.strip()
    if not _ID_RE.fullmatch(bid):
        raise ChatgptBridgeError("chatgpt-bridge-id-invalid")
    src = export_path.resolve()
    if not src.is_file():
        raise ChatgptBridgeError("chatgpt-export-missing")
    size = src.stat().st_size
    if size <= 0 or size > MAX_EXPORT_BYTES:
        raise ChatgptBridgeError("chatgpt-export-size-out-of-range")
    text = src.read_text(encoding="utf-8")
    if len(text.encode("utf-8")) > MAX_EXPORT_BYTES:
        raise ChatgptBridgeError("chatgpt-export-size-out-of-range")
    if scan_text(text):
        raise ChatgptBridgeError("chatgpt-export-secret-findings")
    turns = parse_chat_export(text)
    if not turns:
        raise ChatgptBridgeError("chatgpt-export-no-turns")
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    quarantine = quarantine_provider_output(
        vault,
        envelope_id=f"chatgpt-bridge-{bid}",
        adapter_id="chatgpt-export-bridge",
        payload_text=text,
        payload_kind="text",
        adapters_enabled=True,
    )
    payload: dict[str, Any] = {
        "schema_version": 1,
        "package_id": PACKAGE_ID,
        "compat_snapshot_id": SNAPSHOT_ID,
        "bridge_id": bid,
        "source_path": str(src),
        "source_sha256": digest,
        "turn_count": len(turns),
        "turns": [t.as_dict() for t in turns],
        "export_variant": (
            "json"
            if export_path.suffix.lower() == ".json"
            else "markdown-or-text"
        ),
        "quarantine": {
            "envelope_id": quarantine.get("envelope_id"),
            "status": quarantine.get("status"),
        },
        "chatgpt_bridge": True,
        "live_chatgpt_api": False,
        "llm_authority": False,
        "operator_id": op.operator_id,
        "truth_boundary": TRUTH_BOUNDARY,
        "authority": {
            "level": "derived",
            "note": "ChatGPT bridge quarantines LLM text; never Layer B",
        },
        "generated": {"by": "project-atlas"},
    }
    out = vault / "generated" / "ops" / "chatgpt" / f"{bid}-bridge.json"
    _atomic_write_json(out, payload)
    return payload
