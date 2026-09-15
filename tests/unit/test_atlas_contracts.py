"""Lockstep tests for the AS-INT-001 shared contract package."""

from __future__ import annotations

import json
from pathlib import Path

from atlas_contracts import AgentEvent, EventType, PipelineState


def test_contract_models_validate_required_identity_and_pipeline() -> None:
    event = AgentEvent(
        event_id="AE-contract-test",
        event_type=EventType.IMPLEMENTATION,
        project_id="project-atlas",
        session_id="AS-contract-session",
        agent_id="agent-one",
        adapter_id="generic-cli-v1",
        timestamp="2026-08-01T18:00:00Z",
        summary="contract test",
    )
    assert event.project_id == "project-atlas"
    assert PipelineState(captured=True, normalized=True, verified=True, routed=True).is_verified()


def test_contract_json_schemas_are_present_and_lockstep_versioned() -> None:
    schema_root = Path(__file__).parents[2] / "src" / "atlas_contracts" / "schemas"
    schemas = sorted(schema_root.glob("*.schema.json"))
    assert {path.name for path in schemas} == {
        "agent-event.schema.json",
        "event-package.schema.json",
        "provenance.schema.json",
        "receipt-reference.schema.json",
    }
    for schema_path in schemas:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
        assert schema["$id"].startswith("https://project-atlas.local/schemas/")
