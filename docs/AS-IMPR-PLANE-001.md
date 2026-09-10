# AS-IMPR-PLANE-001 — Delivery-evidence improvement plane

**Status:** Implemented (lane-local; not merged; no authority)  
**Directive:** `ATLAS-PARALLEL-IMPROVEMENT-PLANE-20260910`  
**Goal:** `ATLAS-EVIDENCE-TO-IMPROVEMENT-20260910`  
**Package:** `AS-IMPR-PLANE-001`  
**Entry point:** `python -m project_atlas.improvement_plane`

## Product outcome

An operator can inspect available Atlas delivery evidence and answer:

1. Where is work waiting?
2. Which failures recur?
3. Which evidence is missing or stale?
4. Which owner decisions block progress?
5. Which next improvement has the strongest supporting evidence?

## What this is

A **read-only analysis/reporting lane** that compiles:

- machine-readable JSON (`atlas.improvement-plane.report.v1`)
- a concise operator Markdown summary

from existing captured evidence. It reuses optional vault ops receipt inventory
(`project_atlas.ops_receipts`) when a vault path is supplied.

It is **not**:

- a competing metrics engine
- Truth Core / project authority
- a DAG dispatcher, retry agent, or merge authorizer
- a Studio mission/session/claim/recovery surface
- a claim of measured productivity gains

```text
RECOMMENDATION ≠ AUTHORITY
TELEMETRY ≠ TRUTH CORE
MISSING_TIMESTAMP ≠ 0
MISSING_IV ≠ NEVER_VERIFIED
```

## Ownership boundary

This lane owns:

- `src/project_atlas/improvement_plane/`
- `tests/unit/test_as_impr_plane_001.py`
- `docs/AS-IMPR-PLANE-001.md`
- lane evidence under `docs/evidence/AS-IMPR-PLANE-001-*`

It deliberately does **not** modify shared CLI registration (`cli.py`), CI
workflows, Studio code, DAG telemetry modules, or other agents' active
worktrees.

## Inputs

| Input | Mode |
|---|---|
| `docs/evidence/**/*.json` | READ (primary) |
| optional vault `generated/ops/**` via `inventory_ops_receipts` | READ optional |
| `--reference-utc` | optional waiting-age reference |

Out of scope for v1: Markdown evidence, WORKLOG prose, live `gh`/CI API calls,
file mtime as event time.

## Commands

```bash
# From a checkout with src/ on PYTHONPATH or an editable install:
python -m project_atlas.improvement_plane --repo .

# Waiting age only when a reference timestamp is supplied:
python -m project_atlas.improvement_plane \
  --repo . \
  --reference-utc 2026-09-10T06:00:00Z \
  --output-json docs/evidence/AS-IMPR-PLANE-001-DEMO-REPORT.json \
  --output-md docs/evidence/AS-IMPR-PLANE-001-DEMO-REPORT.md

# Optional vault ops inventory (absence stays unknown):
python -m project_atlas.improvement_plane --repo . --vault /path/to/vault --json
```

## Tests

```bash
python -m pytest tests/unit/test_as_impr_plane_001.py --no-cov
```

## Coverage limits

- Evidence JSON only under `docs/evidence/`
- No automatic reprioritization of the DAG
- Recommendations always `authority: none`
- Source snapshot should be pinned (`docs/evidence/AS-IMPR-PLANE-001-SOURCE-PIN.json`)

## Recommendation contract

Each ranked recommendation includes:

| Field | Meaning |
|---|---|
| `observed_problem` | What the evidence shows |
| `source_records` | Supporting packet paths |
| `scope` | Bounded interpretation surface |
| `uncertainty` | What remains unknown |
| `proposed_action` | Suggested next step |
| `required_actor` | owner / engineer / operator / evidence_author |
| `dependency` | Stated dependency or `none_stated` |
| `ranking_rationale` | Transparent score formula |

Prioritization weights (transparent, non-causal): owner gates (100 + 25/dependent) > recurring failures (70 + open/source terms) > stale packets (55) > queued opportunities (50) > timestamp hygiene (40).

## Optional adoption proposal

If Core later wants a shared CLI surface, add a thin `atlas impr report`
subcommand that calls `compile_improvement_report` without changing this
module's contracts. That adoption is optional and must not block this lane.
