"""AS-2.1-OAI-RESPONSES-POC-001 - experimental OpenAI Responses API POC.

NON_RELEASE_BLOCKING. Quarantine-first. llm_authority=false. No write tools.
OPENAI_API_KEY from environment only (never logged). Offline-first: without a
key, returns IMPLEMENTATION_READY_FOR_LIVE_SMOKE. Not a substitute for
authentic estate PILOT.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from project_atlas.app_service import open_app_service
from project_atlas.authz import OperatorProfile, default_operator
from project_atlas.compat_anchor import SNAPSHOT_ID, require_compatibility_anchor
from project_atlas.provider_adapters import quarantine_provider_output
from project_atlas.secrets import scan_text

PACKAGE_ID = "AS-2.1-OAI-RESPONSES-POC-001"
TRUTH_BOUNDARY = (
    "OAI RESPONSES POC EXPERIMENTAL != RELEASE GATE / LLM!=AUTHORITY / "
    "!= AUTHENTIC PILOT / NO WRITE TOOLS"
)
ADAPTER_ID = "oai-responses-poc-v1"
_ID_RE = re.compile(r"^[a-z][a-z0-9-]{0,63}$")
DEFAULT_MODEL = "gpt-4.1-mini"
API_URL = "https://api.openai.com/v1/responses"
MAX_BODY_BYTES = 256_000

# Read-only AppService tools only — never vault.write / actions / promote.
READ_ONLY_TOOL_NAMES: frozenset[str] = frozenset(
    {
        "atlas_health_read",
        "atlas_projects_list",
        "atlas_knowledge_list",
        "atlas_graph_summary",
    }
)


class OpenAIResponsesPocError(ValueError):
    """Fail-closed Responses POC error."""


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    tmp.replace(path)


def _tool_schemas() -> list[dict[str, Any]]:
    return [
        {
            "type": "function",
            "name": "atlas_health_read",
            "description": "Read Atlas vault health (read-only).",
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
        },
        {
            "type": "function",
            "name": "atlas_projects_list",
            "description": "List Atlas projects (read-only).",
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
        },
        {
            "type": "function",
            "name": "atlas_knowledge_list",
            "description": "List Atlas knowledge answers (read-only).",
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
        },
        {
            "type": "function",
            "name": "atlas_graph_summary",
            "description": "Read derived graph summary (not authority).",
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
        },
    ]


def execute_read_only_tool(vault: Path, tool_name: str) -> dict[str, Any]:
    """Dispatch one allow-listed read-only AppService tool."""
    if tool_name not in READ_ONLY_TOOL_NAMES:
        raise OpenAIResponsesPocError(f"oai-poc-write-or-unknown-tool:{tool_name}")
    svc = open_app_service(vault)
    if tool_name == "atlas_health_read":
        return svc.health()
    if tool_name == "atlas_projects_list":
        return {"projects": svc.projects()}
    if tool_name == "atlas_knowledge_list":
        return {"knowledge": svc.knowledge()}
    return svc.graph_summary()


def _api_key_present() -> bool:
    return bool(os.environ.get("OPENAI_API_KEY", "").strip())


def _call_responses_api(
    *,
    prompt: str,
    model: str,
    timeout_s: float = 60.0,
) -> dict[str, Any]:
    key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not key:
        raise OpenAIResponsesPocError("oai-poc-api-key-missing")
    body = {
        "model": model,
        "input": prompt,
        "tools": _tool_schemas(),
        "tool_choice": "auto",
        "store": False,
    }
    raw = json.dumps(body, sort_keys=True).encode("utf-8")
    if len(raw) > MAX_BODY_BYTES:
        raise OpenAIResponsesPocError("oai-poc-request-too-large")
    req = urllib.request.Request(
        API_URL,
        data=raw,
        method="POST",
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "User-Agent": "project-atlas-oai-responses-poc/2.1",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        # Never echo body (may contain prompt fragments); status only.
        raise OpenAIResponsesPocError(f"oai-poc-http:{exc.code}") from exc
    except urllib.error.URLError as exc:
        raise OpenAIResponsesPocError(f"oai-poc-network:{type(exc.reason).__name__}") from exc
    if not isinstance(payload, dict):
        raise OpenAIResponsesPocError("oai-poc-response-not-object")
    return payload


def _extract_output_text(api_payload: dict[str, Any]) -> str:
    """Best-effort text extraction from Responses API payload."""
    chunks: list[str] = []
    output = api_payload.get("output")
    if isinstance(output, list):
        for item in output:
            if not isinstance(item, dict):
                continue
            content = item.get("content")
            if isinstance(content, list):
                for part in content:
                    if isinstance(part, dict) and part.get("type") in {
                        "output_text",
                        "text",
                    }:
                        text = part.get("text")
                        if isinstance(text, str):
                            chunks.append(text)
            if item.get("type") == "message":
                # nested already handled
                pass
            if item.get("type") == "function_call":
                name = item.get("name")
                if isinstance(name, str):
                    chunks.append(f"[tool_call:{name}]")
    if not chunks:
        # Fallback: compact JSON without attempting to pretty-print secrets.
        chunks.append(
            json.dumps(
                {"id": api_payload.get("id"), "status": api_payload.get("status")},
                sort_keys=True,
            )
        )
    return "\n".join(chunks)


def _dispatch_tool_calls_from_response(
    vault: Path,
    api_payload: dict[str, Any],
) -> list[dict[str, Any]]:
    """Execute any function_call items with read-only tools only."""
    results: list[dict[str, Any]] = []
    output = api_payload.get("output")
    if not isinstance(output, list):
        return results
    for item in output:
        if not isinstance(item, dict):
            continue
        if item.get("type") != "function_call":
            continue
        name = item.get("name")
        if not isinstance(name, str):
            raise OpenAIResponsesPocError("oai-poc-tool-name-missing")
        tool_out = execute_read_only_tool(vault, name)
        results.append(
            {
                "tool": name,
                "ok": True,
                "result_sha256": hashlib.sha256(
                    json.dumps(tool_out, sort_keys=True).encode("utf-8")
                ).hexdigest(),
            }
        )
    return results


def run_openai_responses_poc(
    vault: Path,
    *,
    run_id: str,
    prompt: str,
    model: str = DEFAULT_MODEL,
    operator: OperatorProfile | None = None,
    force_offline: bool = False,
) -> dict[str, Any]:
    """Run experimental Responses POC; quarantine all model output."""
    require_compatibility_anchor()
    op = operator or default_operator()
    op.require("oai.responses")
    rid = run_id.strip()
    if not _ID_RE.fullmatch(rid):
        raise OpenAIResponsesPocError("oai-poc-run-id-invalid")
    text = prompt.strip()
    if not text or len(text) > 4000:
        raise OpenAIResponsesPocError("oai-poc-prompt-invalid")
    if scan_text(text):
        raise OpenAIResponsesPocError("oai-poc-prompt-secret-findings")

    key_present = _api_key_present() and not force_offline
    live_smoke = False
    smoke_status = "IMPLEMENTATION_READY_FOR_LIVE_SMOKE"
    api_meta: dict[str, Any] = {}
    tool_results: list[dict[str, Any]] = []
    retry_count = 0
    model_out = (
        "[oai-responses-poc offline] no OPENAI_API_KEY; "
        "read-only tool schemas registered; llm_authority=false"
    )

    allow_retry = (
        os.environ.get("ATLAS_OAI_POC_RETRY", "").strip().lower() in {"1", "true", "yes"}
    )

    if key_present:
        attempts = 2 if allow_retry else 1
        last_err: str | None = None
        for attempt in range(attempts):
            try:
                api_payload = _call_responses_api(prompt=text, model=model)
                tool_results = _dispatch_tool_calls_from_response(vault, api_payload)
                model_out = _extract_output_text(api_payload)
                live_smoke = True
                smoke_status = "LIVE_SMOKE_EXECUTED"
                api_meta = {
                    "response_id": api_payload.get("id"),
                    "status": api_payload.get("status"),
                    "model": api_payload.get("model") or model,
                    "output_item_count": (
                        len(api_payload["output"])
                        if isinstance(api_payload.get("output"), list)
                        else 0
                    ),
                    "attempt": attempt + 1,
                }
                last_err = None
                break
            except OpenAIResponsesPocError as exc:
                last_err = str(exc)
                if "oai-poc-http:429" in last_err and attempt + 1 < attempts:
                    retry_count += 1
                    time.sleep(1.5)
                    continue
                model_out = f"[oai-responses-poc live-attempt-failed] {last_err}"
                live_smoke = False
                if "oai-poc-http:429" in last_err:
                    smoke_status = "LIVE_SMOKE_RATE_LIMITED"
                elif last_err.startswith("oai-poc-http:"):
                    smoke_status = "LIVE_SMOKE_HTTP_ERROR"
                elif last_err.startswith("oai-poc-network:"):
                    smoke_status = "LIVE_SMOKE_NETWORK_ERROR"
                else:
                    smoke_status = "LIVE_SMOKE_FAILED"
                api_meta = {
                    "error_class": last_err.split(":")[0],
                    "error_code": last_err,
                    "attempt": attempt + 1,
                }
                break


    quarantine = quarantine_provider_output(
        vault,
        envelope_id=f"oai-resp-{rid}",
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
        "experimental": True,
        "release_blocking": False,
        "non_release_blocking": True,
        "openai_api_key_present": key_present,
        "live_smoke": live_smoke,
        "smoke_status": smoke_status,
        "retry_count": retry_count,
        "read_only_tools": sorted(READ_ONLY_TOOL_NAMES),
        "write_tools": [],
        "tool_results": tool_results,
        "api_meta": api_meta,
        "prompt_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "output_sha256": hashlib.sha256(model_out.encode("utf-8")).hexdigest(),
        "quarantine": {
            "envelope_id": quarantine.get("envelope_id"),
            "status": quarantine.get("status"),
        },
        "llm_authority": False,
        "authentic_pilot_substitute": False,
        "operator_id": op.operator_id,
        "truth_boundary": TRUTH_BOUNDARY,
        "authority": {
            "level": "derived",
            "note": "Experimental Responses POC; quarantined; never Layer B",
        },
        "generated": {"by": "project-atlas"},
    }
    out = vault / "generated" / "ops" / "oai-responses-poc" / f"{rid}-poc.json"
    _atomic_write_json(out, payload)
    return payload
