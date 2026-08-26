"""AS-CODER-ALPHA-ASK2-READ-001 -- vault-scoped Ask Atlas 2 REPORT READ.

Read-only consume of existing Ask Atlas 2 / ops-ask artifacts.
This module never calls ``ask_atlas_2``, never invents a grounded answer,
never accepts a question, and never writes vault state.

Honesty:
- ASK2 REPORT != ANSWER
- ARTIFACT != AUTHORITY
- MODEL != AUTHORITY
- UNKNOWN STAYS UNKNOWN
- EMPTY != HEALTHY
- UNKNOWN != HEALTHY
- MCP != AUTHORITY
- WRITE_APPLIED = false
- D149_TOUCHED = NO
- src/project_atlas/atlas3/** UNTOUCHED
- MERGE_AUTHORIZATION = NOT_GRANTED
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Final, Literal

PACKAGE_ID: Final[str] = "AS-CODER-ALPHA-ASK2-READ-001"
GENERATOR_ID: Final[str] = "atlas-coder-alpha-ask2-read-001"
SCHEMA_ID: Final[str] = "atlas.coder-alpha.ask2-read.v1"
SOURCE_PACKAGES: Final[tuple[str, ...]] = ("AS-2.2-ASK2-001",)
SOURCE_RELATIVES: Final[tuple[str, ...]] = (
    "generated/ops/ask",
    "generated/ops/ask2-answer.json",
)
SOURCE_COMMAND: Final[str] = "atlas ask2-status report"
TRUTH_BOUNDARY: Final[str] = (
    "ASK2 REPORT != ANSWER / ARTIFACT != AUTHORITY / MODEL != AUTHORITY / "
    "UNKNOWN STAYS UNKNOWN / EMPTY != HEALTHY / UNKNOWN != HEALTHY / "
    "MCP != AUTHORITY / WRITE_APPLIED = false / D149_TOUCHED = NO / "
    "src/project_atlas/atlas3/** UNTOUCHED / MERGE_AUTHORIZATION = NOT_GRANTED"
)

HONESTY_STATEMENTS: Final[tuple[str, ...]] = (
    "ASK2 REPORT != ANSWER",
    "ARTIFACT != AUTHORITY",
    "MODEL != AUTHORITY",
    "UNKNOWN STAYS UNKNOWN",
    "EMPTY != HEALTHY",
    "UNKNOWN != HEALTHY",
    "MCP != AUTHORITY",
    "WRITE_APPLIED = false",
    "D149_TOUCHED = NO",
    "src/project_atlas/atlas3/** UNTOUCHED",
    "MERGE_AUTHORIZATION = NOT_GRANTED",
)

StatusRollup = Literal["UNKNOWN", "EMPTY", "PRESENT"]


class WebAsk2ReadError(ValueError):
    """Fail-closed Ask Atlas 2 REPORT READ error."""


def _honesty() -> dict[str, bool | str]:
    return {
        "ask2_report_is_answer": False,
        "artifact_is_authority": False,
        "model_is_authority": False,
        "unknown_stays_unknown": True,
        "empty_is_healthy": False,
        "unknown_is_healthy": False,
        "mcp_is_authority": False,
        "write_applied": False,
        "WRITE_APPLIED": False,
        "ask2_invoked": False,
        "question_accepted": False,
        "grounded_answer_invented": False,
        "pilot_invented": False,
        "authentic_pilot": False,
        "demo_is_authentic": False,
        "owner_capability_granted": False,
        "D149_TOUCHED": "NO",
        "atlas3_untouched": "src/project_atlas/atlas3/** UNTOUCHED",
        "MERGE_AUTHORIZATION": "NOT_GRANTED",
        "lens_is_authority": False,
        "ui_is_canonical": False,
        "graph_is_authority": False,
        "atlas_opt_wake_gate": "CLOSED",
    }


def _resolve_vault(vault: Path) -> Path:
    root = vault.expanduser()
    try:
        root = root.resolve()
    except OSError as exc:
        raise WebAsk2ReadError(f"ask2-read-vault-unreadable:{exc}") from exc
    if not root.is_dir():
        raise WebAsk2ReadError("ask2-read-vault-missing")
    return root


def _inside(root: Path, candidate: Path) -> Path:
    resolved = candidate.resolve()
    if not resolved.is_relative_to(root):
        raise WebAsk2ReadError("ask2-read-path-escape")
    return resolved


def _reject_invented_authority(payload: dict[str, Any], *, name: str) -> None:
    if payload.get("authentic_pilot") is True:
        raise WebAsk2ReadError("ask2-read-authentic-pilot-invented")
    if payload.get("AUTHENTIC_PILOT") is True:
        raise WebAsk2ReadError("ask2-read-authentic-pilot-invented")
    if payload.get("estate_pilot_passed") is True:
        raise WebAsk2ReadError("ask2-read-estate-pilot-invented")
    if payload.get("MERGE_AUTHORIZATION") in {"GRANTED", "granted", True}:
        raise WebAsk2ReadError(f"ask2-read-merge-authority-invented:{name}")


def _load_json_object(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeError) as exc:
        raise WebAsk2ReadError(f"ask2-read-artifact-invalid:{path.name}") from exc
    if not isinstance(payload, dict):
        raise WebAsk2ReadError(f"ask2-read-artifact-not-object:{path.name}")
    _reject_invented_authority(payload, name=path.name)
    return payload


def _candidate_files(vault: Path) -> list[Path]:
    files: list[Path] = []
    seen: set[Path] = set()
    single = vault / "generated" / "ops" / "ask2-answer.json"
    if single.exists():
        if not single.is_file():
            raise WebAsk2ReadError("ask2-read-artifact-not-file:generated/ops/ask2-answer.json")
        files.append(_inside(vault, single))
        seen.add(files[-1])
    ask_dir = vault / "generated" / "ops" / "ask"
    if ask_dir.exists():
        if not ask_dir.is_dir():
            raise WebAsk2ReadError("ask2-read-artifact-not-dir:generated/ops/ask")
        _inside(vault, ask_dir)
        for path in sorted(ask_dir.iterdir(), key=lambda item: item.name):
            if not path.is_file() or path.suffix != ".json":
                continue
            resolved = _inside(vault, path)
            if resolved not in seen:
                files.append(resolved)
                seen.add(resolved)
    return files


def _existing_ask2(vault: Path) -> dict[str, Any]:
    records: list[dict[str, Any]] = []
    malformed = 0
    seen_ids: dict[str, str] = {}
    project_ids: set[str] = set()
    for path in _candidate_files(vault):
        relative = path.relative_to(vault).as_posix()
        try:
            payload = _load_json_object(path)
        except WebAsk2ReadError as exc:
            if "invented" in str(exc):
                raise
            malformed += 1
            continue
        artifact_id = str(payload.get("answer_id") or payload.get("id") or "").strip()
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        if artifact_id:
            prior = seen_ids.get(artifact_id)
            if prior is not None and prior != canonical:
                raise WebAsk2ReadError(f"ask2-read-id-collision:{artifact_id}")
            seen_ids[artifact_id] = canonical
        project_id = str(payload.get("project_id") or "").strip()
        if project_id:
            project_ids.add(project_id)
        records.append({"path": relative, "record": payload})
    records.sort(key=lambda row: str(row["path"]))
    return {
        "schema_version": 1,
        "artifact_count": len(records),
        "malformed_count": malformed,
        "project_ids": sorted(project_ids),
        "artifacts": records,
        "authentic_pilot": False,
        "ask2_invoked": False,
    }


def _rollup(view: dict[str, Any]) -> tuple[StatusRollup, str, str, bool]:
    raw_count = view.get("artifact_count")
    raw_malformed = view.get("malformed_count")
    count = raw_count if isinstance(raw_count, int) else 0
    malformed = raw_malformed if isinstance(raw_malformed, int) else 0
    if count == 0 and malformed == 0:
        return (
            "EMPTY",
            "no existing Ask Atlas 2 artifacts; EMPTY != HEALTHY; "
            "ASK2 REPORT != ANSWER; UNKNOWN STAYS UNKNOWN",
            "EMPTY_ASK2_VIEW",
            False,
        )
    if malformed > 0:
        return (
            "UNKNOWN",
            "ask2 artifacts exist but integrity is incomplete; "
            "UNKNOWN != HEALTHY; mixed valid+corrupt is not a healthy report",
            "UNKNOWN_ASK2_VIEW",
            False,
        )
    return (
        "PRESENT",
        "existing Ask Atlas 2 artifacts projected; ASK2 REPORT != ANSWER; "
        "ARTIFACT != AUTHORITY; MODEL != AUTHORITY",
        "ASK2_VIEW_PROJECTED",
        True,
    )


def _envelope(*, view: dict[str, Any]) -> dict[str, Any]:
    status, reason, reason_code, available = _rollup(view)
    return {
        "schema_version": 1,
        "schema": SCHEMA_ID,
        "package_id": PACKAGE_ID,
        "source_packages": list(SOURCE_PACKAGES),
        "source_relatives": list(SOURCE_RELATIVES),
        "source_command": SOURCE_COMMAND,
        "truth_boundary": TRUTH_BOUNDARY,
        "available": available,
        "status": status,
        "reason": reason,
        "reason_code": reason_code,
        "view": view,
        "honesty": _honesty(),
        "honesty_statements": list(HONESTY_STATEMENTS),
        "generated": {"by": GENERATOR_ID},
    }


def read_ask2_view(vault: Path) -> dict[str, Any]:
    """Read-only consume of existing Ask Atlas 2 artifacts. Never writes."""
    root = _resolve_vault(vault)
    return _envelope(view=_existing_ask2(root))


def render_ask2_text(view: dict[str, Any]) -> str:
    """Human CLI rendering. ASCII only."""
    inner: dict[str, Any] = {}
    raw_view = view.get("view")
    if isinstance(raw_view, dict):
        inner = raw_view
    project_ids = inner.get("project_ids")
    project_text = ",".join(project_ids) if isinstance(project_ids, list) else ""
    lines = [
        f"atlas ask2-status report [{view.get('status', 'UNKNOWN')}]",
        f"  available:        {view.get('available')}",
        f"  reason:           {view.get('reason_code')}",
        f"  artifact_count:   {inner.get('artifact_count', 0)}",
        f"  malformed_count:  {inner.get('malformed_count', 0)}",
        f"  project_ids:      {project_text or '(none)'}",
        (
            "  honesty:          ASK2 REPORT != ANSWER; ARTIFACT != AUTHORITY; "
            "MODEL != AUTHORITY; UNKNOWN STAYS UNKNOWN; EMPTY != HEALTHY; "
            "UNKNOWN != HEALTHY; MCP != AUTHORITY; WRITE_APPLIED = false"
        ),
    ]
    return "\n".join(lines) + "\n"
