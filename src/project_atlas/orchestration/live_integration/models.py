"""Integration report models. Never mint authorization."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ComponentManifest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    taskcontract_head: str
    taskcontract_tree: str
    taskcontract_impl_note: str = "single implementation tip (= delivery head)"
    context_tip_head: str
    context_tip_tree: str
    context_impl_head: str
    context_impl_tree: str
    readiness_tip_head: str
    readiness_tip_tree: str
    readiness_impl_head: str
    readiness_impl_tree: str
    supervisor_base_head: str
    supervisor_base_note: str
    integration_head: str | None = None
    integration_tree: str | None = None
    tested_tips: tuple[str, ...] = ()


class ReviewPackage(BaseModel):
    """Readiness selection + context packet identity for a human reviewer."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[1] = 1
    package_id: Literal["AS-LIVE-COMPONENT-INTEGRATION-002"] = (
        "AS-LIVE-COMPONENT-INTEGRATION-002"
    )
    task_id: str
    contract_id: str
    contract_digest: str
    selection_bucket: str
    selection_reasons: tuple[str, ...]
    blockers: tuple[dict[str, Any], ...]
    source_revisions: dict[str, str]
    context_packet_id: str | None = None
    context_content_digest: str | None = None
    context_freshness: str | None = None
    handoff_id: str | None = None
    execution_authorized: Literal[False] = False
    merge_authorized: Literal[False] = False
    independent_review: Literal[False] = False
    real_launch_authorized: Literal[False] = False
    fixture_labeled: bool = False


class IntegrationReport(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[1] = 1
    package_id: Literal["AS-LIVE-COMPONENT-INTEGRATION-002"] = (
        "AS-LIVE-COMPONENT-INTEGRATION-002"
    )
    components_available: bool
    live_interfaces_connected: bool
    controlled_chain_passed: bool
    independent_review: Literal[False] = False
    real_launch_authorized: Literal[False] = False
    remaining_blockers: tuple[str, ...] = ()
    evidence: dict[str, Any] = Field(default_factory=dict)
    manifest: ComponentManifest | None = None
