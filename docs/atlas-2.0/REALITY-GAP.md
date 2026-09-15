# Reality Gap analysis (Atlas 1.0 → 2.0)

Status: **TRACKED** via AS-2.0-REALITY-GAP-001 fixture inventory.
Not a certification of either release. Fixtures only — no estate invent.

## Purpose

Name gaps between current 1.0 Core/Web/SYNC scaffolds and aspirational 2.0
themes so Track B stays honest.

| Gap | gap_id | 1.0 today | 2.0 aspiration | Blocker |
|---|---|---|---|---|
| Estate twin | `estate-twin` | fixtures only; PILOT_ROOTS=0 | Digital Twin | PILOT / waiver |
| Agent OS in Core | `agent-os-in-core` | sibling control plane | integrated Agent OS | owner auth + READY |
| Federation | `federation` | XPROJ derived only | multi-vault FED | contract freeze |
| Advanced UX | `advanced-ux` | WEB ACCEPTED cleared on tip | UX-001 advanced CC | WEB governor #10 |
| Production SYNC | `production-sync` | dry-run scaffolds | SYNC v2 | PILOT + INT-013 |
| Provider/MCP | `provider-mcp` | design / optional registry | optional adapters | NFR-006 + freeze |

## Machine inventory

- Package: [AS-2.0-REALITY-GAP-001.md](../AS-2.0-REALITY-GAP-001.md)
- Schema: `reality-gap-inventory`
- Fixtures: [fixtures/reality-gap/](fixtures/reality-gap/)

## Explicit non-claims

- Does not invent PILOT roots (`pilot_roots=0`)
- Does not stamp WEB ACCEPTED / RELEASE / 2.0 READY from fixture success
- Fixture twin ≠ authentic estate PILOT PASSED

See [ARCHITECTURE.md](ARCHITECTURE.md), [DIGITAL-TWIN.md](DIGITAL-TWIN.md).
