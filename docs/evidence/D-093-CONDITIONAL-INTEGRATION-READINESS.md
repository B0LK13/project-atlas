# D-093 — D-042 conditional integration readiness

DIRECTIVE: `D-PROJECT-ATLAS-CLOUD-D042-D093-CONDITIONAL-INTEGRATION-READINESS`
PACKAGE: `AS-CODER-ALPHA-CONVERSATIONAL-CAPTURE-001` (D-042)
PR: `#353` (do not merge)

This packet prepares final integration so Local D-092A + D-092 can be
ingested in one short reconciliation. It does **not** implement
production. It does **not** change D-091 semantics. It does **not**
authorize merge. It does **not** invent Local Windows-estate results.

```
PRODUCTION_MUTATION = NO
NEW_PR_CREATED = NO
MERGE_AUTHORIZATION = NOT_GRANTED
D042_MERGE_ELIGIBILITY = NO_PENDING_LOCAL
D042_STATE = OPEN — CONDITIONAL INTEGRATION READY
CLOUD_IV = PASS
```

---

## Authoritative state (re-read 2026-08-14)

```
CURRENT_MAIN                 = c282f2c1eb2dde24f997e480c37d083fda906e54
PR                           = 353
PR_353_STATE                 = OPEN
PR_353_MERGED                = NO
PR_353_DRAFT                 = YES
PR_353_MERGEABLE             = YES
mergeStateStatus             = CLEAN
D091_PRODUCTION_HEAD         = 9ec65c7662f1ed8e18805a9496df8ded19d2c65e
D091_PRODUCTION_TREE         = 97e56303ec7642bb86c9799cd2dbd79bfa1eaf08
PRE_D093_PR_TIP              = 902b3a0e74a84e22e7b2f5395c5581f6401540aa
CURRENT_PR_HEAD              = 902b3a0e74a84e22e7b2f5395c5581f6401540aa
D049_STATE                   = CLOSED
D042_EXECUTION_GATE          = OPEN
```

`origin/main` was fetched and matched `CURRENT_MAIN`.

---

## Local status correction

Previous Cloud output `LOCAL_D092_READY = YES` was premature: no D-088
owner project yet had a governed Atlas identity/vault binding. Cloud
cannot observe the owner Windows estate and does **not** claim D-092A
or D-092 PASS.

```
LOCAL_D092_ENVIRONMENT_READY = YES
LOCAL_D092_ACCEPTANCE_ASSETS_READY = YES
LOCAL_D092_GOVERNED_PROJECT_PRECONDITION = PENDING_D092A
LOCAL_D092_READY = CONDITIONAL
D092A_OWNER_AUTHORIZATION = GRANTED_FOR_DARK_FACTORY
D092A_AUTHORIZED_PROJECT_ROOT = D:\dev-ai\dark-factory
D092A_RESULT = PENDING
D092_RESULT = PENDING
```

D-092A accepted-main onboarding mutation ≠ D-091 production payload.
Do not add Dark Factory files to PR `#353`.

---

## Lane A — D-091 lineage

```
git merge-base --is-ancestor c282f2c 9ec65c7  → YES
git merge-base --is-ancestor 9ec65c7 902b3a0  → YES
```

```
D091_FREEZE_DESCENDS_FROM_MAIN = YES
PR_HEAD_DESCENDS_FROM_D091_FREEZE = YES
```

Ancestry:

```
c282f2c  accepted main (D-049 CLOSED merge of #351)
  9ec65c7  D091 PRODUCTION FREEZE
  902b3a0  D091 evidence / D-092 runbook (pre-D093 tip)
```

### Post-freeze path classification (`9ec65c7` → `902b3a0`)

| Path | Class |
| --- | --- |
| `WORKLOG.md` | EVIDENCE_ONLY |
| `docs/backlog.md` | GOVERNANCE_ONLY |
| `docs/evidence/D-091-D042-EXECUTION-AUTHORIZATION.md` | EVIDENCE_ONLY |
| `docs/evidence/D-092-LOCAL-REVALIDATION-RUNBOOK.md` | EVIDENCE_ONLY |

No `src/`, `apps/`, or `tests/` path changed after `9ec65c7`.

```
PRODUCTION_SEMANTIC_CHANGES_AFTER_D091_FREEZE = 0
UNRELATED_PRODUCTION_CHANGE = 0
```

D-093 evidence/governance commits after this file must keep that zero.

---

## Lane B — D-091 production payload inventory

`git diff --name-status c282f2c 9ec65c7` (production freeze only):

| Path | Bucket |
| --- | --- |
| `src/project_atlas/conversation_capture.py` | CONVERSATION CAPTURE CORE / AUTHORITY / ROUTING / SECURITY |
| `src/project_atlas/schemas/conversation-capture.schema.json` | CONVERSATION CAPTURE CORE |
| `src/project_atlas/schema.py` | CONVERSATION CAPTURE CORE |
| `src/project_atlas/cli.py` | CLI |
| `src/project_atlas/api_server.py` | API |
| `src/project_atlas/web_api/brief.py` | WEB / AGENT-CONTEXT READ |
| `src/project_atlas/agent_handoff.py` | AGENT CONTEXT |
| `apps/web/src/hooks/useLiveBrief.ts` | WEB |
| `apps/web/src/pages/production/KnowledgePage.tsx` | WEB |
| `tests/unit/test_as_coder_alpha_042_conversation_capture.py` | TEST_ONLY (freeze) |
| `tests/unit/test_schema.py` | TEST_ONLY (freeze) |

Expected surfaces present on the freeze:

```
CONVERSATION CAPTURE CORE   atlas.conversation-capture.v1; deterministic ccap- id
AUTHORITY                   capture != authority; owner_origin required for
                            confirmed_owner_decision; no Truth Core auto-promote
PROJECT ROUTING             existing governed identity only; unmatched/conflicting
                            fail closed; no identity minting
KNOWLEDGE INBOX             quarantined / reviewable / non-canonical
CLI                         atlas capture conversation
API                         POST /v1/captures/conversation
WEB                         Knowledge Inbox conversational capture display
AGENT CONTEXT               Conversation capture — non-authoritative
SECURITY                    secret-shaped content fail-closed; prompt-injection inert
MCP                         NOT_APPLICABLE (read-only; no write tool invented)
TRANSCRIPT_EXTRACTION       DEFERRED
RAW_TRANSCRIPT_PERSISTED    NO
```

```
PRODUCTION_SCOPE_MATCHES_D091 = YES
UNRELATED_PRODUCTION_CHANGE = 0
```

---

## Lane C — authentic acceptance matrix

### CASE A — D092A PASS and D092 PASS

Require materially:

```
GOVERNED_PROJECT_EXISTS = YES
PROJECT_IDENTITY_ALREADY_EXISTS = YES
UUID_OWNER_CARDINALITY = 1
IDENTITY_CROSS_SURFACE_MATCH = PASS
GOVERNED_VAULT_HEALTH = PASS
UNRELATED_TRACKED_FILES_CHANGED_BY_ATLAS = 0
TARGET_HEAD == 9ec65c7662f1ed8e18805a9496df8ded19d2c65e
TARGET_TREE == 97e56303ec7642bb86c9799cd2dbd79bfa1eaf08
VALIDATION_TARGET_STALE = NO
CAPTURE_ACCEPTED = YES
PROJECT_ROUTING = PASS
KNOWLEDGE_INBOX = PASS
HUMAN_READABLE_PROJECTION = PASS
AGENT_CONTEXT_INTEGRATION = PASS
SAME_INPUT_SAME_CAPTURE_ID = YES
DUPLICATE_INBOX_RECORDS = 0
DUPLICATE_HUMAN_NOTES = 0
CAPTURE_AUTO_PROMOTIONS = 0
TRUTH_CORE_MUTATIONS_FROM_CAPTURE = 0
PROJECT_IDENTITIES_MINTED_BY_CAPTURE = 0
DISCOVERY_SIDE_EFFECTS = 0
CONNECT_SIDE_EFFECTS_FROM_CAPTURE = 0
INGEST_SIDE_EFFECTS_FROM_CAPTURE = 0
SECRET_ECHO = 0
PROMPT_INJECTION_EXECUTIONS = 0
CROSS_PROJECT_LEAKS = 0
```

Then candidate:

```
D091_LOCAL_ACCEPTANCE = PASS
D042_MERGE_ELIGIBILITY = YES
```

Still `MERGE_AUTHORIZATION = NOT_GRANTED` until owner grant.

### CASE B — D092A PASS and D092 PARTIAL

```
D042_MERGE_ELIGIBILITY = NO
```

Return the smallest exact residual. Do not start remediation automatically.

### CASE C — D092A FAIL / PARTIAL

```
D092_AUTHENTIC_ROUND_TRIP = NOT_APPLICABLE | BLOCKED
D042_MERGE_ELIGIBILITY = NO
```

Separate onboarding defect from D-091 conversational-capture defect.
Do not blame D-091 for accepted-main `atlas connect` behavior.

### CASE D — D092 FAIL

```
D042_MERGE_ELIGIBILITY = NO
```

Classify the failing category as one of:

```
AUTHORITY
ROUTING
IDEMPOTENCY
SECURITY
CROSS_PROJECT
CLI/API PARITY
PROJECTION
CONTEXT
OTHER
```

```
D092_ACCEPTANCE_MATRIX_READY = YES
```

---

## Lane D — Dark Factory onboarding reconciliation template

Local D-092A fills these. Cloud leaves them unobserved.

```
PROJECT_ROOT = D:\dev-ai\dark-factory
CANONICAL_GOVERNED_VAULT = D:\atlas-governed\dark-factory
PROJECT_ID = UNOBSERVED
PROJECT_UUID = UNOBSERVED
VAULT_ID = UNOBSERVED
MARKER_CREATED = UNOBSERVED
BIND_CREATED = UNOBSERVED
IDENTITY_CROSS_SURFACE_MATCH = UNOBSERVED
UUID_OWNER_CARDINALITY = UNOBSERVED
GOVERNED_VAULT_HEALTH = UNOBSERVED
UNRELATED_OWNER_FILE_MUTATIONS = UNOBSERVED
ONBOARDING_RESULT = PENDING
```

```
D092A_RECONCILIATION_TEMPLATE_READY = YES
```

---

## Lane E — D-092 result ingest template

Local D-092 fills these against exact freeze `9ec65c7` / `97e56303`.

```
TARGET_HEAD = UNOBSERVED
TARGET_TREE = UNOBSERVED
VALIDATION_TARGET_STALE = UNOBSERVED
CAPTURE_ID = UNOBSERVED
PROJECT_ROUTING = UNOBSERVED
KNOWLEDGE_INBOX = UNOBSERVED
HUMAN_READABLE_PROJECTION = UNOBSERVED
AGENT_CONTEXT_INTEGRATION = UNOBSERVED
SAME_INPUT_SAME_CAPTURE_ID = UNOBSERVED
DUPLICATE_INBOX_RECORDS = UNOBSERVED
DUPLICATE_HUMAN_NOTES = UNOBSERVED
API_SEMANTIC_PARITY = UNOBSERVED
AMBIGUOUS_PROJECT = UNOBSERVED
UNMATCHED_PROJECT = UNOBSERVED
FALSE_OWNER_AUTHORITY_PROMOTIONS = UNOBSERVED
SECRET_ECHO = UNOBSERVED
PROMPT_INJECTION_EXECUTIONS = UNOBSERVED
CROSS_PROJECT_LEAKS = UNOBSERVED
TRUTH_CORE_HASH_CHANGED = UNOBSERVED
PROJECT_IDENTITY_HASH_CHANGED = UNOBSERVED
SOURCE_LINEAGE_OWNERSHIP_CHANGED = UNOBSERVED
CONNECT_STATE_CHANGED = UNOBSERVED
INGEST_OWNERSHIP_CHANGED = UNOBSERVED
CAPTURE_AUTO_PROMOTIONS = UNOBSERVED
TRUTH_CORE_MUTATIONS_FROM_CAPTURE = UNOBSERVED
PROJECT_IDENTITIES_MINTED_BY_CAPTURE = UNOBSERVED
DISCOVERY_SIDE_EFFECTS = UNOBSERVED
CONNECT_SIDE_EFFECTS_FROM_CAPTURE = UNOBSERVED
INGEST_SIDE_EFFECTS_FROM_CAPTURE = UNOBSERVED
D092_AUTHENTIC_ROUND_TRIP = PENDING
```

```
D092_RECONCILIATION_TEMPLATE_READY = YES
```

---

## Lane F — owner merge packet (prepared, not issued)

```
AUTHORIZED_PR = 353
AUTHORIZED_BASE_MAIN = c282f2c1eb2dde24f997e480c37d083fda906e54
AUTHORIZED_PRODUCTION_HEAD = 9ec65c7662f1ed8e18805a9496df8ded19d2c65e
AUTHORIZED_PRODUCTION_TREE = 97e56303ec7642bb86c9799cd2dbd79bfa1eaf08
AUTHORIZED_PR_HEAD = TO_BE_FILLED_AFTER_FINAL_RECONCILIATION
AUTHORIZED_PR_TREE = TO_BE_FILLED_AFTER_FINAL_RECONCILIATION
AUTHORIZED_INTEGRATION_METHOD = GITHUB_MERGE_COMMIT
```

Do not squash, rebase, or force-push.

Fail closed at authorization time if:

- `main` moved unexpectedly
- PR head changed unexpectedly
- D-091 freeze is no longer an ancestor
- production semantics changed after freeze
- Local D-092 is not PASS
- required CI is not green
- `HIGH_OPEN > 0`

```
OWNER_MERGE_PACKET_READY = YES
MERGE_AUTHORIZATION = NOT_GRANTED
```

---

## Lane G — pre-merge checklist

At future owner-authorization time, re-read and require:

```
CURRENT_MAIN == AUTHORIZED_BASE_MAIN
PR_353_STATE = OPEN
PR_353_MERGED = NO
PR_353_MERGEABLE = YES
D091 freeze is ancestor of final tip
PRODUCTION_SEMANTIC_CHANGES_AFTER_D091_FREEZE = 0
D092A = PASS
D092 = PASS
CLOUD_IV = PASS
required CI = PASS
NEW_SECURITY_HIGH = 0
NEW_HIGH = 0
HIGH_OPEN = 0
```

If all hold, future reconciliation may set:

```
D042_STATE = CERTIFIED — MERGE ELIGIBLE
MERGE_AUTHORIZATION = NOT_GRANTED
```

Do not set that now.

```
PREMERGE_CHECKLIST_READY = YES
```

---

## Lane H — post-merge seal (future)

After owner-authorized GitHub merge commit, record:

```
PREVIOUS_MAIN
AUTHORIZED_PR_HEAD
AUTHORIZED_PRODUCTION_HEAD
MERGE_COMMIT
MERGE_TREE
PARENT_1
PARENT_2
POST_MERGE_MAIN
```

Required lineage:

```
PARENT_1 == authorized previous main
PARENT_2 == authorized PR head
POST_MERGE_MAIN == MERGE_COMMIT
```

Exact-main verification (not PR-branch evidence):

- D-042 conversational capture
- session capture regression
- Knowledge Inbox
- agent context
- AppService/API
- Web
- D-049 regression
- identity/connect
- source lineage
- Control Plane
- ruff
- mypy
- Web typecheck
- Web build

Required:

```
AUTHORIZED_PAYLOAD_PRESENT = YES
PRODUCTION_SEMANTIC_DRIFT = 0
UNRELATED_PRODUCTION_CHANGE = 0
POST_MERGE_VERIFICATION = PASS
```

```
POST_MERGE_SEAL_READY = YES
```

---

## Lane I — D-042 final closure packet (conditional, not now)

Only after Local D-092 PASS **and** owner-authorized merge **and**
post-merge exact-main seal PASS may future state become:

```
D042_FINAL_ACCEPTANCE = PASS
D042_STATE = CLOSED
CONVERSATIONAL_CAPTURE = PRODUCTION_ACCEPTED
```

Do not close D-042 during D-093.

```
D042_FINAL_CLOSURE_PACKET_READY = YES
```

---

## Lane J — product acceptance summary (capability, not Local PASS)

Answerable from D-091 production freeze + Cloud IV. Authentic Local-only
questions remain unanswered until D-092 returns.

| Question | Freeze/Cloud answer |
| --- | --- |
| Can a provider submit project knowledge without raw transcript persistence? | YES — structured `atlas.conversation-capture.v1`; raw transcript rejected |
| Can Atlas route it only to an existing governed project? | YES — unmatched / conflicting / name-only fail closed; no minting |
| Can model output become authority automatically? | NO — quarantined evidence; `confirmed_owner_decision` still ≠ Truth Core |
| Does replay duplicate captures? | NO — same canonical input → same `ccap-` id; no second inbox record |
| Can the user see the capture in Knowledge? | YES — Web Knowledge Inbox panel; UI ≠ Truth Core |
| Can agents receive it as clearly non-authoritative context? | YES — labeled `Conversation capture — non-authoritative` |
| Can capture silently trigger discovery/connect/ingest? | NO — capture writes ops/inbox/projection only |
| Can a fake "owner approved this" statement elevate authority? | NO — `FALSE_OWNER_DECISION` without `owner_origin` |

Do not answer whether Dark Factory onboarding or an authentic `D:\`
round-trip passed. Those are Local-only.

```
PRODUCT_ACCEPTANCE_SUMMARY_READY = YES
```

---

## Lane K — PR governance correction

PR `#353` / this packet now state:

```
CLOUD_IV = PASS
D091 production freeze remains exact
LOCAL_D092_ENVIRONMENT_READY = YES
LOCAL_D092_GOVERNED_PROJECT_PRECONDITION = OWNER-AUTHORIZED / LOCAL EXECUTION PENDING
LOCAL_D092_READY = CONDITIONAL
MERGE_AUTHORIZATION = NOT_GRANTED
```

Not claimed:

```
D092 PASS
D092A PASS
Dark Factory UUID
authentic Local capture result
```

Known Cloud CI on pre-D093 tip `902b3a0`, run `31828796134`, conclusion
`success`:

- `ci / control-plane`
- `ci / quality (ubuntu-latest, 3.12, full)`
- `ci / quality (ubuntu-latest, 3.13, compat)`
- `ci / quality (windows-latest, 3.12, windows)`

Do not manufacture extra CI for activity.

---

## Next action

```
NEXT_ACTION = WAIT FOR LOCAL D092A / D092.
```
