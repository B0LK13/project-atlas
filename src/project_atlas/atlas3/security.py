"""AT3 foundation threat catalog (D-193 §13). Catalog ≠ scanner ≠ certification."""

from __future__ import annotations

from typing import Final

PACKAGE_ID: Final[str] = "AT3-SECURITY"
THREATS: Final[tuple[str, ...]] = (
    "provider_spoofing",
    "forged_owner_decisions",
    "cross_project_contamination",
    "secret_ingestion",
    "prompt_injection",
    "event_replay",
    "duplicate_events",
    "timestamp_spoofing",
    "malicious_attachments",
    "stale_memory_poisoning",
    "agent_self_certification",
    "authority_escalation",
)

CONTROLS: Final[dict[str, str]] = {
    "provider_spoofing": "import_mode + capability honesty; metadata != authority",
    "forged_owner_decisions": "FALSE_OWNER_DECISION without owner_origin",
    "cross_project_contamination": "fail-closed project routing",
    "secret_ingestion": "scan_text reject; no echo",
    "prompt_injection": "non-canonical; no auto-promote",
    "event_replay": "idempotent event_id",
    "duplicate_events": "ledger replay != second fact",
    "timestamp_spoofing": "observation only; stronger evidence wins",
    "malicious_attachments": "source safety / quarantine",
    "stale_memory_poisoning": "freshness + Start CURRENT refuse stale-as-truth",
    "agent_self_certification": "MODEL CLAIM != PROOF",
    "authority_escalation": "ledger/twin/inbox remain non-canonical",
}


def threat_model() -> dict[str, object]:
    return {
        "package": PACKAGE_ID,
        "threats": list(THREATS),
        "controls": dict(sorted(CONTROLS.items())),
        "external_security_certification": False,
        "reviewed": True,
    }
