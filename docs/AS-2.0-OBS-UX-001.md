# AS-2.0-OBS-UX-001 — Obsidian non-canonical UX lenses

| Field | Value |
|---|---|
| Package | **AS-2.0-OBS-UX-001** |
| Class | **RWC** |
| Compat | `atlas-1.0.0-compat` |
| Status | PRODUCTION thin contract |

## Purpose

Freeze a read-only Obsidian-like lens registry that consumes Command Center
vocabulary without shipping a plugin or writing canonical vault truth.

## Invariants

- UI ≠ canonical
- Graph ≠ authority
- `plugin_shipped=false`, `canonical_writes=false`
- Bound to compatibility anchor; 1.0 wins conflicts

## Non-claims

- Not an Obsidian plugin release
- Not WEB APPLICATION ACCEPTED re-stamp
- Not Atlas 2.0 RELEASE CERTIFIED
