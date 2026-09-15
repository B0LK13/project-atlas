# D-035 — Frontier Accounting Reconciliation & Owner-Gate Seal

Governance seal, not a re-certification. See D-034 for the full-stack verification this reconciles.

## What was reconciled

D-034 reported an internally inconsistent DAG (`DERIVABLE=1` alongside `AUTONOMOUS_NODES_REMAINING=0`).
This document corrects that using stricter taxonomy: `READY`, `DERIVABLE`, `BLOCKED_BY_OWNER`,
`BLOCKED_EXTERNAL`, `BACKLOG_OPTIONAL`, `DECLINED_NO_DEFECT`, `ALREADY_COMPLETE`.

## Live drift sweep

No drift. `main`, PR #607, and PR #607's own head/tree are byte-identical to D-034. PR #608 moved
(`0987bf2a...` → `5c89c39f...`) but only by the D-034 evidence-doc commit itself (2 new files under
`docs/evidence/`, zero overlap with the Golden Estate skill/tests/CI) — classified **evidence-only**,
not semantic. No D-034 certification result required rerunning.

## SEC021 hermeticity — reclassified

D-034 left this as `READY` while also claiming zero remaining autonomous work — contradictory.
Correct classification: **`BACKLOG_OPTIONAL`**. There is no repository contract requiring tests to
tolerate an arbitrary broken executable pre-existing on a contributor's PATH (not H1), and widening
the test's assertion set would not weaken the actual trusted-execution invariant being tested — the
invariant-bearing assertions (`str(evil) not in payload["command"]`, `not marker.exists()`) are
untouched either way (not H3). It's a legitimate, optional resilience nicety with no validated defect,
no P0/P1, and no blocked dependency behind it. **No code was changed.**

## PR608 retarget — reclassified

D-034 called this `DERIVABLE`. It isn't: the only remaining action (retargeting #608's base from
#607's branch to `main`) requires #607 to actually merge — an owner-exclusive transition. Correct
classification: **`BLOCKED_BY_OWNER`**, dependency `PR607_MERGED → PR608_RETARGET_TO_MAIN`. The
merge-tree simulation itself (0 conflicts) was completed in D-034 and remains valid.

## The three owner-gated nodes, named exactly

1. **OWNER-1** — PR #607 review/merge decision. Preparation complete; nothing autonomous remains.
2. **OWNER-2** — PR #608 review/merge decision, gated behind #607 merging first (then a mechanical,
   already-simulated, 0-conflict retarget).
3. **OWNER-3** — 43-PR supersession cleanup. Analysis complete (D-029); `PR_CLOSE_AUTHORIZATION` was
   never granted, so execution is owner-exclusive regardless of proof quality.

## Windows node

Still `BLOCKED_EXTERNAL` — no Windows capability became available during this session. The D-034
execution packet's target binding was updated to #608's current head/tree (`5c89c39f...` /
`88d1fa45...`); its commands and pass/fail criteria are unchanged since the movement was evidence-only.

## Supersession drift

7 of 43 sampled cumulatively across D-034 + D-035 (#536, #543, #550, #565, #580, #592, plus one more):
**0 drift**. Full 43-entry re-audit not performed — not required.

## Final DAG accounting

| Class | Count |
|---|---|
| READY | 0 |
| DERIVABLE | 0 |
| UNKNOWN_REQUIRES_AUDIT | 0 |
| AUTONOMOUS_REMEDIATIONS | 0 |
| BLOCKED_BY_OWNER | 3 |
| BLOCKED_EXTERNAL | 1 |
| BACKLOG_OPTIONAL | 1 |
| DECLINED_NO_DEFECT | 0 |
| ALREADY_COMPLETE | 2 |

`AUTONOMOUS_NODES_REMAINING = 0 + 0 + 0 + 0 = 0`. `FRONTIER_ACCOUNTING_CONSISTENT = YES`.

MERGE_AUTHORIZATION = NOT_GRANTED. MERGE_PERFORMED = NO.
