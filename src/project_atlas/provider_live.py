"""AS-2.1-PROV-LIVE-001 - real local-model provider adapter to quarantine.

Runs one deterministic local-model adapter (no remote SDK) and quarantines
output via AS-2.0-PROV-001 helpers. LLM != authority.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from project_atlas.authz import OperatorProfile, default_operator
from project_atlas.compat_anchor import SNAPSHOT_ID, require_compatibility_anchor
from project_atlas.provider_adapters import quarantine_provider_output
from project_atlas.secrets import scan_text

PACKAGE_ID = "AS-2.1-PROV-LIVE-001"
TRUTH_BOUNDARY = "PROV LIVE LOCAL-MODEL != REMOTE SDK / LLM!=AUTHORITY"
_ID_RE = re.compile(r"^[a-z][a-z0-9-]{0,63}$")
ADAPTER_ID = "local-model-echo-v1"


class ProviderLiveError(ValueError):
    """Fail-closed live provider error."""


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    tmp.replace(path)


def run_local_model_adapter(
    vault: Path,
    *,
    run_id: str,
    prompt: str,
    operator: OperatorProfile | None = None,
) -> dict[str, Any]:
    """Execute the local-model adapter and quarantine its output."""
    require_compatibility_anchor()
    op = operator or default_operator()
    op.require("provider.live")
    rid = run_id.strip()
    if not _ID_RE.fullmatch(rid):
        raise ProviderLiveError("prov-live-run-id-invalid")
    text = prompt.strip()
    if not text or len(text) > 8000:
        raise ProviderLiveError("prov-live-prompt-invalid")
    if scan_text(text):
        raise ProviderLiveError("prov-live-prompt-secret-findings")
    # Deterministic "model" output - reconstructable, not creative authority.
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    model_out = (
        f"[local-model-echo-v1] sha256={digest[:16]} chars={len(text)}\n"
        f"SUMMARY: {text[:240]}"
    )
    quarantine = quarantine_provider_output(
        vault,
        envelope_id=f"prov-live-{rid}",
        adapter_id=ADAPTER_ID,
        payload_text=model_out,
        payload_kind="text",
        adapters_enabled=True,
    )
    payload: dict[str, Any] = {
        "schema_version": 1,
        "package_id": PACKAGE_ID,
        "compat_snapshot_id": SNAPSHOT_ID,
        "run_id": rid,
        "adapter_id": ADAPTER_ID,
        "provider": "local-model",
        "prompt_sha256": digest,
        "output_sha256": hashlib.sha256(model_out.encode("utf-8")).hexdigest(),
        "quarantine": {
            "envelope_id": quarantine.get("envelope_id"),
            "status": quarantine.get("status"),
        },
        "prov_live": True,
        "remote_sdk": False,
        "llm_authority": False,
        "operator_id": op.operator_id,
        "truth_boundary": TRUTH_BOUNDARY,
        "authority": {
            "level": "derived",
            "note": "Live local-model output quarantined; never Layer B",
        },
        "generated": {"by": "project-atlas"},
    }
    out = vault / "generated" / "ops" / "provider" / f"{rid}-live-run.json"
    _atomic_write_json(out, payload)
    return payload
