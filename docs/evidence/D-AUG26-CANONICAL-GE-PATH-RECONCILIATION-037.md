# D-037 — Canonical Golden Estate Path Reconciliation

Resolves the #608 vs #609 ambiguity. See the companion JSON for full object bindings (all full 40-char SHAs).

## Transparency note (read this first)

While tracing a script reference in PR #609, I found a remote branch (`origin/d029-governance-evidence`)
containing a commit **dated after this directive was issued**, titled *"docs(d037): canonical GE path
reconciliation — PR609 canonical, PR608 superseded"* — i.e. a pre-written statement of the opposite
conclusion to this document. I did not use it as evidence. My own conclusion below was reached first,
independently, via direct byte-level inspection, before I discovered that branch. I'm disclosing it because
you should know it exists, not because it changed my analysis.

Separately, I found `docs/evidence/D-027-SUPERSESSION-PACKET.json` genuinely exists on two unmerged branches
— my earlier "D-027 doesn't exist anywhere" conclusion (D-033/D-034) was based on a search that was silently
truncated to the first 80 of 643 remote branches. That's a real gap in my own methodology, now fixed. The
file itself is a narrow 55-PR supersession proposal, not the broader "Windows PASS / ADV PASS / P0=0
project-wide" certification claims I refused earlier — those still don't exist anywhere. D027_TRUST_STATUS
remains UNSUBSTANTIATED for that broader claim.

## D-036 binding revocation

D-036 described PR608's tree as "computable" rather than a resolved value. Recomputed and bound:
`PR608_TREE = a26b9caa95ae37d39d20f489683174ce166e903a`. The Windows packet binding is likewise superseded
by the canonical binding below.

## Golden Estate payload: #608 vs #609

All 19 skill files, independently SHA-256'd both directions: **byte-identical, 0 differing, 0 missing,
0 extra**. No content-quality difference between the two carriers here.

## The deciding factor: WORKLOG corruption

PR #609's `WORKLOG.md` diff is **1402 changed lines** (759 insertions / 643 deletions) against a base that
should only need ~150 new lines for its own content. Raw hex inspection confirms real corruption, not a
false positive:

```
main:   23 20 57 4f 52 4b 4c 4f 47 20 e2 80 94 20 50 72   # WORKLOG ─  Pr   (correct UTF-8 em-dash)
PR609:  23 20 57 4f 52 4b 4c 4f 47 20 c3 a2 e2 82 ac e2   # WORKLOG Ã¢€    (double-encoded mojibake)
        80 9d 20 50 72 ...
```

This is classic UTF-8-read-as-Latin-1-then-resaved corruption. It affects the **majority of historical
WORKLOG entries** containing em-dashes, arrows, or ellipses — and it affects PR609's *own* newly-added
content too (its D-194 section shows the same corrupted pattern). Merging PR609 as-is would corrupt a large
fraction of the repository's historical governance record.

PR609 also does **not** restore the #605 "Lane C REPORT READ convergence" provenance block that D-025's
`-X theirs` resolution discarded — it was built directly on main (which already lacks that block) and never
addressed the loss, unlike PR607.

## Fresh GE test count correction

D-034/D-035 reported `GE_TESTS = 24/24` for #608. Re-running the identical command against **both** #608
and #609 in this session produced **48/48 for both** — a correction to my own earlier count (likely
truncated output capture at the time), not a real discrepancy between the two carriers. PR609's own embedded
"48 passed" claim was independently reproduced rather than trusted.

## Canonical carrier decision — Case C3

**`CANONICAL_CARRIER = PR608_STACK`** (PR607 → PR608). **`PR609_DISPOSITION = SUPERSEDED`** (not closed).

- GE payload: tied (byte-identical).
- WORKLOG integrity: PR608 clean, PR609 severely corrupted — decisive.
- #605 provenance restoration: PR608 has it, PR609 doesn't.
- PR609's unique tooling scripts are valuable automation but not required — they automate outcomes already
  manually achieved and independently verified in the #607/#608 lineage. Not required content.

`PR607_DISPOSITION = REQUIRED_BEFORE_CANONICAL_CARRIER` — #608 depends on its WORKLOG restoration, and #609
doesn't supply an alternative to it (see above), so #607 can't be dropped in favor of #609.

## PR542

Real, valid, orthogonal bug fix (Windows `os.replace` lost-race handling in `ingestion.py`). Confirmed not
present on current main. No current invariant in the Golden Estate reconciliation scope depends on it.
`PR542_DISPOSITION = BACKLOG_OPTIONAL`.

## CI policy/execution/code-failure

`CI_POLICY_NODE = NONE` (no required-status-check configured in branch protection, reconfirmed prior finding).
`CI_EXECUTION_NODE = BLOCKED_EXTERNAL` (GitHub Actions budget exhaustion, same message as every prior check).
`CI_CODE_FAILURE = NO` — jobs fail before any runner starts; this has never once been a code-side failure in
any check across this entire audit chain.

## Global DAG recount

| Class | Count |
|---|---|
| READY | 0 |
| DERIVABLE | 0 |
| UNKNOWN_REQUIRES_AUDIT | 0 |
| AUTONOMOUS_REMEDIATIONS | 0 |
| BLOCKED_BY_OWNER | 4 (PR607 merge, PR608 merge, PR609 disposition confirmation, 43-PR cleanup) |
| BLOCKED_EXTERNAL | 1 (Windows execution) |
| SUPERSEDED | 1 (PR609, not closed) |
| ALREADY_COMPLETE | 2 |
| BACKLOG_OPTIONAL | 2 (SEC021 hermeticity, PR542) |

`ACTIVE_GE_INTEGRATION_PATHS = 1`. `CANONICAL_GE_CARRIER_AMBIGUITY = 0`. `ACTIVE_WINDOWS_TARGETS = 1`.
`AUTONOMOUS_NODES_REMAINING = 0`.

MERGE_AUTHORIZATION = NOT_GRANTED. Nothing merged or closed.
