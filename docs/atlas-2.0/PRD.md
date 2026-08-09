# Atlas 2.0 — PRD sketch (**PROTOTYPE / PREP**)

Status: **PREP ONLY** — `ATLAS_2_0_IMPLEMENTATION_READY = NO`.

## Problem

Atlas 1.0 certifies a single-vault, offline knowledge compiler. Estate-scale and
provider-assisted workflows need a second major version with harder isolation
and compatibility gates.

## Users

- Portfolio operators maintaining multiple project vaults
- Governors certifying release and pilot evidence
- Optional provider operators (adapters disabled by default)

## Draft capabilities (not requirements until READY)

| ID | Capability | 1.0 dependency |
|---|---|---|
| C-2.0-01 | Multi-vault federation join | XPROJ + ID |
| C-2.0-02 | Advanced Command Center modes | WEB ACCEPTED |
| C-2.0-03 | Provider adapter quarantine path | NFR-006 |
| C-2.0-04 | Estate sync v2 incremental | INT-013 / SYNC-001 |
| C-2.0-05 | Compatibility snapshot consumer | 1.0 freeze |

## Acceptance (future)

Tracked in `IMPLEMENTATION-READY-GATE.md`. Do not treat this PRD as authorization.
