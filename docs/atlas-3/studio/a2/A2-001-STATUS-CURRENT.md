# AS-STUDIO-A2-001 — current status (provenance record)

```text
RECORD_KIND                        = STATUS_WITH_PROVENANCE
CERTIFIED_OBJECT                   = 2debb7784746228c55503a60e55293929a5f5b1c
CERTIFIED_TREE                     = 2ae9a6866977a0a18b1113855195cc11838a7b78
THIS_FILE_DOES_NOT_MUTATE          = THE_CERTIFIED_GIT_OBJECT
HISTORICAL_EVIDENCE_PRESERVED      = YES (A2-EVIDENCE.md tip pins may lag; see below)
```

## Certified object (do not silently redefine)

| Field | Value |
|---|---|
| Package | `AS-STUDIO-A2-001` |
| Branch | `feat/as-studio-a2-001` |
| PR | [#776](https://github.com/B0LK13/project-atlas/pull/776) |
| HEAD | `2debb7784746228c55503a60e55293929a5f5b1c` |
| TREE | `2ae9a6866977a0a18b1113855195cc11838a7b78` |
| Exact-head CI | run `34376691357` — **success** (4/4 jobs) |
| Formal IV | **PASS** — separate Cursor IV subagent |
| IV handoff (durable) | [`iv/A2-001-FORMAL-IV-HANDOFF-2debb778.md`](./iv/A2-001-FORMAL-IV-HANDOFF-2debb778.md) |
| Frozen pre-hardening baseline | `6ff336cd` / CI `34360705782` (preserved) |

Any descendant of `2debb778` is a **new candidate** and does not inherit this certification.

## Evidence reconciliation (2026-09-09)

| Topic | Prior inconsistent statement | Reconciled truth |
|---|---|---|
| Formal IV | PR body unchecked / `FORMAL_IV = PENDING` | Formal IV **PASS** for exact object `2debb778`; merge still NOT_GRANTED; open review threads remain |
| `replace=True` | Earlier hardening row said escape hatch explicit; later tip removed it | Final certified tip: **no** `replace=` parameter on `register_action` |
| Test counts | PR cited 1788 full-suite; handoff cited 6248 | Different scopes/tips — do not combine. Certified tip required-repo run: **6248 passed**, 8 skipped, 4 xfailed (`pytest -q --override-ini=addopts=`). Studio A0–A2 unit: **90 passed**. |
| In-tree `A2-EVIDENCE.md` HEAD pin | Still shows older tip (`3e0fc723`) on certified object | Historical document on that commit; **this status record** is the current reading for `2debb778` without rewriting the certified blob |

## Integration gates (external)

```text
OPEN_REVIEW_THREADS                = 2 (human adjudication)
REQUIRED_APPROVALS                 = UNSATISFIED / empty reviewDecision at last check
MERGE_AUTHORIZATION                = NOT_GRANTED
STACK                              = #763 → #770 → #776 (all OPEN)
A2_PRESENT_ON_ORIGIN_MAIN          = NO
```

## Honesty

```text
CI_PASS != FORMAL_IV
FORMAL_IV != MERGE_AUTHORIZATION
IMPLEMENTED != MERGED
SELF_IV = NO
```
