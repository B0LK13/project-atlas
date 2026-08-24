# D-162 — PR #472 exact-main owner authorization packet

```
DIRECTIVE = D-162-SESSION-RECOVERY-PR472-OWNER-GATE
AUTHORIZED_PR_CANDIDATE = 472
MERGE_AUTHORIZATION = NOT_GRANTED
PR472_MERGED = NO
PR472_STATE = MERGE_READY — OWNER_GATE
```

This is a **candidate packet**, not authorization.

---

## Exact pins (live GitHub, 2026-08-24)

```
EXPECTED_PARENT_MAIN = f0e0c979e8ead0fdad4cc51682c560299db0a074
CANDIDATE_HEAD = 35e7d2ec2e64ead28d1cbcc39f8f8829e802b7df
CI_RUN = 32759197773
CI_RESULT = PASS
BRANCH = feat/d157-lane422-arch
```

---

## Certification status

```
IV_RESULT = PENDING_REBIND (prior iv-472-arch at 5ac11ef invalidated)
ADV_RESULT = PENDING_REBIND
NEW_P0 = 0
NEW_P1 = 0
INDEPENDENT_IV_REQUIRED = YES
```

---

## Purpose

Read-only GET /v1/architecture surface (AS-CODER-ALPHA-ARCHITECTURE-SURFACE-001).

---

## Owner action required

Grant explicit merge authorization for exact candidate HEAD `35e7d2ec` only.
