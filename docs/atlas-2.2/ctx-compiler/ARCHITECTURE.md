# Context Compiler — architecture (PREP)

Status: **PREP ONLY**. Non-normative until schema freeze + unlock.
Package: **AS-2.2-CTX-COMPILER-001**.

## 1. Problem

Agents and operator surfaces need bounded, task-specific context. Dumping the
vault (or a static pack) into a model window fails on:

- authority inversion (generated/inferred crowding out primary evidence)
- stale evidence presented as current
- unresolved conflicts collapsed into false consensus
- unbounded token growth
- missing provenance (why was this item included?)

Existing `AS-2.0-CTX-001` packs prove **fixture-safe assembly with mandatory
provenance pointers**. They are **not** the full Context Compiler pipeline.

## 2. Pipeline

```text
┌─────────┐   ┌────────────┐   ┌───────────┐   ┌───────────┐
│  task   │ → │ candidates │ → │ authority │ → │ freshness │
└─────────┘   └────────────┘   └───────────┘   └───────────┘
                                                      │
┌─────────┐   ┌──────────┐   ┌───────────┐   ┌────────┴────────┐
│ package │ ← │  budget  │ ← │ relevance │ ← │    conflicts    │
└─────────┘   └──────────┘   └───────────┘   └─────────────────┘
```

| Stage | Input | Output | Fail-closed rules |
|---|---|---|---|
| **task** | profile + goal + scope pins | normalized task record | unknown profile → reject; invent-estate flag → reject |
| **candidates** | hybrid/lexical/index pointers | candidate set (unordered→sorted) | no candidate invention; empty set allowed |
| **authority** | candidates + Core authority levels | ranked / demoted set | never elevate inferred/generated over primary without review pointer |
| **freshness** | ranked set + freshness signals | fresh / stale / unknown labels | unknown ≠ fresh; stale may remain with label |
| **conflicts** | labelled set + conflict records | filtered set + conflict sidecars | no silent winner; both sides retained or excluded with reason |
| **relevance** | filtered set + profile weights | relevance-ordered set | profile cannot invent facts |
| **budget** | ordered set + token/byte/count caps | truncated set + overflow receipt | overflow must be explicit; hard cap fail option |
| **package** | truncated set | context package record | provenance + reason required per item |

Optional **privacy** filter runs before budget: secret-scan metadata hits and
sensitive path classes are excluded (metadata only; never log matched secrets).

## 3. Context item record (design)

Every supplied item must record at least:

| Field | Meaning |
|---|---|
| `source` / `ref` | provenance pointer (source/receipt/index/claim/concept) |
| `reason_included` | deterministic stage reason code |
| `authority` | objective authority level from Core (not a trust score) |
| `freshness` | `fresh` / `stale` / `unknown` |
| `project` | project identity pin when scoped |
| `conflict_state` | `none` / `unresolved` / `excluded` |

## 4. Relationship to existing substrate

| Substrate | Role |
|---|---|
| `project_atlas.retrieval` / hybrid plan | candidate generation (read-only) |
| Core authority evaluator | authority stage inputs |
| freshness / orphan validation | freshness stage inputs |
| conflict projections / review queues | conflict stage inputs |
| `AS-2.0-CTX-001` pack schema | **downstream package shape inspiration**; Compiler extends with pipeline receipt |
| Agent OS / Ask Atlas | consumers of packages (post-unlock) |

Compiler **reads** derived indexes and receipts. It **must not** call
`_promote`, mutate claims, or write Layer B notes.

## 5. Determinism

- Stable sort keys at every stage (id, then ref, then reason code)
- JSON `sort_keys=True`; no wall-clock in package bodies (NFR-001)
- Injected reference time only in tests (same pattern as freshness fixtures)
- Identical inputs → byte-identical packages

## 6. Non-goals (PREP + future impl)

- LLM as authority or conflict resolver
- Subjective numeric trust scores
- Automatic PILOT / estate fact invention
- Unbounded “include everything related”
- Shipping embeddings as required path

## 7. Threat notes (prep)

| Threat | Mitigation sketch |
|---|---|
| Prompt-injected source text enters package | retain quarantine/redaction; label untrusted source class |
| Authority spoof via fabricated primary | only Core-evaluated authority levels accepted |
| Budget DoS via huge candidate fan-out | hard caps + overflow fail-closed option |
| Secret leakage into agent context | privacy stage + `secrets.scan_text` metadata gate |

See also `docs/atlas-2.0/THREAT-MODEL.md` for shared Atlas threats.
