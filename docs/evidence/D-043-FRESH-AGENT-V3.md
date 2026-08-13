# D-043 Fresh Agent Challenge V3 — MEASUREMENT

**Directive:** D-PROJECT-ATLAS-CODER-ALPHA-043  
**Mode:** MEASUREMENT ONLY (no feature work)  
**Vault:** `/tmp/atlas-dogfood-d043/.atlas-vault`  
**Project:** `project-atlas`  
**Handoff:** `handoff-56743f61920059e8` (`operator_note`: D-043 V3)

## Honesty stamps

```
DEMO_FIXTURE != AUTHENTIC_PILOT
CODEX_VALIDATED = NO
ATLAS_OPT_WAKE_GATE = CLOSED
UI != CANONICAL
MODEL_OUTPUT != AUTHORITY
lens_is_authority = false
authentic_pilot = false
fabricated_fields = false
unknown_is_valid = true
release_certified = false
```

## Method

1. Used the prepared vault at `/tmp/atlas-dogfood-d043/.atlas-vault` (Atlas context already exported).
2. Answered using **only** these Atlas-generated artifacts (no `/workspace` source browse for answers):
   - `generated/ops/project-brief-project-atlas.json`
   - `generated/answers/ans-architecture-project-atlas.json`
   - `generated/answers/ans-decisions-project-atlas.json`
   - `generated/ops/agent-context/project-atlas.md`
   - `generated/ops/agent-context/project-atlas.json`
   - `generated/ops/handoffs/latest.json` → `handoff-56743f61920059e8.json`
3. Truth-check against repository occurred **after** pack-only answers, for scoring only.
4. Especially verified: `knowledge_compiler.py` spelling; `docs/plan.md` not listed as a Core module; ACTIVE_GOVERNING free of Context/Consequences/CLI-integration noise; attention package id + source-failure why answerable from pack.

Packages observed: `AS-CODER-ALPHA-BRIEF-001`, `AS-CODER-ALPHA-ARCH-002`, `AS-CODER-ALPHA-DECISIONS-001`, `AS-CODER-ALPHA-CONTEXT-001`, `AS-CODER-ALPHA-HANDOFF-001`, plus embedded `AS-CODER-ALPHA-ATTENTION-001` / `AS-CODER-ALPHA-SOURCE-HEALTH-001`.

---

## Fresh-agent answers (pack-only)

### 1. What is Project Atlas?
Project Atlas is the persistent brain for AI-native projects — Knowledge (Obsidian/Web), Context (agents), and Truth (evidence / provenance / conflicts / UNKNOWN). Primary promise: never explain your project to an AI twice (Coder Alpha north star / D-037). Tech stack: Python >=3.12 · pydantic, PyYAML, jsonschema.

### 2. What is the current product direction?
Coder Alpha north star: keep Atlas as the durable knowledge/context/truth substrate so agents do not re-learn the project each session. Architecture lens maturity signal: Atlas 1.0 complete; Atlas 2.0 release-certified; Atlas 2.1 is the live productization layer (read-only MCP and ChatGPT bridge under explicit truth boundaries); Atlas 2.2 work is prep-framed (Reality Gap / ADV pool ADRs).

### 3. Describe the architecture accurately.
Three-layer knowledge pipeline: Layer A original docs imported with minimal modification; Layer B structured OKF concept documents generated from sources; Layer C cross-project / portfolio views synthesized from the canonical layer. Control flow: `atlas discover → ingest → build-indexes → build-portfolio → validate`, with read-only lenses (`query`, `ask2`, `kdiff`, `overview`, `state`). Evidence stages: Discovery → Classification → Extraction → Normalization → Linking → Contradiction detection. Trust boundary: no claim without a traceable source. Major Core modules from pack: `cli.py`, `config.py`, `scaffold.py`, `discovery.py`, `ingestion.py`, `indexes.py`, `portfolio.py`, `validation.py`, `doctor.py`, `knowledge_compiler.py`, `retrieval.py`. Known gap note: `atlas-vault-documentation/` out of scope for the Core commands listed.

### 4. Which decisions govern current work?
`decisions=24; active_governing=14`. ACTIVE_GOVERNING from decisions lens:
1. JSON schemas ship as package data (not top-level `schemas/`)
2. Scaffold generation embeds no wall-clock timestamps
3. ADR-001 — WP-001 foundation decisions
4. ADR-002 — Atlas two-track platform reconciliation
5. ADR-003 — Governed agent-event ingestion contract
6. ADR-005 — MVP portfolio intelligence and pilot onboarding closure
7. ADR-006 — GitHub Repository Governance Baseline
8. ADR-007 — Claim Identity v2 canonicalization
9. ADR-008 — Atlas Web Application foundation
10. ADR-009 — Atlas Web design tokens (design-lab)
11. ADR-010 — Atlas Web UX (production shell vs design-lab)
12. ADR-025 — Research workspace + Ask Atlas 2 prep (SAFE pre-v2.1.0)
13. ADR-028 — Reality Gap prep (Atlas 2.2)
14. ADR-031 — Atlas 2.2 ADV pool prep (threat matrix)

No Context / Consequences / CLI integration section-noise titles appear in ACTIVE_GOVERNING.

### 5. What materially changed?
**UNKNOWN** (honest). Pack: “No prior connect inventory; baseline established (UNKNOWN history).”

### 6. What currently requires attention?
Attention rollup=`BLOCKING` (`AS-CODER-ALPHA-ATTENTION-001`). Brief state: rollup=attention; unresolved_conflicts=10; pending_reviews=317; claims_withheld=11; sources_failed=258; lifecycle=unknown; coverage_absent=decisions,deployment,operations,setup,troubleshooting. care_about_count=7: primarily BLOCKING unresolved competing claims in `review/conflicts` (canonical field untrusted until disposition; do `atlas review decide`) plus NEEDS_HUMAN_REVIEW pending samples. source_failure_total=258 not hidden; collapsed for triage.

### 7. Why are important sources failing?
Answerable from pack Source health (`AS-CODER-ALPHA-SOURCE-HEALTH-001`): compile_failed=258 (also compile_partial=3, excluded=10972, quarantined=9; source_count=11242). Sample rows carry reason `compile_failed` / status `FAILED` — “Knowledge compile marked this source FAILED”; next=inspect diagnostics and repair source structure/metadata. Sample paths: `.cursor/environment.json`, `apps/web/index.html`, `apps/web/package.json`, lockfile, sample mission-control JSON fixtures.

### 8. What should be done next?
From brief / agent context suggested_next_work:
1. Resolve unresolved conflicts in `review/conflicts`
2. Triage pending human reviews in `review/pending`
3. Add source evidence for absent coverage: decisions, deployment, operations, setup, troubleshooting
4. Re-run `atlas connect` after edits to populate What Changed  
Handoff resume: read agent-context before coding; treat UNKNOWN as UNKNOWN; prefer vault Truth Core; after meaningful work run `atlas capture record` then `atlas handoff create`.

### 9. What remains UNKNOWN?
Change history UNKNOWN (baseline first connect); lifecycle=unknown; OPT wake gate CLOSED; authentic_pilot false; lens≠authority; session captures UNKNOWN (none yet); coverage gaps listed above; unresolved conflicts/pending reviews remain open dispositions rather than settled truth.

### 10. Which statements are proposals rather than decisions?
OPEN_PROPOSED (not ACTIVE_GOVERNING), all from `docs/architecture-governance/VERIFY-AS-RET-SEQUENCING-DECISION.md`:
- Option 1 selected
- Option Disposition
- VERIFY / AS-RET Sequencing Decision  
Also present but not governing: SUPERSEDED claim `formally-close-verify-as-superseded`; REJECTED “Alternatives rejected” / “Option 2 rejected”.

### Bounded task (pack-only)

**Task:** Locate where `atlas attention` is implemented and state its package id. Then state how care_about triage works in one sentence.

**Pack-only answer:**
- Implementation: `src/project_atlas/attention_hygiene.py`
- Package id: `AS-CODER-ALPHA-ATTENTION-001`
- CLI: `atlas attention`
- care_about triage (one sentence): It surfaces a small capped set of actionable BLOCKING / NEEDS_HUMAN_REVIEW items (here care_about_count=7) while collapsing bulk source failures (source_failure_total=258) for triage without hiding the failure count.

**FRESH_AGENT_TASK_START = PASS**

---

## Verification checks (pack vs challenge gates)

| Check | Result |
|---|---|
| `major_components` uses `knowledge_compiler.py` (not `knowledgecompiler.py`) | PASS |
| `docs/plan.md` is not listed as a Core module | PASS (`docs/plan.md` appears only as evidence/link, not in major_components) |
| ACTIVE_GOVERNING excludes Context/Consequences/CLI integration noise | PASS (14 ADR/foundation titles only) |
| Attention package id answerable from pack | PASS (`AS-CODER-ALPHA-ATTENTION-001`) |
| Source failure why answerable from pack | PASS (`compile_failed` / Knowledge compile marked FAILED + paths) |

---

## Truth comparison (brief, post-answers only)

| Signal | Pack-only fresh agent | Repository truth (post-score check) |
|---|---|---|
| Purpose / identity | Persistent brain; never explain twice | Matches Coder Alpha north star narrative |
| Three-layer architecture | Correct | Matches vault model principles |
| `knowledge_compiler.py` | Correct underscore spelling | Matches `src/project_atlas/knowledge_compiler.py` |
| Governing decisions | 14 clean ACTIVE_GOVERNING ADR/foundation titles | Matches decisions lens; no section-header noise |
| Attention locate | `attention_hygiene.py` · `AS-CODER-ALPHA-ATTENTION-001` | Matches module docstring / `PACKAGE_ID` |
| care_about triage | Cap actionable items; collapse source failures | Matches attention_hygiene care_about limits + collapse wording |
| Source failure why | compile_failed / Knowledge compile marked FAILED | Matches embedded source-health surface |
| Recent changes | Honest UNKNOWN baseline | Expected for first-connect dogfood |

---

## Scored metrics

```
FRESH_AGENT_FACTUAL_ERRORS = 0
  # Prior V2 pack errors cleared in this vault pack:
  # - no knowledgecompiler.py mangling
  # - docs/plan.md not presented as a Core module
  # - no Context/Consequences/CLI-integration ACTIVE_GOVERNING noise

FRESH_AGENT_REEXPLANATION_REQUIRED = NO
  # Challenge questions + bounded attention task are answerable from the collected
  # Atlas artifacts without owner/repo re-explanation. Remaining UNKNOWN change
  # history is honest baseline, not missing explanation of the product.

FRESH_AGENT_TASK_START = PASS
  # Bounded task answered from agent-context Attention section alone.

FRESH_AGENT_CONTEXT_SUFFICIENCY = PASS
  # Enough for identity, product direction, accurate architecture components,
  # clean governing decisions, attention triage, source-failure why, next work,
  # UNKNOWN inventory, and proposal-vs-decision separation.
  # Residual truncations in some architecture prose slots do not block correct answers.

CODER_ALPHA_ACCEPTANCE = PASS
  # Based ONLY on this V3 Fresh Agent Challenge measurement (not AUTHENTIC_PILOT,
  # not release certification, not OPT wake). Metrics: 0 factual errors,
  # REEXPLANATION_REQUIRED=NO, TASK_START=PASS, CONTEXT_SUFFICIENCY=PASS,
  # and all listed verification gates PASS.
```

## Question scorecard

| # | Question | Score | Notes |
|---|---|---|---|
| 1 | What is Project Atlas? | PASS | North-star purpose accurate |
| 2 | Current product direction | PASS | North star + 2.1/2.2 maturity framing from pack |
| 3 | Architecture | PASS | Three-layer + pipeline + correct major_components |
| 4 | Governing decisions | PASS | 14 clean ACTIVE_GOVERNING; proposals separated |
| 5 | What changed | PASS-HONEST | UNKNOWN baseline correct |
| 6 | Requires attention | PASS | BLOCKING care_about + conflict/review/source posture |
| 7 | Sources failing + why | PASS | Counts + compile_failed reason + sample paths |
| 8 | Next work | PASS | Matches suggested_next_work + handoff resume |
| 9 | Remains UNKNOWN | PASS | Honest UNKNOWN + conflict/coverage gaps |
| 10 | Proposals vs decisions | PASS | OPEN_PROPOSED VERIFY/AS-RET items identified |
| — | Bounded attention locate + care_about | PASS | Path, package id, triage sentence from pack |

## Non-claims

- This run is dogfood measurement, not AUTHENTIC_PILOT.
- No new product features implemented in this measurement step.
- `CODEX_VALIDATED = NO`.
- `ATLAS_OPT_WAKE_GATE = CLOSED`.
- Acceptance PASS above is **challenge-scoped only** (Fresh Agent V3 metrics), not a claim that Atlas is release-certified or that OPT wake is open.
