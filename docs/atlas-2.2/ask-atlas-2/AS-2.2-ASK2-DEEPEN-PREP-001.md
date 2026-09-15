# AS-2.2-ASK2-DEEPEN-PREP-001 — Ask Atlas 2 deepen (SAFE prep)

| Field | Value |
|---|---|
| Package | **AS-2.2-ASK2-DEEPEN-PREP-001** |
| Class | **PREP ONLY** (contracts / fixtures / ADR) |
| Unlock target | Post-`v2.1.0` → feeds future `AS-2.2-ASK2-001` |
| Tip audited | `4cd646a46be16b29db9cdaeb3e965530b2c4bea9` |
| Tree | `02ba2e6755a4cecc7ae83d02fa76be8708ebac08` |
| Scope | `docs/atlas-2.2/ask-atlas-2/**` (+ unique unit test) |
| Production mutation | **NONE** |
| `ask_atlas_live.py` | **do not mutate** |
| `ATLAS_2_1_RELEASE_CERTIFIED` | **NO** |
| `ATLAS_2_2_INTELLIGENCE_IMPLEMENTATION_UNLOCKED` | **NO** |

## Purpose

Deepen the Ask Atlas 2 answer surface **beyond** the research-ask2 envelope
already sketched under `docs/atlas-2.2/research/` and
`docs/atlas-2.2/contracts/research/ask-atlas-2-answer.schema.json`.

This PREP owns a **unique path** (`docs/atlas-2.2/ask-atlas-2/**`) for:

- structured citation chains (evidence → hypothesis → pack),
- multi-lens projections (web / MCP / CLI),
- deepen answer views with retained conflicts + UNKNOWN density rules,
- fail-closed forbidden-action vocabulary (live mutate / LLM authority /
  canonical write),

without reopening the 2.1 `ask_atlas_live` LIVE_READ_ONLY path and without
claiming 2.1 release credit.

## Conceptual reference (read-only)

| Surface | Package / path | Role in this PREP |
|---|---|---|
| Ask Atlas 1.x contract | `AS-2.0-WEB-ASK-001` | Thin read-only contract ancestor |
| Ask Atlas live | `ask_atlas_live.py` (AS-2.1) | LIVE_READ_ONLY match lens — **do not mutate** |
| Research Ask Atlas 2 facet | `AS-2.2-RESEARCH-001` → `research/ASK-ATLAS-2.md` | Base 8-field answer envelope |
| Research answer stub | `contracts/research/ask-atlas-2-answer.schema.json` | Flat answer shape (peer; do not dual-own) |
| Research fixture | `fixtures/research/expected-ask-atlas-2-answer.json` | Envelope sample (peer) |
| Soft peer | `AS-2.2-CONFLICT-UX-PREP-001` | Conflict-presence cards for CONFLICTS slot |

This PREP package **references** those contracts conceptually. It does **not**
relocate research stubs, does **not** dual-own the research fixture family,
and does **not** edit `src/project_atlas/ask_atlas_live.py`.

## Deliverables in this PREP

| Doc | Role |
|---|---|
| [`ARCHITECTURE.md`](ARCHITECTURE.md) | Layers, deepen delta, truth boundaries |
| [`CONTRACT.md`](CONTRACT.md) | Stub schema index + FR IDs |
| [`INVARIANTS.md`](INVARIANTS.md) | Live≠mutate / LLM≠authority / UI≠canonical |
| [`FIXTURE-PLAN.md`](FIXTURE-PLAN.md) | Fixture family inventory |
| [`contracts/`](contracts/) | JSON Schema stubs (docs-owned; not package data) |
| [`fixtures/`](fixtures/) | Synthetic rehearsal payloads |
| [`adr/ADR-2.2-ASK2-001-answer-lens-deepen-prep.md`](adr/ADR-2.2-ASK2-001-answer-lens-deepen-prep.md) | Prep boundary ADR |

**No `README.md`** in this tree (index ownership stays with the 2.2 prep-index
lane; package card above is the entry).

## Deepen delta vs research-ask2

| Concern | research-ask2 | This deepen PREP |
|---|---|---|
| Answer fields | Flat 8-field envelope | Same fields **plus** citation chains + lens block |
| Evidence | String ID list | Structured chain nodes with role + provenance |
| Consume path | Single projected answer | Explicit web / MCP / CLI lens projections |
| Fail-closed ops | Truth-boundary flags only | Forbidden-action vocabulary + negative fixtures |
| Live path | Documented non-replace | Explicit non-mutation of `ask_atlas_live.py` |

## Hard invariants

1. **ASK2 ≠ LIVE MUTATE** — deepen prep never edits `ask_atlas_live.py`.
2. **LLM ≠ AUTHORITY** — no `llm_authority=true`; no trust scores.
3. **UI ≠ CANONICAL** — lenses never write Layer B / never stamp authority.
4. **RESEARCH ENVELOPE ≠ DUAL OWN** — research stubs remain under `research/` /
   `contracts/research/`; this tree deepens under `ask-atlas-2/` only.
5. Fixture rehearsal ≠ authentic estate PILOT PASS ≠ WEB ACCEPTED ≠ 2.1 RELEASE
   CERTIFIED ≠ 2.2 unlock.

## Explicit non-claims

- Not a mutation of `src/project_atlas/ask_atlas_live.py` or `web_ask_atlas.py`
- Not shipped package-data schema promotion
- Not a replacement of the 2.1 LIVE_READ_ONLY match path
- Not `ATLAS_2_1_RELEASE_CERTIFIED = YES`
- Not `ATLAS_2_2_INTELLIGENCE_IMPLEMENTATION_UNLOCKED`
- Not authentic estate PILOT evidence
- Not dual ownership of `docs/atlas-2.2/research/**`

## Forbidden in this package

- Edits under `src/`, shipped `schemas/`, `apps/`, or Ask live runtime paths
- Editing `docs/atlas-2.2/README.md` (index owned by sibling harvest worker)
- Relabeling research-ask2 fixture success as 2.1/2.2 release credit
- Fixture payloads that invent PILOT roots, LLM authority, or live-path writes

## Exit (PREP)

PREP is complete when this tree lands via PR with docs/fixtures/ADR + unit
presence tests only. Runtime unlock remains blocked until
`ATLAS_2_2_INTELLIGENCE_IMPLEMENTATION_UNLOCKED`.
