# D-082 — D-080 conditional merge readiness

DIRECTIVE: `D-PROJECT-ATLAS-CLOUD-D080-MERGE-READINESS-082`

This packet prepares the integration path. It does **not** authorize merge.
It does **not** change production semantics.

```
PRODUCTION_MUTATION = NO
NEW_PR_CREATED = NO
MERGE_AUTHORIZATION = NOT_GRANTED
D081_RESULT = PENDING
NEXT_ACTION = WAIT FOR LOCAL D-081.
```

---

## Lane A — exact lineage proof

Observed 2026-08-14 after `git fetch origin main` and
`git fetch origin cursor/d049-authorized-volume-root-6f85`.

```
CURRENT_MAIN              = 198350319c17b4de0665f972fda0bc51420cd686
CURRENT_MAIN_TREE         = 2250a7bf1162db778b26a41d94e6e6f7d6b9480c
origin/main               = 198350319c17b4de0665f972fda0bc51420cd686
D080_PRODUCTION_FREEZE    = 99aa937b3718cf0432bb688dbfa074daade7c049
D080_TREE                 = e73273f208009f9c317ffb489919e154938ee1c4
CURRENT_PR_EVIDENCE_TIP   = 13e20b9c217bdac9d11581b789b41774c7a78c89
D080_FREEZE_DESCENDS_FROM_MAIN     = YES
PR_TIP_DESCENDS_FROM_D080_FREEZE   = YES
```

Ancestry (oldest → newest on #351):

```
198350319  main
  fcaf4f5  fix(d049): authorize explicit Windows non-system volume roots   [D078 PRODUCTION]
  e2f0dfc  docs(d078): freeze receipt, Cloud IV, and Local runbook         [EVIDENCE_ONLY]
  99aa937  fix(d049): deterministic bounded candidate selection (D-080)    [D080 PRODUCTION FREEZE]
  e8f6ad8  docs(d080): freeze receipt, Cloud IV, and Local D-081 runbook   [EVIDENCE_ONLY]
  13e20b9  docs(d078): record D-080 as superseding merge candidate         [EVIDENCE_ONLY / GOVERNANCE_ONLY]
```

`git merge-base --is-ancestor 198350319 99aa937` → YES  
`git merge-base --is-ancestor 99aa937 13e20b9` → YES

### D080_PRODUCTION_FREEZE → CURRENT_PR_EVIDENCE_TIP path classification

`git diff --name-status 99aa937 13e20b9`:

| Path | Class |
| --- | --- |
| `WORKLOG.md` | EVIDENCE_ONLY |
| `docs/backlog.md` | GOVERNANCE_ONLY |
| `docs/evidence/D-078-SUPERSEDING-FREEZE.md` | EVIDENCE_ONLY |
| `docs/evidence/D-080-INDEPENDENT-IV.md` | EVIDENCE_ONLY |
| `docs/evidence/D-080-SUPERSEDING-FREEZE.md` | EVIDENCE_ONLY |
| `docs/evidence/D-081-LOCAL-REVALIDATION-RUNBOOK.md` | EVIDENCE_ONLY |

```
PRODUCTION_SEMANTIC_CHANGES_AFTER_D080_FREEZE = 0
```

No `src/`, `apps/`, or `tests/` path changed after `99aa937`.

If a later evidence-only tip exists at decision time, Cloud must re-run this
exact `git diff --name-status 99aa937 <tip>` check. If any production path
appears → STOP. Do not repair automatically.

---

## Lane B — exact production delta (`main` → `D080_PRODUCTION_FREEZE`)

Inspected actual `git diff --name-status 198350319 99aa937` (not commit
messages alone).

| Path | Capability class |
| --- | --- |
| `src/project_atlas/estate_discovery.py` | D078 volume-root policy + D080 selection + D080 scope-container + D080 knowledge fail-closed |
| `src/project_atlas/cli.py` | D078 `--root-mode` contract / help (unchanged by D080 production commit) |
| `src/project_atlas/web_api/discovery.py` | UI/API projection (mode + selection diagnostics) |
| `apps/web/src/hooks/useEstateDiscovery.ts` | UI/API projection |
| `apps/web/src/pages/production/DiscoveryPage.tsx` | UI/API projection |
| `tests/unit/test_as_d049_078_authorized_volume_root.py` | tests (D078) |
| `tests/unit/test_as_d049_080_candidate_selection.py` | tests (D080) |
| `tests/unit/test_as_d049_067_high_remediation.py` | tests (help asserts `owner-authorized-volume`) |
| `docs/evidence/D-078-*.md` | EVIDENCE_ONLY (landed between D078 freeze and D080 freeze) |
| `WORKLOG.md` / `docs/backlog.md` | GOVERNANCE_ONLY |

CLI diff vs main is only `--root-mode` wiring and help. API/Web diffs only
project `authorized_root_mode`, `volume_root_*`, and selection/cap fields.
No connect/ingest/identity/lineage/control-plane production files changed.

```
UNRELATED_PRODUCTION_CHANGE = 0
```

---

## Lane C — PR #351 integration sanity

Observed via `gh pr view 351` and Checks on run `31793117292`
(head `13e20b9`).

```
PR_351_OPEN                         = YES
PR_351_MERGED                       = NO
PR_351_BASE                         = main
PR_351_BASE_OID                     = 198350319c17b4de0665f972fda0bc51420cd686
PR_351_HEAD                         = 13e20b9c217bdac9d11581b789b41774c7a78c89
PR_351_DRAFT                        = YES
PR_351_MERGEABLE                    = YES
PR_351_MERGE_STATE_STATUS           = UNSTABLE
AUTHORIZED_PRODUCTION_FREEZE_PRESENT = YES
D080_FREEZE_IS_ANCESTOR_OF_PR_HEAD  = YES
```

`UNSTABLE` is GitHub’s merge-state for an open PR with a failing required-or-
reported check (Windows quality). GitHub still reports `mergeable=MERGEABLE`
(no conflict).

This directive did not mark ready, merge, or change production files.

---

## Lane D — already-observed validation receipts

Do not treat this section as a fresh suite run. These are previously observed
results plus GitHub Checks on `13e20b9`.

| Gate | Result | Where observed |
| --- | --- | --- |
| D049 / D063 / D064 / D067 / D078 / D080 focused | PASS (82) | D-080 Cloud implementer session |
| identity / connect / source lineage | PASS (33) | D-080 Cloud implementer session |
| Control Plane | PASS (171 local; `ci / control-plane` success) | D-080 session + GH run 31793117292 |
| ruff | PASS | D-080 session + `ci / quality (ubuntu-latest, 3.12, full)` |
| mypy | PASS | D-080 session + same Ubuntu full job |
| Web typecheck / build | PASS | D-080 session (`tsc -b && vite build`) |
| Cloud IV (D-078 policy + D-080 falsify) | PASS | `docs/evidence/D-078-INDEPENDENT-IV.md`, `docs/evidence/D-080-INDEPENDENT-IV.md` |
| `ci / quality (ubuntu-latest, 3.12, full)` | PASS | GH run 31793117292 |
| `ci / quality (ubuntu-latest, 3.13, compat)` | PASS | GH run 31793117292 |
| `ci / quality (windows-latest, 3.12, windows)` | FAIL | GH run 31793117292 job 94744244282 |

Windows failure (exact):

```
FAILED tests/unit/test_as_d049_078_authorized_volume_root.py::test_f_linux_filesystem_root_refuses
Failed: DID NOT RAISE EstateDiscoveryError
1 failed, 2562 passed, 4 skipped, 1 xfailed
```

Classification (not repaired in D-082):

- The test uses `Path(Path.cwd().anchor)` as a stand-in for Linux `/`.
- On GitHub `windows-latest` the workspace anchor is typically a **non-system
  volume** (often `D:\`), not `C:\` and not `/`.
- Default mode still refused that root (`FILESYSTEM_ROOT_NOT_ALLOWED`).
- Explicit `--root-mode owner-authorized-volume` accepted it — that is the
  D-078 **intended** non-system volume capability, not a system-drive bypass.
- Therefore: `FAILURE_CLASS = TEST_PORTABILITY`, not
  `SYSTEM_VOLUME_ROOT_NOT_ALLOWED` regression, not a new security HIGH.

```
KNOWN_CLOUD_GATES = FAIL
KNOWN_CLOUD_GATES_LINUX = PASS
WINDOWS_CI = FAIL
WINDOWS_CI_CLASS = TEST_PORTABILITY
NEW_SECURITY_HIGH = 0
NEW_HIGH = 0
HIGH_OPEN = 0
```

`KNOWN_CLOUD_GATES = FAIL` because the observed GitHub PR check set is not
all-green. Linux/Cloud focused gates remain PASS. Do not rewrite D-078 policy
PASS into FAIL.

Fixing the portable test requires a **separately directed** test-only change
after this packet. D-082 does not authorize that change.

---

## Lane E — conditional D-081 decision matrix

### CASE A — D081 PASS

Require all of:

```
KNOWN_EXPECTED_FOUND = 5/5
  dark-factory
  playbook-platform
  black-agency-web-design
  vibed-dev-env
  onedrive-organizer
AUTHORIZED_VOLUME_ROOT_EMITTED_AS_PROJECT = 0
EMPTY_PROJECT_ID_ASSIGNMENTS = 0
DANGLING_PROJECT_RELATIONS = 0
FALSE_KNOWLEDGE_PROJECT_ASSIGNMENTS = 0
SILENT_IDENTITY_MERGES = 0
PATH_ESCAPES = 0
NEW_HIGH = 0
HIGH_OPEN = 0
SCAN honesty preserved (do not require SCAN_COMPLETE = YES)
D078 policy probes still PASS
Local validated exact D080_HEAD / D080_TREE
```

Then:

```
D080_LOCAL_REVALIDATION = PASS
AUTHENTIC_USER_ESTATE_ACCEPTANCE = PASS
D_049_FINAL_ACCEPTANCE_RECOMMENDATION = PASS
PR_351_MERGE_ELIGIBILITY = YES
```

Still **do not merge automatically**. Before asking the owner to authorize:

1. Re-prove `PRODUCTION_SEMANTIC_CHANGES_AFTER_D080_FREEZE = 0` on the
   then-current PR head.
2. Confirm Local D-081 evidence still applies to that head.
3. Resolve or owner-waive `WINDOWS_CI_CLASS = TEST_PORTABILITY`
   (`ci / quality (windows-latest, 3.12, windows)`).

GitHub merge of a draft PR with `UNSTABLE` checks is not the same as
product eligibility. Case A product PASS does not by itself click Merge.

### CASE B — D081 PARTIAL

```
PR_351_MERGE_ELIGIBILITY = NO
```

Classify only the smallest remaining blocker (examples, do not pre-invent):

- one missing owner anchor due to residual selection
- remaining false knowledge assignment
- volume root still emitted as project
- scan-honesty regression
- performance so severe the scan is unusable (separate residual; see below)

Do **not** start a broad remediation campaign until separately directed.

### CASE C — D081 FAIL

```
PR_351_MERGE_ELIGIBILITY = NO
D_042_EXECUTION_GATE = CLOSED
```

Do not mutate #351.

---

## Lane F — owner merge packet (PREPARED, NOT ISSUED)

```
AUTHORIZED_PR                 = 351
AUTHORIZED_PRODUCTION_HEAD    = 99aa937b3718cf0432bb688dbfa074daade7c049
AUTHORIZED_PRODUCTION_TREE    = e73273f208009f9c317ffb489919e154938ee1c4
EXPECTED_PR_HEAD              = 13e20b9c217bdac9d11581b789b41774c7a78c89
                              or refreshed evidence-only descendant at decision time
AUTHORIZED_BASE_MAIN          = 198350319c17b4de0665f972fda0bc51420cd686
PREFERRED_INTEGRATION         = GitHub MERGE COMMIT
FORBIDDEN                     = squash, rebase, force-push
```

Owner authorization applies only after Cloud proves, at decision time:

```
PRODUCTION_SEMANTIC_CHANGES_AFTER_D080_FREEZE = 0
Local D-081 evidence remains applicable to PR head
CASE A criteria satisfied
WINDOWS_CI residual resolved or explicitly waived by owner
```

This packet is **not** owner authorization.

---

## Lane G — post-merge seal runbook (future, owner-authorized only)

After a future owner-authorized GitHub merge commit of #351 onto `main`:

1. Record `MERGE_COMMIT`, `MERGE_TREE`.
2. Prove `parent1 == pre-merge main` (expected `198350319` if main has not
   moved; if main moved, STOP and re-reconcile).
3. Prove `parent2 == authorized #351 head` (expected `13e20b9` or the
   evidence-only descendant authorized at decision time).
4. Prove merge tree contains D-078 + D-080 production payload
   (`--root-mode`, selection policy, volume-root container, knowledge
   fail-closed).
5. Prove `git diff AUTHORIZED_PRODUCTION_HEAD MERGE -- src apps/web/src tests`
   introduces **no** unexpected production semantic drift beyond the
   already-classified D-078/D-080 set.
6. `UNRELATED_PRODUCTION_CHANGE = 0`.
7. Bounded exact-main validation (do not launch an unrelated campaign):

```
pytest D-049 / D-063 / D-064 / D-067 / D-078 / D-080 focused
pytest identity / connect / source lineage
pytest atlas-vault-documentation/tests --no-cov
ruff / mypy
apps/web tsc -b && npm run build
```

Required: `NEW_HIGH = 0`, `HIGH_OPEN = 0`.

Then, and only then, apply Lane H.

---

## Lane H — D-049 final close template (conditional)

**IF and only if all three exist:**

1. D081 CASE A PASS
2. owner-authorized #351 merge
3. post-merge exact-main verification PASS

**THEN:**

```
D_049_STATE = POST_MERGE_VERIFIED
AUTHENTIC_USER_ESTATE_ACCEPTANCE = PASS
D_049_FINAL_ACCEPTANCE = PASS
D_049_STATE = CLOSED
D_042_EXECUTION_GATE = OPEN
```

Do **not** open D-042 before all three conditions exist.

Until then:

```
D_049_FINAL_ACCEPTANCE = PARTIAL
D_042_EXECUTION_GATE = CLOSED
```

---

## Performance residual (do not fix here)

```
D079_AUTHENTIC_RUNTIME ≈ 11 minutes
D079_DIRS_VISITED = 301002
D080_PERFORMANCE_RESIDUAL = NOT_MEASURED_ON_AUTHENTIC_ESTATE
PERFORMANCE_RESIDUAL = PENDING_D081
```

After D-081, classify `NONE | MINOR | MATERIAL | SEVERE` from Local’s
measured authentic runtime. Do not contaminate correctness reconciliation
unless the scan is materially unusable.

---

## Wait state

Forbidden until D-081 returns and a later directive authorizes work:

- new production implementation
- new PR / new freeze
- broad CI reruns
- D-042 coding
- Documentation Health / Living Roadmap / Project Memory / Momentum /
  Portfolio / 2.3 / OPT / AutoLab / Prime
