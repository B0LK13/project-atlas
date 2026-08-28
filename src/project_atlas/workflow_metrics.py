"""AS-CODER-ALPHA-WORKFLOW-METRICS-001 — North Star metrics from objective evidence.

Read-only compiler over existing ops receipts. Telemetry != Truth Core.
Does not fabricate zeros. When Atlas cannot infer a metric, status is
``UNKNOWN`` or ``NOT_INSTRUMENTED``.

Does not capture raw prompts or chat transcripts merely to calculate a
metric. Does not import live-LLM or network clients.
"""

from __future__ import annotations

import json
import math
import os
from pathlib import Path
from typing import Any, Final, Literal

from atlas_contracts.identity import safe_relative_component

PACKAGE_ID: Final[str] = "AS-CODER-ALPHA-WORKFLOW-METRICS-001"
GENERATOR_ID: Final[str] = "atlas-coder-alpha-workflow-metrics-001"
SCHEMA_NAME: Final[str] = "atlas.coder-alpha.workflow-metrics.v1"
RECEIPT_REL: Final[Path] = Path("generated") / "ops" / "workflow-metrics.json"
TRUTH_BOUNDARY: Final[str] = (
    "WORKFLOW METRICS != TRUTH CORE / TELEMETRY != AUTHORITY / "
    "UNKNOWN != 0 / NOT_INSTRUMENTED != 0 / DEMO_FIXTURE != AUTHENTIC_PILOT"
)

MetricStatus = Literal["MEASURED", "UNKNOWN", "NOT_INSTRUMENTED"]

METRIC_IDS: Final[tuple[str, ...]] = (
    "TIME_TO_USEFUL_CONTEXT",
    "HANDOFF_SUCCESS_RATE",
    "STALE_CONTEXT_RATE",
    "UNKNOWN_HONESTY",
    "CONTEXT_ACCURACY",
    "MEANINGFUL_CHANGES_CAPTURED",
    "USER_CORRECTIONS_REQUIRED",
    "MISTAKES_PREVENTED",
    "REEXPLANATION_RATE",
)

_HANDOFF_DIR = Path("generated") / "ops" / "handoffs"
_CAPTURE_DIR = Path("generated") / "ops" / "session-captures"
_FRESH_AGENT_DIR = Path("generated") / "ops" / "fresh-agent"
_FRESHNESS_DIR = Path("generated") / "ops" / "context-freshness"
_CONNECT_RECEIPT = Path("generated") / "ops" / "connect-receipt.json"


class WorkflowMetricsError(ValueError):
    """Fail-closed workflow-metrics error."""


def _safe_project_id(project_id: str) -> str:
    try:
        return safe_relative_component(project_id, label="project id")
    except ValueError as exc:
        raise WorkflowMetricsError(str(exc)) from exc


def _write_atomic(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    try:
        tmp.write_bytes(content)
        os.replace(tmp, path)
    finally:
        if tmp.exists():
            tmp.unlink(missing_ok=True)


def _read_json(path: Path) -> tuple[str, dict[str, Any] | None]:
    if not path.is_file():
        return "absent", None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return "unreadable", None
    if not isinstance(raw, dict):
        return "unreadable", None
    return "ok", raw


def _receipt_in_project_scope(payload: dict[str, Any], project_id: str | None) -> bool:
    if not project_id:
        return True
    scoped = payload.get("project_id")
    if not isinstance(scoped, str) or not scoped.strip():
        return False
    return scoped == project_id


def _strict_json_bool(value: object) -> bool | None:
    """Accept only JSON booleans — never bool-subclass int coercion."""
    if type(value) is bool:
        return value
    return None


def _numeric_metric_value(value: object) -> float | None:
    """Accept finite non-bool numbers in the closed rate range [0, 1] only."""
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        number = float(value)
        if not math.isfinite(number):
            return None
        if number < 0.0 or number > 1.0:
            return None
        return number
    return None


def _metric(
    metric_id: str,
    *,
    status: MetricStatus,
    value: float | int | None,
    evidence: list[str],
    note: str,
) -> dict[str, Any]:
    if status != "MEASURED" and value is not None:
        raise WorkflowMetricsError(f"unmeasured-metric-must-not-carry-value:{metric_id}")
    if status == "MEASURED" and value is None:
        raise WorkflowMetricsError(f"measured-metric-missing-value:{metric_id}")
    return {
        "id": metric_id,
        "status": status,
        "value": value,
        "evidence": evidence,
        "note": note,
    }


def _list_json(directory: Path, prefix: str) -> list[Path]:
    if not directory.is_dir():
        return []
    return sorted(
        path
        for path in directory.glob("*.json")
        if path.name.startswith(prefix) and path.name != "latest.json"
    )


def _time_to_useful_context(vault: Path) -> dict[str, Any]:
    status, receipt = _read_json(vault / _CONNECT_RECEIPT)
    if status == "absent":
        return _metric(
            "TIME_TO_USEFUL_CONTEXT",
            status="NOT_INSTRUMENTED",
            value=None,
            evidence=[],
            note=(
                "Connect receipts omit wall-clock timestamps (NFR-001 / ADR-001). "
                "Duration from connect/resume to useful context is not instrumented."
            ),
        )
    if status == "unreadable":
        return _metric(
            "TIME_TO_USEFUL_CONTEXT",
            status="UNKNOWN",
            value=None,
            evidence=["generated/ops/connect-receipt.json"],
            note="Connect receipt exists but is unreadable; duration still not instrumented.",
        )
    assert receipt is not None
    if "duration_ms" in receipt or "elapsed_ms" in receipt or "generated_at" in receipt:
        return _metric(
            "TIME_TO_USEFUL_CONTEXT",
            status="UNKNOWN",
            value=None,
            evidence=["generated/ops/connect-receipt.json"],
            note=(
                "A clock-like field is present but this compiler refuses to treat "
                "it as a duration metric without an explicit instrumented contract."
            ),
        )
    return _metric(
        "TIME_TO_USEFUL_CONTEXT",
        status="NOT_INSTRUMENTED",
        value=None,
        evidence=["generated/ops/connect-receipt.json"],
        note=(
            "Connect receipt inspected; no duration field. "
            "NFR-001 forbids wall-clock timestamps in generated content."
        ),
    )


def _handoff_success_rate(vault: Path, project_id: str | None) -> dict[str, Any]:
    root = vault / _HANDOFF_DIR
    if not root.exists():
        return _metric(
            "HANDOFF_SUCCESS_RATE",
            status="UNKNOWN",
            value=None,
            evidence=[],
            note="No handoff receipt directory; resume success cannot be inferred.",
        )
    packs = _list_json(root, "handoff-")
    latest_status, _latest = _read_json(root / "latest.json")
    resume_receipts = _list_json(root, "resume-")
    if not packs:
        return _metric(
            "HANDOFF_SUCCESS_RATE",
            status="UNKNOWN",
            value=None,
            evidence=["generated/ops/handoffs/"],
            note=(
                "Handoff directory present but no handoff-*.json packs. "
                "Create count is not assumed to be zero for success rate."
            ),
        )
    scoped = 0
    for path in packs:
        status, payload = _read_json(path)
        if status != "ok" or payload is None:
            continue
        if not _receipt_in_project_scope(payload, project_id):
            continue
        scoped += 1
    if not resume_receipts:
        return _metric(
            "HANDOFF_SUCCESS_RATE",
            status="UNKNOWN",
            value=None,
            evidence=[
                f"generated/ops/handoffs/ ({scoped} create packs)",
                f"latest.json={latest_status}",
            ],
            note=(
                f"Objective handoff_create_count={scoped}. "
                "Resume success is not durably receipted, so the rate is UNKNOWN "
                "rather than create_count/create_count."
            ),
        )
    resumes_ok = 0
    resumes_total = 0
    for path in resume_receipts:
        status, payload = _read_json(path)
        # Malformed / unreadable resumes are not evidence (WFM-001).
        if status != "ok" or payload is None:
            continue
        if not _receipt_in_project_scope(payload, project_id):
            continue
        resumes_total += 1
        if payload.get("status") == "resumed":
            resumes_ok += 1
    if resumes_total == 0:
        return _metric(
            "HANDOFF_SUCCESS_RATE",
            status="UNKNOWN",
            value=None,
            evidence=["generated/ops/handoffs/"],
            note="Resume receipts present but none in project scope.",
        )
    return _metric(
        "HANDOFF_SUCCESS_RATE",
        status="MEASURED",
        value=resumes_ok / resumes_total,
        evidence=["generated/ops/handoffs/"],
        note=(
            f"resumed={resumes_ok} of {resumes_total} resume receipts; "
            f"latest={latest_status}"
        ),
    )


def _rate_from_receipts(
    vault: Path,
    directory: Path,
    metric_id: str,
    field_path: tuple[str, ...],
    *,
    project_id: str | None,
    absent_note: str,
) -> dict[str, Any]:
    root = vault / directory
    if not root.exists():
        return _metric(
            metric_id,
            status="UNKNOWN",
            value=None,
            evidence=[],
            note=absent_note,
        )
    files = sorted(path for path in root.glob("*.json") if path.name != "latest.json")
    if not files:
        return _metric(
            metric_id,
            status="UNKNOWN",
            value=None,
            evidence=[directory.as_posix()],
            note="Directory present but no score receipts to average.",
        )
    values: list[float] = []
    evidence: list[str] = []
    for path in files:
        status, payload = _read_json(path)
        if status != "ok" or payload is None:
            continue
        if not _receipt_in_project_scope(payload, project_id):
            continue
        cursor: Any = payload
        for key in field_path:
            if not isinstance(cursor, dict) or key not in cursor:
                cursor = None
                break
            cursor = cursor[key]
        numeric = _numeric_metric_value(cursor)
        if numeric is None:
            continue
        values.append(numeric)
        evidence.append(path.relative_to(vault).as_posix())
    if not values:
        return _metric(
            metric_id,
            status="UNKNOWN",
            value=None,
            evidence=[directory.as_posix()],
            note="Receipts present but the metric field is absent.",
        )
    return _metric(
        metric_id,
        status="MEASURED",
        value=sum(values) / len(values),
        evidence=evidence,
        note=f"averaged {len(values)} receipt(s)",
    )


def _meaningful_changes(vault: Path, project_id: str | None) -> dict[str, Any]:
    root = vault / _CAPTURE_DIR
    if not root.exists():
        return _metric(
            "MEANINGFUL_CHANGES_CAPTURED",
            status="UNKNOWN",
            value=None,
            evidence=[],
            note=(
                "Session-capture directory absent. A missing instrument is not zero "
                "captures."
            ),
        )
    files = _list_json(root, "capture-")
    counted = 0
    meaningful = 0
    for path in files:
        status, payload = _read_json(path)
        if status != "ok" or payload is None:
            continue
        if not _receipt_in_project_scope(payload, project_id):
            continue
        counted += 1
        changes = payload.get("changes")
        if isinstance(changes, list) and any(str(item).strip() for item in changes):
            meaningful += 1
    if counted == 0:
        return _metric(
            "MEANINGFUL_CHANGES_CAPTURED",
            status="UNKNOWN",
            value=None,
            evidence=["generated/ops/session-captures/"],
            note=(
                "No valid in-scope capture receipts; absent evidence is not "
                "measured zero."
            ),
        )
    return _metric(
        "MEANINGFUL_CHANGES_CAPTURED",
        status="MEASURED",
        value=meaningful,
        evidence=["generated/ops/session-captures/"],
        note=(
            f"{meaningful} of {counted} inspected capture receipts list "
            "non-empty changes"
        ),
    )


def _reexplanation_rate(vault: Path, project_id: str | None) -> dict[str, Any]:
    root = vault / _FRESH_AGENT_DIR
    if not root.exists():
        return _metric(
            "REEXPLANATION_RATE",
            status="UNKNOWN",
            value=None,
            evidence=[],
            note="No fresh-agent challenge receipts; re-explanation is not inferred.",
        )
    files = sorted(path for path in root.glob("*.json") if path.name != "latest.json")
    if not files:
        return _metric(
            "REEXPLANATION_RATE",
            status="UNKNOWN",
            value=None,
            evidence=["generated/ops/fresh-agent/"],
            note="Fresh-agent directory present but empty of score receipts.",
        )
    total = 0
    required = 0
    evidence: list[str] = []
    for path in files:
        status, payload = _read_json(path)
        if status != "ok" or payload is None:
            continue
        if not _receipt_in_project_scope(payload, project_id):
            continue
        flag = _strict_json_bool(payload.get("reexplanation_required"))
        if flag is None:
            continue
        total += 1
        if flag:
            required += 1
        evidence.append(path.relative_to(vault).as_posix())
    if total == 0:
        return _metric(
            "REEXPLANATION_RATE",
            status="UNKNOWN",
            value=None,
            evidence=["generated/ops/fresh-agent/"],
            note="Receipts lack reexplanation_required; rate not inferred as zero.",
        )
    return _metric(
        "REEXPLANATION_RATE",
        status="MEASURED",
        value=required / total,
        evidence=evidence,
        note=f"{required} of {total} scored challenge(s) required re-explanation",
    )


def compile_workflow_metrics(
    vault: Path,
    *,
    project_id: str | None = None,
) -> dict[str, Any]:
    """Compile North Star metrics from objective ops receipts only."""
    vault_path = vault.expanduser().resolve()
    if not vault_path.is_dir():
        raise WorkflowMetricsError(f"vault is not a directory: {vault_path}")
    scoped = _safe_project_id(project_id) if project_id else None
    metrics = [
        _time_to_useful_context(vault_path),
        _handoff_success_rate(vault_path, scoped),
        _rate_from_receipts(
            vault_path,
            _FRESHNESS_DIR,
            "STALE_CONTEXT_RATE",
            ("metrics", "STALE_CONTEXT_RATE"),
            project_id=scoped,
            absent_note=(
                "No context-freshness receipts. STALE_CONTEXT_RATE is UNKNOWN, not 0."
            ),
        ),
        _rate_from_receipts(
            vault_path,
            _FRESH_AGENT_DIR,
            "UNKNOWN_HONESTY",
            ("metrics", "UNKNOWN_HONESTY"),
            project_id=scoped,
            absent_note=(
                "No fresh-agent challenge receipts. UNKNOWN_HONESTY is UNKNOWN, not 0."
            ),
        ),
        _metric(
            "CONTEXT_ACCURACY",
            status="NOT_INSTRUMENTED",
            value=None,
            evidence=[],
            note=(
                "North Star CONTEXT_ACCURACY has no durable objective receipt yet. "
                "Exposed as NOT_INSTRUMENTED rather than omitted."
            ),
        ),
        _meaningful_changes(vault_path, scoped),
        _metric(
            "USER_CORRECTIONS_REQUIRED",
            status="NOT_INSTRUMENTED",
            value=None,
            evidence=[],
            note=(
                "No objective owner-edit / correction receipt exists. "
                "Not fabricated as zero."
            ),
        ),
        _metric(
            "MISTAKES_PREVENTED",
            status="NOT_INSTRUMENTED",
            value=None,
            evidence=[],
            note=(
                "No durable block/gate receipt records that Atlas prevented a mistake. "
                "Freshness findings alone are not counted as preventions."
            ),
        ),
        _reexplanation_rate(vault_path, scoped),
    ]
    by_id = {item["id"]: item for item in metrics}
    if set(by_id) != set(METRIC_IDS):
        raise WorkflowMetricsError("metric-set-incomplete")
    for item in metrics:
        if item["status"] != "MEASURED" and item["value"] is not None:
            raise WorkflowMetricsError(f"fabricated-value:{item['id']}")
    return {
        "schema_version": 1,
        "schema": SCHEMA_NAME,
        "package_id": PACKAGE_ID,
        "project_id": scoped,
        "metrics": by_id,
        "privacy": {
            "raw_prompt_capture": False,
            "chat_transcript_capture": False,
            "secret_echo": False,
        },
        "truth_boundary": TRUTH_BOUNDARY,
        "generated": {"by": GENERATOR_ID},
        "honesty": {
            "authentic_pilot": False,
            "demo_fixture_ne_authentic_pilot": True,
            "telemetry_ne_truth_core": True,
            "unknown_ne_zero": True,
            "not_instrumented_ne_zero": True,
        },
    }


def write_workflow_metrics_receipt(
    vault: Path,
    report: dict[str, Any] | None = None,
    *,
    project_id: str | None = None,
) -> Path:
    """Persist a non-authoritative metrics receipt under generated/ops."""
    vault_path = vault.expanduser().resolve()
    payload = report or compile_workflow_metrics(vault_path, project_id=project_id)
    if "generated_at" in payload:
        raise WorkflowMetricsError("wall-clock-forbidden")
    out = vault_path / RECEIPT_REL
    _write_atomic(
        out,
        (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8"),
    )
    return out
