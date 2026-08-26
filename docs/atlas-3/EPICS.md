# Atlas 3.0 — Epics

| Field | Value |
|---|---|
| Directive | D-191 / D-192 / D-193 |
| Epic count | **61** |
| First vertical | AT3-003, AT3-014, AT3-015, AT3-030, AT3-050 |
| Foundation priority | AT3-001, 002, 003, 004, 005, 014, 015, 030, 035, 050 |

Status vocabulary: `PREP` · `ISOLATED_RUNTIME` · `LANDED_2X_REUSE` · `BLOCKED_DEMO` · `NOT_STARTED`.

`ISOLATED_RUNTIME` means code exists under `src/project_atlas/atlas3/` and
does not mutate certified 2.x production surfaces.

## Wave A — Foundation

| ID | Title | Status | Reuse |
|---|---|---|---|
| AT3-001 | Program charter / north star | PREP (this tree + FOUNDATION.md) | Coder Alpha north star |
| AT3-002 | Project twin schema | ISOLATED_RUNTIME | constructors + JSON schemas; graph ≠ authority |
| AT3-003 | Engineering event model | ISOLATED_RUNTIME | canonical envelope; `kind` remains alias |
| AT3-004 | Capability registry | ISOLATED_RUNTIME | D-193 remap; surfaces ≠ capabilities |
| AT3-005 | 2.x→3.x compatibility contract | ISOLATED_RUNTIME | D-193 remap; `prove_compatibility()` |
| AT3-006 | Program security / threat model | PREP + catalog | `SECURITY.md`; catalog ≠ certification |

D-191 used AT3-004 for temporal reuse and AT3-005 for authority reuse.
Those remain **LANDED_2X_REUSE constraints** in `FOUNDATION.md` (no second
clock, no second Truth Core). They were not dropped.

## Wave B — Engineering estate

| ID | Title | Status | Reuse |
|---|---|---|---|
| AT3-010 | Repository / component inventory | ISOLATED_RUNTIME | declared inventory; graph != authority |
| AT3-011 | File / symbol graph | ISOLATED_RUNTIME | declared graph; no host walk |
| AT3-012 | Service / environment nodes | ISOLATED_RUNTIME | declared fixture; not authentic estate |
| AT3-013 | PR / commit / test / build nodes | ISOLATED_RUNTIME | ledger projection; no invented git |
| AT3-014 | Universal event ledger | ISOLATED_RUNTIME | new store; do not dual-write ops_events |

## Wave C — Truth Graph 2

| ID | Title | Status | Reuse |
|---|---|---|---|
| AT3-020 | Claim / decision / requirement nodes | LANDED_2X_REUSE | claims, decisions lens |
| AT3-021 | Derived relationship expansion | ISOLATED_RUNTIME | AS-GRAPH-003 aliases; no store write |
| AT3-022 | Conflict / UNKNOWN projection | LANDED_2X_REUSE | conflicts, unknown lens |
| AT3-023 | Graph ≠ authority enforcement | LANDED_2X_REUSE | GRAPH-001–005 invariants |

## Wave D — Universal agent memory (D-192)

| ID | Title | Status | Reuse |
|---|---|---|---|
| AT3-035 | Universal LLM connector framework | ISOLATED_RUNTIME | provider_adapters, conversation_capture |
| AT3-036 | ChatGPT knowledge sync | ISOLATED_RUNTIME | chatgpt_bridge compose; parse_chat_export |
| AT3-037 | Claude knowledge sync | ISOLATED_RUNTIME | export ingest; no history API claimed |
| AT3-038 | Gemini knowledge sync | ISOLATED_RUNTIME | export ingest; no history API claimed |
| AT3-039 | Cross-provider conversation normalization | ISOLATED_RUNTIME | canonical envelope |
| AT3-040 | Conversation knowledge extractor | ISOLATED_RUNTIME | existing ITEM_TYPES |
| AT3-041 | Cross-LLM deduplication | ISOLATED_RUNTIME | content-hash + normalized text |
| AT3-042 | Cross-LLM conflict detection | ISOLATED_RUNTIME | do not collapse state/intent/history |
| AT3-043 | Conversation decision + intent extraction | ISOLATED_RUNTIME | owner_origin contract; INTENT != CURRENT STATE |
| AT3-044 | Memory freshness + invalidation | ISOLATED_RUNTIME | temporal reuse |
| AT3-045 | Provider identity + session lineage | ISOLATED_RUNTIME | conversation ids + hashes; provider spoof fails closed |
| AT3-046 | Incremental conversation sync | NOT_STARTED | ChatGPT live sync still NOT general |
| AT3-047 | Privacy / consent / retention | ISOLATED_RUNTIME | secrets + minimize raw transcript |
| AT3-048 | Unified LLM memory search | ISOLATED_RUNTIME | search extracted items, not dumps |
| AT3-049 | Cross-LLM memory reconciliation | ISOLATED_RUNTIME | compose 041/042/044; no auto-promote |

## Wave E — Causality and intent

| ID | Title | Status |
|---|---|---|
| AT3-060 | Causal graph (CAUSED_BY) | ISOLATED_RUNTIME |
| AT3-061 | Intent vs current-state separation | ISOLATED_RUNTIME |
| AT3-062 | DECIDED_BY provenance | ISOLATED_RUNTIME |

## Wave F — Proof and autonomy

| ID | Title | Status | Reuse |
|---|---|---|---|
| AT3-050 | Agent proof-of-work | ISOLATED_RUNTIME | orch receipts; not local_proof CLI |
| AT3-051 | Independent verification binding | ISOLATED_RUNTIME | AS-ORCH result envelope |
| AT3-052 | ADV binding | ISOLATED_RUNTIME | adv_release_cert |
| AT3-053 | Autonomy gate reuse | LANDED_2X_REUSE | DAG, leases, owner gates |

## Wave G — Interoperability

| ID | Title | Status |
|---|---|---|
| AT3-070 | Surface contract (CLI/API/Web/TUI/MCP/A2A) | ISOLATED_RUNTIME |
| AT3-071 | Transport ≠ authority | ISOLATED_RUNTIME |
| AT3-072 | Provider register / capabilities CLI design | ISOLATED_RUNTIME |

## Wave H — Project intelligence

| ID | Title | Status |
|---|---|---|
| AT3-080 | Impact explorer data | ISOLATED_RUNTIME |
| AT3-081 | Stale / conflict intelligence | ISOLATED_RUNTIME (Pulse + memory) |
| AT3-082 | Next-action honesty | LANDED_2X_REUSE (next lens; Pulse composes) |

## Wave I — Product experience

| ID | Title | Status |
|---|---|---|
| AT3-015 | Atlas Pulse | ISOLATED_RUNTIME |
| AT3-030 | Atlas Start | ISOLATED_RUNTIME |
| AT3-090 | Atlas Home | ISOLATED_RUNTIME |
| AT3-091 | Timeline | ISOLATED_RUNTIME |
| AT3-092 | Truth Graph UX | NOT_STARTED |
| AT3-093 | Time Machine UX reuse | LANDED_2X_REUSE (kdiff / web) |
| AT3-094 | Decision Explorer | NOT_STARTED |
| AT3-095 | Impact Explorer | NOT_STARTED |
| AT3-096 | Mission Command Center | NOT_STARTED |

## Wave J — Observability

| ID | Title | Status |
|---|---|---|
| AT3-100 | Twin health | ISOLATED_RUNTIME |
| AT3-101 | Ledger observability | ISOLATED_RUNTIME (list/status) |
| AT3-102 | Provider sync status | ISOLATED_RUNTIME (honest capability states) |

## Wave K — Organization twin

| ID | Title | Status |
|---|---|---|
| AT3-110 | Multi-project twin | NOT_STARTED — blocked on first vertical + federation honesty |
| AT3-111 | Org identity | NOT_STARTED |
| AT3-112 | Federation reuse | LANDED_2X_REUSE (federation lens; not authority) |

## Wave L — Ecosystem / enterprise

| ID | Title | Status |
|---|---|---|
| AT3-120 | Third-party provider adapters | NOT_STARTED |
| AT3-121 | Knowledge marketplace | NOT_STARTED — remains speculative (NS-3.0-008) |
| AT3-122 | Enterprise policy-as-code | NOT_STARTED |

## Count

61 unique epics (AT3-001…006, 010…015, 020…023, 030, 035…053, 060…062, 070…072, 080…082, 090…096, 100…102, 110…112, 120…122).
