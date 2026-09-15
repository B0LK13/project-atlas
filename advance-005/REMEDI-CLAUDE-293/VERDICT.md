# REMEDI-CLAUDE-293 — Holdout isolation hotfix (003/004/010)

| Field | Value |
|---|---|
| Package | ADVANCE-005 / Group D / #293 AS-2.2-EVAL-001 |
| Tip base | `b0d4413cc5591a9cc789101db95b3f2cd3621afe` |
| Branch | `hotfix/adv005-claude-003-004-010-holdouts` |
| Worktree | `D:\atlas-worktrees\remedi-claude-293` |
| Mode | Tip HOTFIX remediation |
| Evidence | `advance-005/REMEDI-CLAUDE-293/` |

## Findings disposition

| ID | Claim | Disposition | Notes |
|---|---|---|---|
| CLAUDE-ADV005-003 | plaintext expected in durable receipts | **REMEDIATED** | holdout `expected_norm` redacted; schema enforces empty + `expected_redacted` |
| CLAUDE-ADV005-004 | role≠trust | **REMEDIATED** | `ATLAS_EVAL_SCORING_CAPABILITY=1` + private expected map required |
| CLAUDE-ADV005-010 | hidden holdouts ordinary git files | **PARTIAL** | git bodies no longer carry plaintext `expected`; metadata still tracked |

## Gate flags (post-remedi)

| Flag | Value |
|---|---|
| **HIDDEN_HOLDOUT_ISOLATION** | **PARTIAL_TOWARD_PASS** |
| **EVALUATOR_READY_FOR_AUTOLAB** | **NO** (sealed gate; no broker yet) |
| **ATLAS_OPT_WAKE_GATE** | **CLOSED** |
| PLAINTEXT_EXPECTED_IN_HOLDOUT_FILES | **NO** |
| PLAINTEXT_EXPECTED_IN_GENERATED_RECEIPT | **NO** |
| SCORING_CAPABILITY_GATE | **YES** |

## Changes

1. `eval_substrate.py` — capability env gates, private expected map, receipt redaction.
2. Holdout case JSON — removed plaintext `expected` from git-tracked bodies.
3. `eval-score-receipt.schema.json` — holdout rows require redacted expected fields.
4. `.gitignore` — `fixtures/eval/holdouts/private/` for operator-local secrets.
5. Unit tests — 14 cases covering capability gate + redaction regressions.

## What was not done

- No merge / no OPT wake / no #291
- No RELEASE CERT / CODEX_VALIDATED / external security revalidation
- No separate eval broker (014/015/020 supporting gaps remain)

## Seal

```
REMEDI=APPLIED
FINDINGS=003,004,010
HIDDEN_HOLDOUT_ISOLATION=PARTIAL_TOWARD_PASS
EVALUATOR_READY_FOR_AUTOLAB=NO
ATLAS_OPT_WAKE_GATE=CLOSED
DO_NOT_MERGE=HONORED
```
