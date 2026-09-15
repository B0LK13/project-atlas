# AS-2.0-FED-001 — Multi-vault federation join inventory

| Field | Value |
|---|---|
| Package | **AS-2.0-FED-001** |
| Directive | `D-PROJECT-ATLAS-1.0-VERIFY-TO-2.0-AUTONOMOUS-001` |
| Status | **PRODUCTION** |
| Class | **READY** (depends on AS-2.0-COMPAT-001) |

## Purpose

Operator-declared federation membership inventory. Consume-only. No crawl-as-consent,
no implicit merge, no cross-vault promote.

## Surfaces

- Schema: `federation-join-inventory`
- Module: `project_atlas.federation`
- CLI: `atlas federation join --member 'id|path|role'`

## Truth boundary

`FEDERATION JOIN ≠ CROSS-VAULT AUTHORITY`

## Non-claims

- Not estate sync / authentic PILOT
- Not Layer B authority merge
- Not Atlas 2.0 RELEASE CERTIFIED
