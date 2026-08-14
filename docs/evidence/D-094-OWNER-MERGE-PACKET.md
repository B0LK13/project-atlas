# D-094 — owner merge packet for #353

DIRECTIVE: `D-PROJECT-ATLAS-CLOUD-D094-AND-OVERNIGHT-AUTONOMOUS-DEVELOPMENT-001`

This packet is **not** owner authorization. `MERGE_AUTHORIZATION` remains
`NOT_GRANTED` until the owner explicitly grants it.

Preferred integration: **GitHub merge commit**.  
Forbidden: squash, rebase, force-push.

---

## Authorized identities

```
AUTHORIZED_PR                    = 353
AUTHORIZED_BASE_MAIN             = c282f2c1eb2dde24f997e480c37d083fda906e54
AUTHORIZED_PRODUCTION_HEAD       = 9ec65c7662f1ed8e18805a9496df8ded19d2c65e
AUTHORIZED_PRODUCTION_TREE       = 97e56303ec7642bb86c9799cd2dbd79bfa1eaf08
AUTHORIZED_PR_HEAD               = TO_BE_STAMPED
AUTHORIZED_PR_TREE               = TO_BE_STAMPED
AUTHORIZED_INTEGRATION_METHOD    = GITHUB_MERGE_COMMIT
```

`AUTHORIZED_PR_HEAD` / `AUTHORIZED_PR_TREE` are stamped in the follow-up
evidence commit that freezes this packet on the branch tip.

Local D-092 validated the D-091 production freeze, not a later evidence tip.

```
PRODUCTION_SEMANTIC_CHANGES_AFTER_D091_FREEZE = 0
LOCAL_D092_APPLICABLE_TO_PR = YES
```

---

## Pre-merge fail-closed conditions

Owner authorization is valid only while **all** of the following remain true
at authorization time (re-read; do not trust this file alone):

```
CURRENT_MAIN == c282f2c1eb2dde24f997e480c37d083fda906e54
PR #353 = OPEN
PR #353 = UNMERGED
PR #353 = MERGEABLE
PR HEAD == AUTHORIZED_PR_HEAD
D091 freeze remains ancestor of PR HEAD
PRODUCTION_SEMANTIC_CHANGES_AFTER_D091_FREEZE = 0
D092A = PASS
D092_RECONCILED_RESULT = PASS
D091_LOCAL_ACCEPTANCE = PASS
CLOUD_IV = PASS
required CI = PASS
NEW_SECURITY_HIGH = 0
NEW_HIGH = 0
HIGH_OPEN = 0
```

Observed at D-094 reconciliation time (pre-stamp tip `e905c80`):

```
PR_353_OPEN = YES
PR_353_MERGED = NO
PR_353_MERGEABLE = YES
PR_353_DRAFT = YES
mergeStateStatus = CLEAN
baseRefOid = c282f2c1eb2dde24f997e480c37d083fda906e54
LINUX_CI = PASS
WINDOWS_CI = PASS
CI_RUN = 31832932117
```

If any condition changes:

```
OWNER_MERGE_PACKET_VALID = NO
```

Require reconciliation before merge.

Do **not** mark the PR ready unless the owner separately authorizes that.
Do **not** merge without explicit owner merge authorization.
Do **not** squash, rebase, or force-push.

---

## What merge includes

Production freeze `9ec65c7` / tree `97e56303` plus later
evidence/governance-only descendants. Local D-092 validated the freeze.

---

## Post-merge seal (future; not now)

After owner-authorized GitHub merge commit, record:

```
PREVIOUS_MAIN = c282f2c1eb2dde24f997e480c37d083fda906e54
AUTHORIZED_PR_HEAD = <stamped>
AUTHORIZED_PRODUCTION_HEAD = 9ec65c7662f1ed8e18805a9496df8ded19d2c65e
MERGE_COMMIT
MERGE_TREE
PARENT_1 = PREVIOUS_MAIN
PARENT_2 = AUTHORIZED_PR_HEAD
POST_MERGE_MAIN = MERGE_COMMIT
```

Then run exact-main verification for D-042 capture, session-capture
regression, Knowledge Inbox, agent context, AppService/API, Web, D-049,
identity/connect, source lineage, Control Plane, ruff, mypy, Web
typecheck/build.

Required:

```
AUTHORIZED_PAYLOAD_PRESENT = YES
PRODUCTION_SEMANTIC_DRIFT = 0
UNRELATED_PRODUCTION_CHANGE = 0
POST_MERGE_VERIFICATION = PASS
```

Only then may `D042_STATE = CLOSED`.
