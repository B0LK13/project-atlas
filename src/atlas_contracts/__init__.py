"""Stable, dependency-light contracts shared by Atlas subsystems."""

from atlas_contracts.agent_event import AgentEvent, EventType, SkillBinding, VaultIdentity
from atlas_contracts.event_package import (
    EVENT_PACKAGE_FILES,
    EventPackage,
    EventPackageInventory,
    PackageValidationError,
    inspect_event_package,
    load_event_package,
)
from atlas_contracts.provenance import ProvenanceRecord
from atlas_contracts.receipts import PipelineState, ReceiptReference

__all__ = [
    "EVENT_PACKAGE_FILES",
    "AgentEvent",
    "EventPackage",
    "EventPackageInventory",
    "EventType",
    "PackageValidationError",
    "PipelineState",
    "ProvenanceRecord",
    "ReceiptReference",
    "SkillBinding",
    "VaultIdentity",
    "inspect_event_package",
    "load_event_package",
]
