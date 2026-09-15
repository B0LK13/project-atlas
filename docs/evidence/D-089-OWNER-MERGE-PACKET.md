# D-089 — owner merge packet for #351

DIRECTIVE: `D-PROJECT-ATLAS-CLOUD-D049-D089-FINAL-RECONCILIATION`

This packet is **not** owner authorization. `MERGE_AUTHORIZATION` remains
`NOT_GRANTED` until the owner explicitly grants it.

Preferred integration: **GitHub merge commit**.  
Forbidden: squash, rebase, force-push.

---

## Authorized identities

```
AUTHORIZED_PR                    = 351
AUTHORIZED_BASE_MAIN             = 198350319c17b4de0665f972fda0bc51420cd686
AUTHORIZED_PRODUCTION_HEAD       = b2b5d9b9fc7e4d3aff69fea3e1a90d9c950b0b78
AUTHORIZED_PRODUCTION_TREE       = 14318297c5fbf40b4fff054ad27126ee4c89db7f
AUTHORIZED_PR_HEAD               = PENDING_D089_EVIDENCE_TIP
AUTHORIZED_PR_TREE               = PENDING_D089_EVIDENCE_TIP
AUTHORIZED_PR_HEAD_DESCENDS_FROM_D087 = YES
PRODUCTION_SEMANTIC_CHANGES_D087_TO_AUTHORIZED_PR_HEAD = 0
```

`AUTHORIZED_PR_HEAD` / `AUTHORIZED_PR_TREE` are stamped in the follow-up
evidence commit that adds this packet to the branch tip.

---

## Pre-merge fail-closed conditions

Owner authorization is valid only while **all** of the following remain true:

```
CURRENT_MAIN == 198350319c17b4de0665f972fda0bc51420cd686
PR #351 = OPEN
PR #351 = UNMERGED
PR #351 = MERGEABLE
PR HEAD == AUTHORIZED_PR_HEAD
D087 freeze remains ancestor of PR HEAD
D088 evidence remains applicable
  (LOCAL_D088_HEAD == D087_PRODUCTION_HEAD
   and PRODUCTION_SEMANTIC_CHANGES_AFTER_D087_FREEZE = 0)
KNOWN_CLOUD_GATES = PASS
NEW_HIGH = 0
HIGH_OPEN = 0
```

Observed at D-089 reconciliation time (pre-stamp tip `568ef53`):

```
PR_351_OPEN = YES
PR_351_MERGED = NO
PR_351_MERGEABLE = YES
PR_351_DRAFT = YES
mergeStateStatus = CLEAN
baseRefOid = 198350319c17b4de0665f972fda0bc51420cd686
```

If any condition changes:

```
OWNER_MERGE_PACKET_VALID = NO
```

Require reconciliation before merge.

Do **not** mark the PR ready unless the owner separately authorizes that.
Do **not** merge without explicit owner merge authorization.

---

## What merge includes

Production freeze `b2b5d9b` plus later evidence/governance/test-only
descendants. Local D-088 validated the freeze, not the evidence tip.

---

## What merge does not do

- does not close D-049 (needs post-merge exact-main seal)
- does not open D-042
- does not reopen `#344`
- does not authorize connect / ingest / identity minting
