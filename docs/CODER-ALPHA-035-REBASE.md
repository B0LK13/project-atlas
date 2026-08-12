# D-PROJECT-ATLAS-CODER-ALPHA-035 — Product Rebase

| Field | Value |
|---|---|
| Directive | `D-PROJECT-ATLAS-CODER-ALPHA-035` |
| Base | `main` @ `322f55b` (pre-execution) |
| North star | **Project Atlas = the persistent brain for AI-native projects** |
| Pillars | Knowledge · Context · Truth |
| Primary promise | Never explain your project to an AI twice |
| Secondary promise | Never lose what you learned, decided, or built |

## Governance (unchanged)

- `ATLAS_OPT_WAKE_GATE = CLOSED`
- `EVALUATOR_STABLE = YES` (wake recommendation `OPEN_ELIGIBLE` is governance-only)
- AutoLab / Prime / RL = **NOT ACTIVATED**
- `DEMO_FIXTURE != AUTHENTIC_PILOT`
- `CODEX_VALIDATED = NO`
- `EXTERNAL_SECURITY_REVALIDATION_REQUIRED = YES`

---

## Phase 1 — Roadmap reconciliation

Classification vocabulary: `KEEP` | `REFRAME` | `SUPERSEDE` | `DEFER` | `EXTERNAL_BLOCKED`

| Package / gate | Status on `main` | Class | PRODUCT-IMPACT |
|---|---|---|---|
| **AS-MVP-001** | Code/fixtures on `main`; receipt still `merge_authorized: false` | **REFRAME** | Keep portfolio/stale/conflict telemetry as Knowledge/Truth health signals — not “MVP closure.” Receipt paperwork is owner debt; does not deliver persistent AI memory by itself. |
| **INT-013** | Unchecked; fixture waiver does not open authentic estate sync | **EXTERNAL_BLOCKED** | Real multi-project sync proves Truth outside fixtures. Requires owner-provisioned authentic roots; agents must not invent pilot estates. |
| **AS-GH-002** | Not started; AS-GH-001 artifacts already on `main` | **DEFER** | Repo process hygiene only. Zero leverage on Knowledge/Context/Truth or “never explain twice.” |
| **AS-OPT-GATE-001** | Merged (`#321`); wake gate **CLOSED** | **KEEP** | Safety boundary for any future experiment promotion. Guardrail ≠ product. |
| **OPEN_ELIGIBLE** | Governance recommendation only | **DEFER** | Not a product unlock. Durable project memory first. |
| **Atlas-OPT / AutoLab / RL / Prime** | Not activated | **DEFER** | Orthogonal and premature vs persistent Knowledge/Context/Truth. |
| **Authentic pilot** | `PILOT_ROOTS = 0`; dormant | **EXTERNAL_BLOCKED** | Required for honest claims over real projects. Owner supplies safe roots. |
| **`feat/as-core2-008/009/010`**, **`feat/as-int-010`**, **`feat/as-l-001`** | Tips are ancestors of / merged into `main` | **SUPERSEDE** | “Governor-held unmerged” narrative is obsolete. No merge campaigns. Optional remote branch cleanup only. |
| **`feat/as-mvp-001*`** | No remote heads | **SUPERSEDE** | Branch framing dead; treat as on-`main` + receipt/docs drift. |
| Stale backlog “GOVERNOR REQUIRED” tip claims | Many tips already on `main` | **SUPERSEDE** | Treat git ancestry as status; prose is docs debt, not a work queue. |
| `WEB APPLICATION ACCEPTED` | Signed YES | **SUPERSEDE** as open gate | Not an open owner hold. |
| ChatGPT hosted connector runtime | May remain blocked | **EXTERNAL_BLOCKED** | Non-core to Coder Alpha dogfood. |
| External security / Codex revalidation | Still required | **EXTERNAL_BLOCKED** | Process hold, not north-star feature work. |

### Honest remaining owner/external holds

1. Authentic pilot roots + **INT-013** estate sync  
2. **AS-GH-002** live GitHub settings  
3. AS-MVP-001 receipt certification flags  
4. External security / Codex revalidation  

Do **not** auto-merge historical owner-held branches. Do **not** wake Atlas-OPT.

---

## Phase 2 — Journey gap (summary)

Full table: `docs/evidence/D-PROJECT-ATLAS-CODER-ALPHA-035-phase2-journey-audit.md`

| Step | Status |
|---|---|
| Fresh project | PARTIAL (connect shipped) |
| `atlas connect .` | **IMPLEMENTED** (AS-CODER-ALPHA-CONNECT-001 on main) |
| Understands project | PARTIAL |
| Knowledge / Obsidian | PARTIAL |
| What is this / changed / decisions / unknown | PARTIAL |
| What next | MISSING |
| Cursor context | NOT_PRODUCTIZED |
| Auto session capture | PARTIAL |
| `atlas handoff` | MISSING |
| Agent resume | PARTIAL |
| Human updates back | PARTIAL |
| Same Truth Core | **IMPLEMENTED** |

Top dogfood gaps: (1) `atlas connect .`, (2) auto-materialize knowledge/ask surfaces from Core, (3) Cursor context + handoff + default session capture.

---

## Phase 3 — Coder Alpha backlog (smallest sequence)

Package prefix: `AS-CODER-ALPHA-*`. Obsidian remains the human PKM surface; Atlas owns intelligence + truth + structure.

| Order | ID | Deliverable | Unblocks |
|---|---|---|---|
| **A** | `AS-CODER-ALPHA-CONNECT-001` | `atlas connect .` — one-command bind + compile (init vault if needed → discover → ingest → SEC-002 rediscover → ingest → build-indexes → validate) | Fresh → understands |
| **B** | `AS-CODER-ALPHA-OVERVIEW-001` | Project Overview answer/projection from Core (`project.md` + claims) exposed via CLI/web without tribal flags | “What is this project?” |
| **C** | `AS-CODER-ALPHA-STATE-001` | Current State lens (lifecycle + pending reviews + freshness) | Current State |
| **D** | `AS-CODER-ALPHA-CHANGED-001` | Default “what changed?” (last connect → now) over kdiff/catalogs | What changed |
| **E** | `AS-CODER-ALPHA-DECISIONS-001` | Decision memory query over `decisions.md` / decision claims | Decisions that matter |
| **F** | `AS-CODER-ALPHA-UNKNOWN-001` | Bundled unknown/conflict/review inspection command | Honesty surface |
| **G** | `AS-CODER-ALPHA-CAPTURE-001` | Default meaningful session capture hooks (explicit → semi-auto) | Session memory |
| **H** | `AS-CODER-ALPHA-HANDOFF-001` | `atlas handoff create/resume` packs for cross-agent Continuity | Never explain twice |
| **I** | `AS-CODER-ALPHA-CONTEXT-001` | Agent context compiler/export for Cursor/Claude/Codex/ChatGPT | Cursor receives context |
| **J** | `AS-CODER-ALPHA-OBSIDIAN-001` | Living Obsidian projection (notes Atlas owns; humans edit protected regions) | Knowledge pillar |
| **K** | `AS-CODER-ALPHA-HUMAN-LOOP-001` | Owner decisions flowing back into Truth Core (review → promote, fail-closed) | Human → Truth |
| **L** | `AS-CODER-ALPHA-WEB-001` | Web Knowledge UX wired to Core (not DEMO_FIXTURE inventory) | Knowledge UX |
| **M** | `AS-CODER-ALPHA-TRUTH-UX-001` | Evidence/conflict/UNKNOWN inspection UI/CLI bundle | Truth pillar |

Non-goals: Obsidian clone; OPT wake; authentic pilot invention; merging superseded tip branches.

---

## Phase 4 — Dogfood contract

**Estate:** Project Atlas repository itself is the canonical Coder Alpha dogfood estate.

**Success criterion:** Owner starts a fresh Cursor/Claude/Codex/ChatGPT session without manually re-explaining Project Atlas context.

**Primary acceptance:** “I would notice immediately if Atlas disappeared from my coding workflow.”

### Metrics (instrument later; define now)

| Metric | Intent |
|---|---|
| `TIME_TO_USEFUL_CONTEXT` | Wall time from `atlas connect .` (or resume) to first useful overview/context pack |
| `REEXPLANATION_RATE` | Fraction of sessions where owner re-pastes project explanation |
| `HANDOFF_SUCCESS_RATE` | Fraction of handoff resume sessions that start with correct project identity + open decisions |
| `CONTEXT_ACCURACY` | Spot-check: context claims match vault Truth Core |
| `STALE_CONTEXT_RATE` | Context packs citing superseded claims / missing recent commits |
| `UNKNOWN_HONESTY` | Unknown/conflict surfaced rather than invented answers |
| `MEANINGFUL_CHANGES_CAPTURED` | Sessions with capture receipts for real work |
| `USER_CORRECTIONS_REQUIRED` | Owner edits needed to correct Atlas after a session |
| `MISTAKES_PREVENTED` | Documented cases where Atlas blocked stale/wrong guidance |

Honesty stamps on every dogfood claim: `DEMO_FIXTURE != AUTHENTIC_PILOT`; UI ≠ canonical; model ≠ authority; UNKNOWN ≠ healthy.

---

## Phase 5 — Execution pointer

First package: **`AS-CODER-ALPHA-CONNECT-001`** (`atlas connect .`).

Standing D-032 autonomous merge authorization applies to routine certified merges. Escalate only genuine owner boundaries (authentic pilot, INT-013, AS-GH-002, OPT wake, external security).
