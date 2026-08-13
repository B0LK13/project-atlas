# D-038 Real Atlas Dogfood — Findings

**Directive:** D-PROJECT-ATLAS-CODER-ALPHA-038
**Estate:** /workspace (Project Atlas repository)
**Vault:** /tmp/atlas-dogfood-d038/.atlas-vault
**Connect:** TIME_TO_CONNECT_MS=36447 (exit 0)

## Exercise results
All commanded surfaces returned OK on first dogfood vault:
overview, state, changed, decisions, unknown, brief, context,
capture record/list, handoff create/resume, obsidian project.

## Metrics (pre-remediation vault)
| Metric | Value | Notes |
|---|---|---|
| TIME_TO_CONNECT | ~36.4s | Fresh vault scaffold + full compile |
| TIME_TO_USEFUL_CONTEXT | ~37.1s | connect + context (~0.7s) |
| PROJECT_IDENTITY_ACCURACY | LOW→remediated | Root auto-marker was `workspace`; fixtures polluted estate |
| PURPOSE_ACCURACY | PARTIAL | project-atlas purpose thin ("status: prototype") |
| TECH_STACK_ACCURACY | MISS | UNKNOWN despite pyproject/Python reality |
| ARCHITECTURE_ACCURACY | PARTIAL | Mirrors thin purpose; pipeline not summarized |
| CURRENT_STATE_ACCURACY | GOOD | pending_reviews/sources honest |
| MEANINGFUL_CHANGES_RECALL | BASELINE | First connect → UNKNOWN history (honest) |
| DECISION_RECALL | MISS | important_decisions UNKNOWN for project-atlas |
| UNKNOWN_HONESTY | PASS | conflicts/pending/coverage_absent surfaced |
| HANDOFF_SUCCESS | PASS | create+resume OK; auto-capture attached |
| SESSION_CONTINUITY | PASS | resume returned context + instructions |
| OBSIDIAN_USEFULNESS | PARTIAL | Notes generated for all projects; useful per-project |
| EVIDENCE_TRACEABILITY | PASS | evidence_links present on brief/context |
| USER_CORRECTION_REQUIRED | YES | Identity + stack + decisions need human/source fixes |
| MANUAL_EXPLANATION_REQUIRED | MEDIUM | Fresh agent gets thin purpose/stack |
| REEXPLANATION_RATE | TBD | Fresh-agent challenge after merge |

## Defects
1. **HIGH** Connect on repo root created `workspace` identity and ingested all `fixtures/**` pilot estates → wrong primary identity.
2. **HIGH** Tech stack UNKNOWN for real Atlas package.
3. **MEDIUM** Important decisions UNKNOWN despite docs/adr + WORKLOG.
4. **MEDIUM** Purpose/architecture under-informative for vibe-coder onboarding.
5. **UX** Web Knowledge was flat inventory only (addressed by WEB-001).
6. **UX** No Truth inspection path in Web (addressed by TRUTH-UX-001).
7. **LOW** Pending review entries lack subject/field in some queue rows.

## Remediations in this package
- Tracked root `.atlas-project.yaml` with `project.id: project-atlas`
- `fixtures` added to discovery DEFAULT_EXCLUDES + connect exclude globs
- `GET /v1/brief` + Knowledge UX sections + Truth panel

## Classification
| ID | Severity | Status |
|---|---|---|
| DF-038-01 fixture pollution | HIGH | remediated (code) |
| DF-038-02 wrong root identity | HIGH | remediated (marker) |
| DF-038-03 tech_stack unknown | MEDIUM | open (compiler coverage) |
| DF-038-04 decisions unknown | MEDIUM | open (compiler coverage) |
| DF-038-05 thin purpose | MEDIUM | open |
| DF-038-06 web flat inventory | UX | remediated WEB-001 |
| DF-038-07 truth UX missing | MISSING_CAPABILITY | remediated TRUTH-UX-001 |
