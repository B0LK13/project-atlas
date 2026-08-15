# D-095 — D-042 post-merge ratification and seal

DIRECTIVE: `D-PROJECT-ATLAS-OWNER-D042-D095-POST-MERGE-RATIFICATION-AND-CLOSURE`
VALIDATOR: Local (Windows)
PACKAGE: `AS-CODER-ALPHA-CONVERSATIONAL-CAPTURE-001` (CAPTURE-002 / D-042)
RECORDED: 2026-08-15

This packet is **evidence / governance only**. It does **not** change
D-091 production semantics. `POST_MERGE_CLOSURE_PRODUCTION_CHANGES = 0`.
PR #354 was not touched.

---

## Honest authorization history (do not rewrite)

`#353` was **already merged** when D-095 began. This packet does **not**
claim that a pre-merge owner authorization existed.

Known preserved repository state before this seal (D-091 / D-094, and
Local D-092C):

```
MERGE_AUTHORIZATION            = NOT_GRANTED
PREMERGE_AUTHORIZATION         = NOT_ESTABLISHED
```

Independent D-095 search of `docs/` and preserved Local evidence found
**no** owner receipt that granted merge authorization before the GitHub
merge. D-091 recorded `MERGE_AUTHORIZATION = NOT_GRANTED`. D-094's owner
merge packet explicitly said it was **not** owner authorization.

The owner later granted **conditional post-merge ratification** for D-095
if exact lineage / integrity / exact-main gates passed. Those gates
passed. This is **not** retroactive pre-merge authorization.

```
PREMERGE_AUTHORIZATION         = NOT_ESTABLISHED
OWNER_POST_MERGE_RATIFICATION  = VALID
OWNER_ACCEPTS_EXISTING_MERGE   = YES
```

---

## Observed live merge (re-read)

```
PR                             = 353
PR_353_MERGED                  = YES
OBSERVED_MERGED                = YES
OBSERVED_MERGE_COMMIT          = 9441b0c576dc54bc43a92a62a4e972889424c21f
CURRENT_MAIN                   = 9441b0c576dc54bc43a92a62a4e972889424c21f
MAIN_MOVED_AFTER_D042_MERGE    = NO
mergedAt                       = 2026-08-14T20:36:07Z
baseRefName                    = main
headRefOid                     = 822a6d82fa81df8afa1f4de759f3d2dc2a8b93fb
GITHUB_MERGE_COMMIT            = YES
SQUASH                         = NO
REBASE                         = NO
```

`git fetch origin` then `git rev-parse origin/main` equaled the observed
merge commit. `git rev-list --count origin/main ^9441b0c` = `0`.

---

## Merge object integrity

```
MERGE_COMMIT                   = 9441b0c576dc54bc43a92a62a4e972889424c21f
MERGE_TREE                     = ed78a92e941d88ac1aa198c311b0120b4c9ce7ef
PARENT_1                       = c282f2c1eb2dde24f997e480c37d083fda906e54
PARENT_2                       = 822a6d82fa81df8afa1f4de759f3d2dc2a8b93fb
EXPECTED_PREVIOUS_MAIN         = c282f2c1eb2dde24f997e480c37d083fda906e54
EXPECTED_AUTHORIZED_PR_HEAD    = 822a6d82fa81df8afa1f4de759f3d2dc2a8b93fb
EXPECTED_AUTHORIZED_PR_TREE    = ed78a92e941d88ac1aa198c311b0120b4c9ce7ef
PARENT_1_MATCH                 = YES
PARENT_2_MATCH                 = YES
MERGE_TREE_EQUALS_CERTIFIED_PR_TREE = YES
```

`git cat-file -p 9441b0c` is a two-parent GitHub merge commit
(`Merge pull request #353 from B0LK13/cursor/d042-conversational-capture-6f85`).
`git diff --stat 822a6d82 9441b0c` is empty.

---

## D-091 payload presence

```
EXPECTED_D091_PRODUCTION_HEAD  = 9ec65c7662f1ed8e18805a9496df8ded19d2c65e
EXPECTED_D091_PRODUCTION_TREE  = 97e56303ec7642bb86c9799cd2dbd79bfa1eaf08
AUTHORIZED_D091_PAYLOAD_PRESENT = YES
PRODUCTION_SEMANTIC_DRIFT_FROM_CERTIFIED_PR = 0
UNRELATED_PRODUCTION_CHANGE    = 0
```

Exact merge tree contains:

- `src/project_atlas/conversation_capture.py`
- `src/project_atlas/schemas/conversation-capture.schema.json`
- schema registration (`conversation-capture` in `schema.py`)
- CLI `atlas capture conversation`
- API `POST /v1/captures/conversation`
- Knowledge Inbox integration (`build_knowledge_inbox_receipt`)
- human-readable non-authoritative projection
- agent-context label `Conversation capture — non-authoritative`
- Web Knowledge conversation-capture surface
- D-042 production tests (`tests/unit/test_as_coder_alpha_042_conversation_capture.py`)

Post-D-091-freeze path delta (`9ec65c7` → `9441b0c`) is evidence /
governance only:

- `WORKLOG.md`
- `docs/backlog.md`
- `docs/evidence/D-091-D042-EXECUTION-AUTHORIZATION.md`
- `docs/evidence/D-092-LOCAL-REVALIDATION-RUNBOOK.md`
- `docs/evidence/D-093-CONDITIONAL-INTEGRATION-READINESS.md`
- `docs/evidence/D-094-FINAL-RECONCILIATION.md`
- `docs/evidence/D-094-OWNER-MERGE-PACKET.md`

No `src/`, `apps/`, or production-test path changed after the D-091
freeze.

---

## Exact-main validation environment

Fresh disposable worktree `D:\atlas-acceptance-d060\d095-atlas-src`
detached at the merge commit, then branched only for this docs seal.

```
VALIDATION_HEAD                = 9441b0c576dc54bc43a92a62a4e972889424c21f
VALIDATION_TREE                = ed78a92e941d88ac1aa198c311b0120b4c9ce7ef
STALE_GLOBAL_ATLAS_USED        = NO
PYTHON                         = py -3.12 (3.12.10) worktree venv
```

The worktree venv `atlas` entry resolves to
`D:\atlas-acceptance-d060\d095-atlas-src\src\project_atlas`. Package
metadata still prints `project-atlas 2.0.0`; that is this tree's
`pyproject.toml` version, not a stale global install.

---

## D-042 exact-main suite

```
D042_EXACT_MAIN                = PASS
```

`python -m pytest tests/unit/test_as_coder_alpha_042_conversation_capture.py`
→ 7 passed.

Covered: structured submission, provider neutrality, unique / ambiguous /
conflicting / name-only / path-shaped routing, inbox quarantine, human
projection, agent-context label, CLI, API parity, `owner_origin`, replay
idempotency, secret hygiene, prompt-injection inertness, raw-transcript
rejection, review ≠ promotion.

---

## Regression gates (exact-main)

| Gate | Result | Evidence |
| --- | --- | --- |
| D049_REGRESSION | PASS | focused D-049 files + estate discovery; 102 passed, 1 skipped |
| IDENTITY_CONNECT | PASS | `test_as_coder_alpha_connect_001.py` — 8 passed |
| SOURCE_LINEAGE | PASS | `test_source_identity.py` — 17 passed |
| SESSION_CAPTURE | PASS | `test_as_coder_alpha_capture_001.py` — 5 passed |
| AGENT_HANDOFF | PASS | `test_as_coder_alpha_context_handoff_001.py` — 2 passed |
| API_ADV | PASS | `test_as_2_1_api_adv_deepen_001.py` — 22 passed |
| SECURITY | PASS | `test_as_sec_009_api_auth.py` — 7 passed |
| MCP | PASS | `test_as_2_0_mcp_001.py` + `test_as_2_1_mcp_adv_001.py` — 13 passed |
| CONTROL_PLANE | PASS | exact-merge GitHub `control-plane` (ubuntu) success; see residual |
| RUFF | PASS | `python -m ruff check .` — All checks passed |
| MYPY | PASS | exact-merge GitHub `quality (ubuntu-latest, 3.12, full)` mypy success; see residual |
| WEB_TYPECHECK | PASS | `npx tsc -b` exit 0 |
| WEB_BUILD | PASS | `npm run build` (`tsc -b && vite build`) exit 0 |

No full `D:\` authentic discovery was run.

### Recorded residuals (not D-042 production defects)

Local `python -m mypy src` with freshly resolved mypy 1.20.2 / 2.3.1
reported `unused-ignore` at `src/project_atlas/yaml_structured.py:222`.
That file is **byte-identical** to previous main `c282f2c` (not in the
D-042 production delta). Exact-merge CI mypy on `9441b0c` (run
`31838651156`) reported `Success: no issues found in 187 source files`.

Local Windows Control Plane
(`atlas-vault-documentation/tests/test_agent_control.py::test_two_managed_sessions_receive_distinct_ids`)
failed on a `fcntl` ImportError fallback plus a `\\?\` extended-path
prefix (`unsafe output path outside root`). The applicable Control Plane
gate in `.github/workflows/ci.yml` is `ubuntu-latest` and passed on
exact merge. Sibling-suite Windows path-lock residual; not a D-042
payload change.

---

## Local D-092 applicability (owner-supplied; Cloud-unobserved estate)

Preserved Local evidence. This validator did **not** claim Cloud observed
the Windows estate. Authentic Dark Factory capture was **not** rerun.

```
D092A_ONBOARDING               = PASS
D092_AUTHENTIC_OWNER_ROUND_TRIP = PASS
D092B_ROUTING_SUPPLEMENT       = PASS
D092_RECONCILED_RESULT         = PASS
D091_LOCAL_ACCEPTANCE          = PASS
LOCAL_D042_CAMPAIGN_STATE      = SEALED_PASS
DOGFOOD_PROJECT_ID             = dark-factory-02ee94d0
DOGFOOD_PROJECT_UUID           = c440d169-bb43-4e97-a175-0d3f62177d8f
DOGFOOD_BASELINE_READY         = YES
DOGFOOD_SNAPSHOT               = CREATED
CANONICAL_VAULT_MUTATION_BY_D092 = NO
UNEXPECTED_OWNER_MUTATIONS     = 0
LOCAL_D092_APPLICABLE_TO_MERGED_MAIN = YES
```

References (not rewritten): `D:\atlas-acceptance-d060\d092c-final\`,
`d092-run`, `d092b-routing`, `d092a-onboarding`.

Applicability holds because the merge tree equals the certified PR tree
and the D-091 production freeze is an ancestor with zero production
semantic drift after freeze.

---

## GitHub CI distinction

Do not mislabel PR-head CI as merge-main CI.

### Final PR-head CI (pre-merge; certified tip `822a6d82`)

```
PR_HEAD_GITHUB_CI              = PASS
PR_HEAD_CI_RUN                 = 31837034472
event                          = pull_request
headSha                        = 822a6d82fa81df8afa1f4de759f3d2dc2a8b93fb
```

Jobs: `control-plane`, `quality (ubuntu-latest, 3.12, full)` including
ruff + mypy, `quality (ubuntu-latest, 3.13, compat)`,
`quality (windows-latest, 3.12, windows)` — all success.

### Post-merge CI (exact main `9441b0c`)

```
POST_MERGE_GITHUB_CI           = PASS
POST_MERGE_CI_RUN              = 31838651156
event                          = push
headBranch                     = main
headSha                        = 9441b0c576dc54bc43a92a62a4e972889424c21f
```

Jobs: same four identities, all success. Windows pytest
`2590 passed, 5 skipped, 1 xfailed`. Ubuntu 3.12 full
`2592 passed, 3 skipped, 1 xfailed`. Mypy success. Control-plane success.

---

## Security / authority final check

From sealed D-092 / D-092B evidence plus the exact-main D-042 suite.
Authentic Dark Factory capture was not rerun.

```
NEW_SECURITY_HIGH              = 0
NEW_HIGH                       = 0
HIGH_OPEN                      = 0
CAPTURE_AUTO_PROMOTIONS        = 0
TRUTH_CORE_MUTATIONS_FROM_CAPTURE = 0
PROJECT_IDENTITIES_MINTED_BY_CAPTURE = 0
DISCOVERY_SIDE_EFFECTS         = 0
CONNECT_SIDE_EFFECTS_FROM_CAPTURE = 0
INGEST_SIDE_EFFECTS_FROM_CAPTURE = 0
SECRET_ECHO                    = 0
PROMPT_INJECTION_EXECUTIONS    = 0
CROSS_PROJECT_LEAKS            = 0
```

Historical `AS-CODER-ALPHA-044-HIGH` remains a separate open package and
is not a D-042 HIGH.

---

## Closure verdict

```
D042_EXACT_MAIN                = PASS
D042_FINAL_ACCEPTANCE          = PASS
D042_STATE                     = CLOSED
CONVERSATIONAL_CAPTURE         = PRODUCTION_ACCEPTED
D042_EXECUTION_GATE            = SATISFIED
D091_PRODUCTION_FREEZE         = ACCEPTED_ON_MAIN
D091_LOCAL_ACCEPTANCE          = PASS
POST_MERGE_CLOSURE_PRODUCTION_CHANGES = 0
ROADMAP_PR_354_TOUCHED         = NO
```

Persistence of this receipt on `main` is a separate owner-held docs PR.
The operational D-042 closure verdict is recorded here after the
exact-main seal passed.

---

## Local freeze copy

`D:\atlas-acceptance-d060\d095-seal\FINAL_REPORT.md` (outside the
repository unless later copied by owner).
