# D-040 Fresh Agent Challenge V2 — MEASUREMENT

**Directive:** D-PROJECT-ATLAS-CODER-ALPHA-040  
**Mode:** MEASUREMENT ONLY (no feature work)  
**Vault:** `/tmp/atlas-dogfood-d040/.atlas-vault`  
**Project:** `project-atlas`  
**Handoff:** `handoff-56743f61920059e8`

## Honesty stamps

```
DEMO_FIXTURE != AUTHENTIC_PILOT
CODEX_VALIDATED = NO
ATLAS_OPT_WAKE_GATE = CLOSED
UI != CANONICAL
MODEL_OUTPUT != AUTHORITY
lens_is_authority = false
authentic_pilot = false
```

## Method

1. Rematerialized architecture + brief (`refresh=False` on brief).
2. Exported agent context: `atlas context --no-refresh`.
3. Created handoff pack: `atlas handoff create --no-refresh --no-capture`.
4. Simulated fresh agent answered 10 questions using **only** Atlas-generated context files below (no `/workspace` source browse for answers).
5. Compared answers briefly to repository truth (`AGENTS.md`, dogfood metrics) for scoring only.

## Collected Atlas artifacts (exclusive answer set)

| Artifact | Path |
|---|---|
| Project brief JSON | `generated/ops/project-brief-project-atlas.json` |
| Architecture lens | `generated/answers/ans-architecture-project-atlas.json` |
| Agent context markdown | `generated/ops/agent-context/project-atlas.md` |
| Agent context JSON | `generated/ops/agent-context/project-atlas.json` |
| Handoff pack | `generated/ops/handoffs/handoff-56743f61920059e8.json` |
| Handoff latest pointer | `generated/ops/handoffs/latest.json` |

Packages observed: `AS-CODER-ALPHA-BRIEF-001`, `AS-CODER-ALPHA-ARCH-002`, `AS-CODER-ALPHA-CONTEXT-001`, `AS-CODER-ALPHA-HANDOFF-001`.

---

## Fresh-agent answers (pack-only)

### 1. What is Project Atlas?
Project Atlas is the persistent brain for AI-native projects — Knowledge (Obsidian/Web), Context (agents), and Truth (evidence / provenance / conflicts / UNKNOWN). Primary promise: never explain your project to an AI twice (Coder Alpha north star / D-037). Tech stack: Python >=3.12 · pydantic, PyYAML, jsonschema.

### 2. What problem does it solve?
Converts fragmented / scattered project documentation into a source-backed, continuously maintained Open Knowledge Format portfolio / knowledge control plane — so humans and agents do not re-explain the project each session. Architecture lens: vault should not become another archive of copied documents.

### 3. Describe its architecture.
Three-layer vault knowledge pipeline: Layer A source evidence; Layer B canonical OKF knowledge; Layer C portfolio intelligence. Core control flow: `atlas discover → ingest → build-indexes → build-portfolio → validate`, with read-only lenses (`query`, `ask2`, `kdiff`, `overview`, `state`). Evidence pipeline: Discovery → Classification → Extraction → Normalization → Linking → Contradiction detection. Trust boundary: no claim without a traceable source.

### 4. What are its major components and boundaries?
Pack lists Core modules: `cli.py`, `config.py`, `scaffold.py`, `discovery.py`, `ingestion.py`, `indexes.py`, `portfolio.py`, `validation.py`, `doctor.py`, `knowledgecompiler.py`, plus `retrieval.py`. Surfaces mentioned: Obsidian; integrations include Git, Google Drive, Markdown vaults, PDFs/Word. Known gap note (truncated): `atlas-vault-documentation/` out of scope for Core commands; missing provenance / required project documents. Product maturity in lens: Atlas 1.0 complete; 2.0 release-certified; 2.1 live productization (MCP/ChatGPT bridge under truth boundaries).

### 5. What materially changed recently?
**UNKNOWN** (honest). Pack: “No prior connect inventory; baseline established (UNKNOWN history).”

### 6. Which decisions currently govern the project?
Pack: `decisions=17; active_governing=12`. Named ACTIVE_GOVERNING signals include ADR-001 (WP-001 foundation; JSON schemas as package data; no wall-clock timestamps in scaffold) and ADR-002 (two-track platform reconciliation). Pack also lists noisy labels (“Context”, “Consequences”, “Decision”, “Migration and validation”) as ACTIVE_GOVERNING — treated as pack noise, not trusted decision titles.

### 7. Which problems actually require attention?
Rollup conflict/attention: unresolved_conflicts=10; pending_reviews=316; claims_withheld=11; sources_failed=258; lifecycle=unknown; coverage_absent=decisions,deployment,operations,setup,troubleshooting. Suggested next work aligns: resolve conflicts, triage pending reviews, add evidence for absent coverage, re-run connect for What Changed.

### 8. Are any sources missing/failing, and why?
Yes — pack reports `sources_failed=258` (and `sources_complete=587`). **Why: UNKNOWN from this pack** (counts only; no source-health reason codes/paths in brief/context/architecture/handoff).

### 9. What should be worked on next?
1. Resolve unresolved conflicts in `review/conflicts`  
2. Triage pending human reviews in `review/pending`  
3. Add source evidence for absent coverage: decisions, deployment, operations, setup, troubleshooting  
4. Re-run `atlas connect` after edits to populate What Changed  

### 10. What remains UNKNOWN or conflicting?
Change history UNKNOWN; lifecycle unknown; 10 unresolved conflicts; 316 pending reviews; 11 claims withheld; 258 failed sources without explainability in this pack; coverage gaps listed above; OPT wake gate CLOSED; authentic_pilot false; lens≠authority.

### Bounded task (pack-only attempt)
**Task:** Locate where `atlas attention` is implemented and state its package id.  
**Pack-only answer:** **UNKNOWN.** None of the collected artifacts name `attention_hygiene`, `atlas attention`, or `AS-CODER-ALPHA-ATTENTION-001`. Fresh agent cannot start this code task from the handoff pack alone.

---

## Truth comparison (brief, post-answers)

| Signal | Pack-only fresh agent | Repository / dogfood truth |
|---|---|---|
| Purpose / identity | Persistent brain; never explain twice | Matches `AGENTS.md` Coder Alpha north star |
| Three-layer architecture | Correct | Matches `AGENTS.md` / plan principles |
| Recent changes | Honest UNKNOWN | Dogfood `MEANINGFUL_CHANGES_RECALL = N/A_BASELINE_FIRST_CONNECT` |
| Attention location | UNKNOWN | `src/project_atlas/attention_hygiene.py` · `AS-CODER-ALPHA-ATTENTION-001` |
| Source failure why | UNKNOWN in pack | Dogfood `SOURCE_FAILURE_EXPLAINABILITY = PASS` via separate `source-health` surface (not in collected pack) |
| Architecture module list | Partial / noisy | Real modules include `attention_hygiene`, `knowledge_compiler` (underscore), `retrieval`, etc.; pack truncates and mis-lists `docs/plan.md` as a module |

---

## Scored metrics

```
FRESH_AGENT_CONTEXT_SUFFICIENCY = PARTIAL
  # Enough for identity, purpose, state/attention rollup, next-work triage posture.
  # Insufficient for precise architecture inventory, decision titles, source-failure why,
  # and locating implementation package ids (e.g. attention).

FRESH_AGENT_FACTUAL_ERRORS = 3
  1. Architecture major_components treats docs/plan.md / atlas-project.yaml as "Core package modules"
  2. Module/path mangling in pack: knowledgecompiler.py; src/projectatlas/ (missing underscore)
  3. Decision lens noise promoted into brief as ACTIVE_GOVERNING ("Context", "Consequences", "Decision", "Migration and validation")

FRESH_AGENT_MISSING_CONTEXT =
  - AS-CODER-ALPHA-ATTENTION-001 implementation path/package id
  - Source-failure reason codes / explainability (source-health)
  - Clean governing decision inventory (without section-header noise)
  - Non-truncated architecture slots / complete component responsibilities
  - Meaningful change history (baseline UNKNOWN — expected)
  - Explicit sibling boundary detail for atlas-vault-documentation/ control plane

FRESH_AGENT_REEXPLANATION_REQUIRED = YES
  # Owner/repo browse still required for architecture precision, source-failure why,
  # and any code-locate task such as attention package id.

FRESH_AGENT_TASK_START = FAIL
  # Bounded task "Locate atlas attention + package id" cannot be answered from
  # brief/architecture/context/handoff artifacts alone.
```

## Question scorecard (vs truth)

| # | Question | Score | Notes |
|---|---|---|---|
| 1 | What is Project Atlas? | PASS | North-star purpose accurate |
| 2 | Problem solved | PASS | Knowledge compiler / no re-explain |
| 3 | Architecture | PARTIAL | Three-layer + pipeline correct; truncated/noisy |
| 4 | Components/boundaries | PARTIAL | Core idea present; wrong/mangled module list |
| 5 | What changed | PASS-HONEST | UNKNOWN baseline correct |
| 6 | Governing decisions | PARTIAL | ADR-001/002 real; header noise |
| 7 | Problems needing attention | PASS | Conflicts/reviews/sources/coverage match dogfood attention posture |
| 8 | Sources failing + why | PARTIAL | Count yes; why UNKNOWN in pack |
| 9 | Next work | PASS | Matches suggested_next_work |
| 10 | UNKNOWN/conflicting | PASS | Honest UNKNOWN + conflict counts |

## Non-claims

- This run is dogfood measurement, not AUTHENTIC_PILOT.
- No new features implemented.
- Handoff success for pack creation: YES (`handoff-56743f61920059e8`).
- `CODEX_VALIDATED = NO`.

---

## REVISED scores (post attention/source-health embed in agent context)

**Re-score trigger:** Agent context now embeds Attention + Source health sections (`AS-CODER-ALPHA-ATTENTION-001`, `AS-CODER-ALPHA-SOURCE-HEALTH-001`). Pack-only re-read of:

- `generated/ops/agent-context/project-atlas.md`
- `generated/ops/agent-context/project-atlas.json`
- `generated/ops/project-brief-project-atlas.json`
- `generated/answers/ans-architecture-project-atlas.json`

### Bounded task (pack-only, revised)

**Task:** Locate where `atlas attention` is implemented and state its package id.  
**Pack-only answer:** `src/project_atlas/attention_hygiene.py` · package `AS-CODER-ALPHA-ATTENTION-001` (CLI `atlas attention`).  
**FRESH_AGENT_TASK_START = PASS**

### Q7 re-check (attention)

Problems requiring action are explicit in context Attention section: rollup=`BLOCKING`; item_count=274; top items are unresolved competing claims in `review/conflicts` (matter=canonical field untrusted until disposition; do=`atlas review decide`). Aligns with brief rollup (conflicts=10, pending_reviews=316, sources_failed=258, coverage_absent=…). **Score remains PASS** (richer evidence).

### Q8 re-check (source failures + why)

Yes — `compile_failed=258` (also compile_partial=3, excluded=10903, quarantined=9; source_count=11173). **Why now in pack:** reason code `compile_failed` / status `FAILED` — “Knowledge compile marked this source FAILED”; next=inspect diagnostics and repair source structure/metadata; sample paths include `.cursor/environment.json`, `apps/web/index.html`, `apps/web/package.json`, etc. Package `AS-CODER-ALPHA-SOURCE-HEALTH-001` · `src/project_atlas/source_health.py`. **Score: PARTIAL → PASS** (count + reason codes/paths answerable from pack; deeper root-cause still via diagnostics).

### Revised scored metrics

```
FRESH_AGENT_CONTEXT_SUFFICIENCY = PARTIAL
  # Improved: attention package/path + source-health why now in agent context.
  # Still insufficient for precise architecture inventory and clean decision titles.

FRESH_AGENT_FACTUAL_ERRORS = 3
  1. Architecture major_components treats docs/plan.md / atlas-project.yaml as "Core package modules"
  2. Module/path mangling in pack: knowledgecompiler.py; src/projectatlas/ (missing underscore)
  3. Decision lens noise promoted into brief as ACTIVE_GOVERNING ("Context", "Consequences", "Decision", "Migration and validation")

FRESH_AGENT_MISSING_CONTEXT =
  - Clean governing decision inventory (without section-header noise)
  - Non-truncated architecture slots / complete component responsibilities
  - Meaningful change history (baseline UNKNOWN — expected)
  - Explicit sibling boundary detail for atlas-vault-documentation/ control plane
  # REMOVED vs V2 baseline: attention package/path; source-failure why (now embedded)

FRESH_AGENT_REEXPLANATION_REQUIRED = YES
  # Owner/repo browse still required for architecture precision and decision-title cleanup.
  # No longer required for attention locate or source-failure why (embedded in context).

FRESH_AGENT_TASK_START = PASS
  # Bounded task answerable from agent-context alone:
  # attention_hygiene.py + AS-CODER-ALPHA-ATTENTION-001

CODER_ALPHA_ACCEPTANCE = NOT_CLAIMED
  # Do not invent PASS; architecture/decision noise and REEXPLANATION_REQUIRED=YES remain.
```

### Revised question scorecard (delta)

| # | Question | Prior | Revised | Notes |
|---|---|---|---|---|
| 7 | Problems needing attention | PASS | PASS | Attention section adds BLOCKING items + package id |
| 8 | Sources failing + why | PARTIAL | PASS | Source-health reason codes/paths in context |
| — | Bounded attention locate | FAIL | PASS | Pack names `attention_hygiene.py` + `AS-CODER-ALPHA-ATTENTION-001` |
