# AS-2.0-KCI-001 — Knowledge Compilation Interface

| Field | Value |
|---|---|
| Package | **AS-2.0-KCI-001** |
| Directive | `D-PROJECT-ATLAS-1.0-VERIFY-TO-2.0-AUTONOMOUS-001` |
| Status | **PRODUCTION** (thin contract) |
| Class | **READY** (depends on AS-2.0-COMPAT-001) |
| Compat pin | `require_compatibility_anchor` / `atlas-1.0.0-compat` |

## Purpose

Thin, consume-only Knowledge Compilation Interface envelopes for fixture-safe
compile requests and receipts. Surfaces Agent OS / UX compile intent without
bypassing 1.0 provenance, authority, or validation gates.

## Surfaces

| Kind | Path |
|---|---|
| Schema | `kci-compile-request`, `kci-compile-receipt` |
| Module | `project_atlas.kci` |
| CLI | `atlas kci request`, `atlas kci receipt` |

## Truth boundary

`KCI COMPILE ≠ AUTHORITY / ≠ SILENT WINNER`

`KCI RECEIPT ≠ LAYER B AUTHORITY`

Receipts always set `consume_only=true` and `authority_promoted=false`.

## Non-claims

- Not Layer B claim/authority promotion
- Not silent authority-winner selection
- Not Atlas 2.0 RELEASE CERTIFIED
- Not authentic ESTATE PILOT PASS
- Not OpenAI/MCP production wiring
