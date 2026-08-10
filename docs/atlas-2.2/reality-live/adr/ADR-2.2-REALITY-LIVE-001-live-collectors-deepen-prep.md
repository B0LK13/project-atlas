# ADR-2.2-REALITY-LIVE-001 — Live Reality Gap collectors deepen (PREP boundary)

| Field | Value |
|---|---|
| Status | **Accepted (PREP boundary)** |
| Package | AS-2.2-REALITY-LIVE-DEEPEN-PREP-001 |
| Date | 2026-08-10 |
| Tip | `961577c` |
| `ATLAS_2_1_RELEASE_CERTIFIED` | **NO** |

## Context

Wave-1 reality-live PREP (PR #167) landed collector design, plane taxonomy, schema
drafts, and positive fixtures under `docs/atlas-2.2/reality-live/` and
`docs/atlas-2.2/contracts/reality-live/`. Sibling wave-2 packages (mem-gov deepen,
research deepen, Ask Atlas 2 deepen) carry explicit invariants, fixture-plan
inventory, and negative rehearsal payloads. Live Reality Gap collectors lacked
that sibling depth.

## Decision

1. Land deepen invariants, forbidden-action schema, and negative fixtures under
   `docs/atlas-2.2/reality-live/**` only (unique deepen path vs base stub tree).
2. Keep base design docs, schema drafts, and positive fixtures at their existing
   paths — no relocation or dual ownership.
3. Forbid PILOT invent, LLM authority stamps, conversational sole certifier,
   Layer B promotion, and release-cert stamps in the forbidden-action vocabulary.
4. Do **not** dual-own AS-2.0-REALITY-GAP-001 inventory or mutate
   `reality_gap.py` / `reality_gap_ui.py` until unlock.

## Consequences

- Positive: reality-live reaches wave-2 sibling artifact depth; clear fail-closed
  vocabulary for future collector implementers.
- Negative: no runtime collector module until post-`v2.1.0` unlock; fixtures grant
  no gate credit.

## Non-decisions

- UI panel wiring for live gap report (supersedes 2.0 UI catalog timing)
- Authentic estate PILOT evidence ingestion paths
- Cross-plane rank ordering tweaks beyond conservative merge sketch
