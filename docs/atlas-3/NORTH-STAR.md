# Atlas 3.0 — North Star

| Field | Value |
|---|---|
| Directive | D-191 / D-193 |
| Status | **CANONICAL SUCCESSOR PROGRAM DIRECTION** |
| Current main | `f1b5256510cb66e037e6774aa49d753bdb7dd96f` |
| Precedence | Owner directives > landed `main` truth > this document > historical roadmaps |

## Definition

```text
ATLAS 3.0 =
THE VERIFIABLE SHARED REALITY LAYER BETWEEN
SOFTWARE PROJECTS, HUMANS, AND AUTONOMOUS AGENTS
```

Atlas 3 does not replace the Atlas 2.x knowledge compiler. It is the program
that turns landed Truth / Time / Context foundations into a **verifiable
project digital twin** that humans and every LLM provider can share.

Foundation layer ownership and exit criteria: `docs/atlas-3/FOUNDATION.md`.
Chronicle / Ambient Knowledge remains `ROADMAP_HORIZON`.

## Promises

**Primary promise:** Never explain your project to an AI twice.

**Extended promise:** Never let an agent act on stale, conflicting, unproven,
or out-of-scope project knowledge.

These promises already appear in Coder Alpha
(`docs/product/CODER-ALPHA-NORTH-STAR.md`). Atlas 3 keeps them and adds
verifiability: evidence, time, causality, intent, proof, then autonomy.

## Canonical stack

```text
EVIDENCE
  → TRUTH
  → TIME
  → CAUSALITY
  → INTENT
  → PROOF
  → AUTONOMY
```

| Layer | Meaning | Atlas 3 must |
|---|---|---|
| Evidence | Imported sources, events, conversations, CI, deployments | Reuse lineage, quarantine, secrets |
| Truth | Claims, authority, conflicts, UNKNOWN | Reuse Truth Core; never let LLM text skip this |
| Time | Valid-from / valid-to / observed-at / recorded-at | Reuse AS-2.0-TEMPORAL-001; no second engine |
| Causality | What caused what | New derived graph; provenance required |
| Intent | What was decided / planned vs what is | Separate from current state |
| Proof | Independent evidence of work | `AGENT_PROOF`; model claim ≠ proof |
| Autonomy | Governed action | Reuse DAG / leases / owner gates; no self-merge |

## Product shape

Atlas 3 is:

- a **project digital twin** (nodes + provenanced relationships + time)
- a **universal event ledger** over engineering and conversational evidence
- a **cross-LLM memory** that never becomes Truth Core by capture alone
- a **bounded context compiler** (`atlas start`) with an explicit token budget
- a **pulse** of what changed, matters, went stale, conflicts, failed, or was decided
- a **proof-of-work** chain from task through post-merge

Atlas 3 is not:

- a second truth engine
- a UI-invented model
- a scrape-the-provider-history product
- an autonomous merger
- a claim that `FULL_LIVE_DEMO_READY = YES`

## First product vertical

```text
AT3-003 Engineering Event Model
  → AT3-014 Universal Event Ledger
  → AT3-015 Atlas Pulse
  → AT3-030 Atlas Start
  → AT3-050 Agent Proof-of-Work
```

Do not start organization / enterprise waves before this slice works.

D-192 first memory vertical (parallel, isolated):

```text
ChatGPT export
  → canonical envelope
  → knowledge extraction
  → deduplication
  → freshness
  → memory search
  → AT3-054 Context Compiler consume-only
```

Then prove provider neutrality with Claude, then Gemini, without changing
Truth Core semantics.

## Reuse mandate

Every Atlas 3 proposal states:

```text
REUSED_COMPONENTS =
NEW_COMPONENTS =
MIGRATION_REQUIRED =
COMPATIBILITY_RISK =
```

See [ARCHITECTURE.md](ARCHITECTURE.md) for the program-level reuse map.

## Demo isolation

Current FULL_LIVE_DEMO closure outranks Atlas 3 runtime mutation of certified
surfaces.

```text
If demo closure and Atlas 3 work overlap:
  CURRENT_DEMO_CLOSURE_WINS.
```

`FULL_LIVE_DEMO_READY` is **NO** on this main pin. Atlas 3 may prepare isolated
packages. It must not destabilize demo-critical 2.x surfaces.

## Honesty stamps

```text
PREP != IMPLEMENTED
DEMO_FIXTURE != AUTHENTIC_PILOT
DEMO != RELEASE
UI != CANONICAL TRUTH
MODEL OUTPUT != AUTHORITY
CONVERSATION != TRUTH CORE
PROVIDER MEMORY != PROJECT REALITY
GRAPH != AUTHORITY
PROMOTE_ELIGIBLE != MERGED
MERGE_AUTHORIZATION = NOT_GRANTED
```
