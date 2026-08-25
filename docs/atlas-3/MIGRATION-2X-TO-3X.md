# Atlas 3.0 — Migration 2.x → 3.x

## Position

Atlas 3 is a **successor program**, not a vault-format break.

```text
MIGRATION_REQUIRED =
  NO breaking migration for existing vaults
  YES additive derived stores under generated/ops/atlas3/
  YES historical-doc classification (files kept)

COMPATIBILITY_RISK =
  LOW on isolated atlas3/ runtime
  HIGH if 2.x certified modules are rewritten
```

## What stays byte-compatible

| 2.x artifact | 3.x rule |
|---|---|
| `.atlas/vault.json` identity | Reuse; no remint |
| `projects/` identity locks | Reuse; fail-closed routing |
| `state/claims`, authoritative state | Read; no Atlas 3 writer |
| `review/conflicts` | Read |
| `generated/ops/bitemporal/` | Reuse engine |
| `generated/ops/conversation-captures/` | Reuse schema `atlas.conversation-capture.v1` |
| `generated/ops/chatgpt/` | ChatGPT bridge remains owner |
| `generated/ops/events/` | Do not dual-write |
| `generated/graph/relationships/` | Consume as derived |
| Compat anchor | Bind; do not relax |

## Additive 3.x stores

All new, derived, non-authoritative:

```text
generated/ops/atlas3/ledger/<project>.jsonl
generated/ops/atlas3/pulse/<project>.json
generated/ops/atlas3/start/<project>.json
generated/ops/atlas3/proof/<task-id>.json
generated/ops/atlas3/memory/<project>/envelopes/
generated/ops/atlas3/memory/<project>/items/
generated/ops/atlas3/memory/<project>/reconcile.json
generated/ops/atlas3/compat/receipt.json
```

Deleting these stores must not corrupt Layer A/B. They are rebuildable.

## Command migration

| 2.x command | 3.x command | Relationship |
|---|---|---|
| `atlas changed` | `atlas pulse` | Pulse composes changed; does not replace it |
| `atlas brief` / `atlas context` | `atlas start` | Start is budgeted briefing; does not replace brief |
| `atlas inbox list` / `atlas capture conversation` | `atlas memory *` | Memory searches extracted knowledge; capture remains intake |
| `atlas live oai-import` | `atlas memory sync` (future) | Sync composes export parsers; does not replace oai-import |
| orch `local_proof` | `atlas proof` | Different plane; proof-of-work ≠ SDK smoke |

Existing commands keep their contracts.

## Provider migration (D-192)

| 2.x | 3.x |
|---|---|
| `conversation_capture` structured_submission | Still the only Core capture mode |
| ChatGPT export / quarantine | Kept; Atlas 3 wraps `parse_chat_export` |
| `transcript_extraction` | Still **not** implemented in Core |
| chatgpt-live PREP | Still not live full-history sync |
| CLAUDE.md / GEMINI.md | Bootstrap only; not conversation ingestion |

## Compatibility invariants (AT3-005)

Proved by `atlas compatibility` / `prove_compatibility()` on isolated stores:

```text
NO_TRUTH_LOSS
NO_PROJECT_ID_ROTATION
NO_PROVENANCE_LOSS
NO_TEMPORAL_RESET
NO_AUTHORITY_ESCALATION
NO_CONTEXT_FRESHNESS_REGRESSION
NO_OWNER_GATE_REGRESSION
```

Prefer additive schemas. Atlas 3 must not write Layer B.

## Honesty during migration

- Do not claim a vault is “Atlas 3 native” because `atlas3/` artifacts exist.
- Do not claim ChatGPT/Claude/Gemini are synchronized when only fixtures ran.
- Do not migrate fixture twin (`AS-2.0-TWIN-001`) into authentic PILOT.
