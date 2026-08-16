"""Validate untrusted AgentResultEnvelope payloads (AS-ORCH-001A).

Treat structured agent output as untrusted input. Fail closed on unknown
enums, extra fields, malformed receipts, and oversized payloads. Validation
and classification have no side effects and do not execute envelope content.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Final, TextIO

from pydantic import ValidationError

from project_atlas.orchestration.models import (
    PACKAGE_ID,
    SCHEMA_KIND,
    TRUTH_BOUNDARY,
    AgentResultEnvelope,
    NextTransition,
    OrchestrationDecision,
    WorkflowState,
)
from project_atlas.orchestration.transitions import classify_envelope
from project_atlas.schema import SchemaValidationError, validate_record

MAX_RESULT_BYTES: Final[int] = 256 * 1024


class ResultValidationError(ValueError):
    """Raised when an envelope cannot be accepted as a typed result."""


def parse_envelope(payload: object) -> AgentResultEnvelope:
    """Validate a mapping against the Pydantic model and the shipped JSON schema."""
    if not isinstance(payload, dict):
        raise ResultValidationError("result envelope must be a JSON object")
    try:
        envelope = AgentResultEnvelope.model_validate(payload)
    except ValidationError as exc:
        raise ResultValidationError(f"result envelope invalid: {exc}") from exc
    try:
        validate_record(envelope, SCHEMA_KIND)
    except SchemaValidationError as exc:
        raise ResultValidationError(str(exc)) from exc
    return envelope


def malformed_decision(reason: str) -> OrchestrationDecision:
    """Fail-closed decision for schema-invalid or unreadable input."""
    return OrchestrationDecision(
        valid=False,
        producer=None,
        task=None,
        outcome=None,
        workflow_state=WorkflowState.REJECTED,
        next_transition=NextTransition.REJECTED,
        execution_authorized=False,
        owner_required=False,
        merge_authorized=False,
        reasons=["malformed_or_schema_invalid", reason],
        requested_transition=None,
    )


def validate_and_classify(payload: object) -> OrchestrationDecision:
    """Validate then classify. Malformed input yields REJECTED, never execution."""
    try:
        envelope = parse_envelope(payload)
    except ResultValidationError as exc:
        return malformed_decision(str(exc))
    return classify_envelope(envelope)


def load_result_bytes(data: bytes) -> object:
    """Decode and parse JSON bytes with a hard size limit."""
    if len(data) > MAX_RESULT_BYTES:
        raise ResultValidationError("result envelope exceeds size limit")
    try:
        text = data.decode("utf-8")
    except UnicodeError as exc:
        raise ResultValidationError("result envelope is not valid UTF-8") from exc
    try:
        payload: object = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ResultValidationError(f"result envelope is not valid JSON: {exc}") from exc
    return payload


def read_result_source(
    *,
    path: Path | None,
    from_stdin: bool,
    stdin: TextIO,
) -> bytes:
    """Read envelope bytes from a file or stdin. Never executes the content."""
    if from_stdin and path is not None and str(path) != "-":
        raise ResultValidationError("provide a result path or --stdin, not both")
    use_stdin = from_stdin or (path is not None and str(path) == "-")
    if use_stdin:
        return _read_stdin_bytes(stdin)
    if path is None:
        raise ResultValidationError(
            "result path is required (example: atlas orchestrator validate-result result.json)"
        )
    return path.read_bytes()


def _read_stdin_bytes(stdin: TextIO) -> bytes:
    raw_buffer = getattr(stdin, "buffer", None)
    if raw_buffer is not None:
        data = raw_buffer.read(MAX_RESULT_BYTES + 1)
        if isinstance(data, bytes):
            return data
    text = stdin.read(MAX_RESULT_BYTES + 1)
    return text.encode("utf-8")


def run_validate_result(
    *,
    path: Path | None,
    from_stdin: bool,
    stdin: TextIO,
) -> tuple[OrchestrationDecision, int]:
    """Read-only validate+classify entry used by the CLI. Exit 0 iff envelope is valid."""
    try:
        raw = read_result_source(path=path, from_stdin=from_stdin, stdin=stdin)
        payload = load_result_bytes(raw)
    except ResultValidationError as exc:
        return malformed_decision(str(exc)), 1
    except OSError as exc:
        return malformed_decision(f"cannot read result file: {exc}"), 1
    decision = validate_and_classify(payload)
    return decision, (0 if decision.valid else 1)


def package_identity() -> dict[str, str]:
    return {
        "package_id": PACKAGE_ID,
        "schema_kind": SCHEMA_KIND,
        "truth_boundary": TRUTH_BOUNDARY,
    }
