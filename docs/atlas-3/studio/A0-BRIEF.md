# AS-STUDIO-A0-001 — brief

| Field | Value |
|---|---|
| Package ID | `AS-STUDIO-A0-001` (proposed in #746; treat as allocated for Studio program unless registry collision found) |
| Phase | A0 |
| Status | **READY FOR IMPLEMENTATION PACKAGE** after this docs sync |
| Epic | [#746](https://github.com/B0LK13/project-atlas/issues/746) |

## Objective

Establish the foundation for Atlas Studio without claiming a workstation:

1. Exact current repository **reuse map** (Truth Core, coordination F1–F16,
   daemon/runtime/control-plane inventory).
2. **Studio ↔ daemon authority ADR** (`STUDIO_UI != AUTHORITY`,
   `ATLAS_DAEMON = AUTHORITATIVE_RUNTIME`).
3. Versioned typed **snapshot / event / API contracts**.
4. **Authentication/authorization** boundary.
5. **Threat model**.
6. **Compatibility / migration** policy (`NO_WHOLESALE_CORE_REWRITE`,
   `REUSE_BEFORE_REIMPLEMENT`).
7. Smallest **Linux read-only** Studio vertical slice using **real Atlas state**
   and F1–F16 primitives (`control-view` / telemetry / residuals / frontier) —
   no CLI text parsing as protocol; no mutation endpoints.

## Explicit non-goals (A0)

- Knowledge Plane / Improvement Plane runtime implementation.
- AS-STUDIO-A1 Mission Control productization beyond the RO spike.
- Merge/deploy/IV claims.
- Provider-specific architecture choices as Atlas architecture.

## Exit evidence (must be reviewable)

- Commit/tree inventory with exact paths reused.
- ADR + schemas + threat model + migration policy in-repo.
- Linux RO slice runnable against real coordination state (or honest
  UNAVAILABLE when coordination tip not present on the checkout).
- Tests proving: no mutation surface; stale/offline/unknown honesty;
  UI/process crash does not imply task termination contract (documented +
  tested at boundary stubs).
- PR opened; `MERGE_AUTHORIZATION = NOT_GRANTED` unless owner grants.

## Dependency on coordination stack

```text
ATLAS_AUTONOMOUS_COORDINATION_STACK = FULLY_INTEGRATED_AT_IMPLEMENTATION_LAYER
IMPLEMENTED != MERGED_TO_MAIN
```

A0 implementation should prefer the coordination PR tip (Feature 16 / #751
lineage) when executing the RO slice so it can import real F1–F16 modules.
Docs canon may land on `main` independently.
