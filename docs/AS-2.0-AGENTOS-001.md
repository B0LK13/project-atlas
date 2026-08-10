# AS-2.0-AGENTOS-001 — Agent OS session envelope

| Field | Value |
|---|---|
| Package | **AS-2.0-AGENTOS-001** |
| Directive | `D-PROJECT-ATLAS-1.0-VERIFY-TO-2.0-AUTONOMOUS-001` |
| Status | **PRODUCTION** (thin envelope) |
| Class | **RWC** |

## Purpose

Governed session envelope complementary to the sibling control plane. Receipt
required; protected paths acknowledged; skill hash optional but fail-closed when
present. Never mutates Core authority planes.

## Surfaces

- Schema: `agentos-session-envelope`
- Module: `project_atlas.agentos`
- Output: `generated/ops/agentos/<session_id>.json`

## Truth boundary

`AGENT OS ENVELOPE ≠ CORE AUTHORITY`

## Non-claims

- Not a replacement for `atlas-vault-documentation/` control plane
- Not authentic PILOT / not 2.0 RELEASE CERTIFIED
