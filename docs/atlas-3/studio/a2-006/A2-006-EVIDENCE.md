# AS-STUDIO-A2-006 — evidence

```text
PACKAGE_ID              = AS-STUDIO-A2-006
BRANCH                  = feat/as-studio-a2-006-mission-session
PR                      = #791
BASE_BRANCH             = feat/as-studio-a2-004-action-evidence
BASE_FREEZE_HEAD                    = 1bca04e39e6cb6bff12a8b586f22bdb1b5b594df
FORMAL_IV_PRIOR         = PASS on 4904125f (A2-004/005 only; NOT inherited)
HEAD                    = d45ec111d43a6883cb7904e8a3be4dadc88d578f
TREE                    = 91de77e78075b949768b9385d207175717224b4b
PRIOR_TIP_AA915318      = aa915318a79872cf7bc6ea9004c4a87178114589 (pre-hardening; superseded)
CI_CANDIDATE_HEAD       = 1bca04e39e6cb6bff12a8b586f22bdb1b5b594df
CI_EXACT_HEAD           = PENDING
FORMAL_IV               = NOT_STARTED (packet prepared under iv/)
MERGE_AUTHORIZATION     = NOT_GRANTED
```

## Local validation

```text
Studio unit suite: 134 passed
Doctor: a2_006_* PASS
```

## Repairs in this hardening cycle

| Risk | Result |
|---|---|
| Fingerprint changes with wall-clock | Fixed — fingerprint excludes `generated_at_utc` |
| Malformed → PENDING_EXECUTE | Fixed — continuity returns MALFORMED; session INCOMPLETE |
| Malformed intent + success decision | Fixed — not CONFIRMED_SUCCESS |
| `--repo` without artifact repos | Fixed — REPO_UNVERIFIED_IN_ARTIFACTS fail closed |
| Conflicting evidence vs decision | Fixed — CONFLICTING_EVIDENCE |
| DRY_RUN / FAILED_NO_MUTATION → REFUSED | Fixed — dedicated session states |
| Orphan tmp with final | Fixed — not INTERRUPTED; tmp not promoted |
| Persistence-failed recommends replay | Fixed — explicit do_not + recovery text |

## Honesty

```text
CI_PASS != FORMAL_IV
FORMAL_IV_4904125f != THIS_CANDIDATE
AUTO_RETRY = FORBIDDEN
CONTROL_PLANE_OBSERVATION = UNAVAILABLE (explicit)
```
