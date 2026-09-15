# D-086 — D-084 conditional integration readiness

DIRECTIVE: `D-PROJECT-ATLAS-CLOUD-D084-D086-CONDITIONAL-INTEGRATION-READINESS`

This packet updates closure readiness from the superseded D-080 baseline to
the exact D-084 production freeze. It does **not** authorize merge.
It does **not** change production semantics.

```
PRODUCTION_MUTATION = NO
NEW_PR_CREATED = NO
MERGE_AUTHORIZATION = NOT_GRANTED
D085_RESULT = PENDING
NEXT_ACTION = WAIT FOR LOCAL D-085.
```

---

## Lane A — D-084 lineage re-proof

Observed 2026-08-14.

```
CURRENT_MAIN                 = 198350319c17b4de0665f972fda0bc51420cd686
CURRENT_MAIN_TREE            = 2250a7bf1162db778b26a41d94e6e6f7d6b9480c
origin/main                  = 198350319c17b4de0665f972fda0bc51420cd686
D084_PRODUCTION_HEAD         = 2fcf8186d4a2c6d4209cee82b6d6f076e2119589
D084_PRODUCTION_TREE         = 4148e9a63de0089736bea1c0b2631dd1e4fe72e5
CURRENT_PR_EVIDENCE_TIP      = 167b1f6e0e47658d34a7f06526ca5b324e4aeaa0
D084_FREEZE_DESCENDS_FROM_MAIN     = YES
PR_TIP_DESCENDS_FROM_D084_FREEZE   = YES
```

Ancestry (oldest → newest on #351):

```
198350319  main
  fcaf4f5  D078 PRODUCTION
  e2f0dfc  D078 evidence
  99aa937  D080 PRODUCTION (historical Local FAIL candidate)
  e8f6ad8  D080 evidence
  13e20b9  D078 superseded-by-D080 note
  8bb8d03  D082 evidence
  cc5c10b  D083 TEST_ONLY
  2fcf818  D084 PRODUCTION FREEZE
  167b1f6  D084 evidence / D-085 runbook
```

`git merge-base --is-ancestor 198350319 2fcf818` → YES  
`git merge-base --is-ancestor 2fcf818 167b1f6` → YES

### D084 freeze → PR tip path classification

`git diff --name-status 2fcf818 167b1f6`:

| Path | Class |
| --- | --- |
| `WORKLOG.md` | EVIDENCE_ONLY |
| `docs/backlog.md` | GOVERNANCE_ONLY |
| `docs/evidence/D-080-SUPERSEDING-FREEZE.md` | EVIDENCE_ONLY |
| `docs/evidence/D-084-INDEPENDENT-IV.md` | EVIDENCE_ONLY |
| `docs/evidence/D-084-SUPERSEDING-FREEZE.md` | EVIDENCE_ONLY |
| `docs/evidence/D-085-LOCAL-REVALIDATION-RUNBOOK.md` | EVIDENCE_ONLY |

```
PRODUCTION_SEMANTIC_CHANGES_AFTER_D084_FREEZE = 0
```

No `src/`, `apps/`, or `tests/` path changed after `2fcf818`.

If a later tip exists at decision time, re-run
`git diff --name-status 2fcf818 <tip>`. If any production path appears →
STOP. Do not repair automatically.

---

## Lane B — exact production payload (`main` → `D084` freeze)

Inspected actual `git diff --name-status 198350319 2fcf818` (not commit
messages alone). Unrelated production probe
(connect / ingest / identity / lineage / control-plane / capture) = empty.

| Path | Capability class |
| --- | --- |
| `src/project_atlas/estate_discovery.py` | D078 volume-root policy + D080 container/knowledge fail-closed + D084 hierarchical fair selection, boundary, siblings, independent nested, bounded enrichment, diagnostics |
| `src/project_atlas/cli.py` | D078 `--root-mode` contract / help |
| `src/project_atlas/web_api/discovery.py` | UI/API projection (mode + selection/enrichment diagnostics) |
| `apps/web/src/hooks/useEstateDiscovery.ts` | UI/API projection |
| `apps/web/src/pages/production/DiscoveryPage.tsx` | UI/API projection |
| `tests/unit/test_as_d049_078_authorized_volume_root.py` | D078 tests + D083 TEST_ONLY portability |
| `tests/unit/test_as_d049_080_candidate_selection.py` | D080 tests |
| `tests/unit/test_as_d049_084_fair_selection.py` | D084 tests |
| `tests/unit/test_as_d049_067_high_remediation.py` | tests (help asserts `owner-authorized-volume`) |
| `docs/evidence/*` / `WORKLOG.md` / `docs/backlog.md` | EVIDENCE_ONLY / GOVERNANCE_ONLY |

```
UNRELATED_PRODUCTION_CHANGE = 0
```

D-083 is test-only and is an ancestor of the D-084 freeze. It does not
change production semantics.

---

## Lane C — D-085 fast-path acceptance matrix

### CASE A — D085 PASS

Require all of:

```
KNOWN_EXPECTED_FOUND = 5/5
OWNER_ANCHORS_STARVED_BY_CAP = 0
NOISY_SUBTREE_MONOPOLY = NO
VIBED_DEV_ENV_EMITTED = YES
ONEDRIVE_ORGANIZER_EMITTED = YES
BOUNDED_ENRICHMENT_AUTHENTIC = PASS
EXPENSIVE_ENRICHMENT_FOR_ALL_SIGHTINGS = NO
AUTHORIZED_VOLUME_ROOT_EMITTED_AS_PROJECT = 0
EMPTY_PROJECT_ID_ASSIGNMENTS = 0
DANGLING_PROJECT_RELATIONS = 0
SILENT_IDENTITY_MERGES = 0
SILENT_KNOWLEDGE_MISASSIGNMENT = 0
PATH_ESCAPES = 0
FALSE_SCAN_COMPLETENESS = 0
NEW_SECURITY_HIGH = 0
NEW_HIGH = 0
HIGH_OPEN = 0
PERFORMANCE_RESIDUAL != SEVERE
Local validated exact D084_HEAD / D084_TREE
D078 policy probes still PASS
```

Then:

```
D084_LOCAL_REVALIDATION = PASS
AUTHENTIC_USER_ESTATE_ACCEPTANCE = PASS
D_049_FINAL_ACCEPTANCE_RECOMMENDATION = PASS
PR_351_MERGE_ELIGIBILITY = YES
```

Still **do not merge automatically**. Before asking the owner:

1. Re-prove `PRODUCTION_SEMANTIC_CHANGES_AFTER_D084_FREEZE = 0` on the
   then-current PR head.
2. Confirm Local D-085 evidence still applies to that head.
3. Confirm Lane F pre-merge checklist is all YES.

### CASE B — correctness PASS, performance SEVERE

```
D085_RESULT = PARTIAL
AUTHENTIC_USER_ESTATE_ACCEPTANCE = PARTIAL
D_049_FINAL_ACCEPTANCE = PARTIAL
PR_351_MERGE_ELIGIBILITY = NO
```

Classify performance as the exact remaining blocker. Do not silently waive.

### CASE C — PARTIAL / FAIL

```
PR_351_MERGE_ELIGIBILITY = NO
D_042_EXECUTION_GATE = CLOSED
```

Extract only the smallest evidence-backed residual. Do not start
remediation until separately directed. Do not mutate #351.

---

## Lane D — performance reconciliation template

Do not fill elapsed/class until D-085 evidence exists.

| Run | DIRS_VISITED | SEEN | PRESELECTED | ENRICHED | EMITTED | KNOWLEDGE_SEEN | ELAPSED |
| --- | --- | --- | --- | --- | --- | --- | --- |
| D079 | ~301002 | (cap-starved) | n/a | n/a | 500 | 500 | ≈ 00:10:59 |
| D081 | 301473 | 11461 | n/a (enrich-all) | ≈ seen | 500 | 24543 | 01:17:19 |
| D085 | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING |

Classifications (apply only after D-085): `NONE | MINOR | MATERIAL | SEVERE`.

Questions (do not answer yet):

1. Did bounded enrichment reduce expensive work materially?
2. Did runtime return toward a usable range?
3. Is residual cost mainly filesystem traversal rather than enrichment?
4. Would the user reasonably tolerate first discovery at this scale?
5. Is incremental discovery a later optimization rather than a D-049
   acceptance blocker?

---

## Lane E — owner merge packet V2 (PREPARED, NOT ISSUED)

```
AUTHORIZED_PR                 = 351
AUTHORIZED_PRODUCTION_HEAD    = 2fcf8186d4a2c6d4209cee82b6d6f076e2119589
AUTHORIZED_PRODUCTION_TREE    = 4148e9a63de0089736bea1c0b2631dd1e4fe72e5
EXPECTED_PR_HEAD              = refreshed exact evidence descendant at decision time
AUTHORIZED_BASE_MAIN          = 198350319c17b4de0665f972fda0bc51420cd686
PREFERRED_INTEGRATION         = GitHub MERGE COMMIT
FORBIDDEN                     = squash, rebase, force-push
```

Packet is **invalid** (do not issue) if at decision time:

- `main` moved unexpectedly
- production semantics changed after D084 freeze
- PR head no longer descends from D084 freeze
- Local D-085 evidence is not applicable to PR head
- required CI is not green
- CASE A is not satisfied

This packet is **not** owner authorization.

---

## Lane F — pre-merge fail-closed checklist

At decision time, all must be true or `MERGE_AUTHORIZATION = INVALID`:

```
CURRENT_MAIN == AUTHORIZED_BASE_MAIN
PR_351_OPEN = YES
PR_351_MERGED = NO
PR_351_MERGEABLE = YES
D084 freeze present in PR ancestry
PR tip is evidence/test/governance-only descendant of D084 freeze
PRODUCTION_SEMANTIC_CHANGES_AFTER_D084_FREEZE = 0
D085 = PASS
KNOWN_CLOUD_GATES = PASS
NEW_HIGH = 0
HIGH_OPEN = 0
```

---

## Lane G — post-merge seal V2 (future, owner-authorized only)

After a future owner-authorized GitHub merge commit of #351 onto `main`:

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
PARENT_1 = PREVIOUS_MAIN
PARENT_2 = authorized #351 head
```

Then verify:

- D-078 + D-080 + D-084 production payload present
- D-083 test portability present
- production semantic drift = 0
- unrelated production change = 0

Bounded exact-main suites:

```
pytest D-049 / D-063 / D-064 / D-067 / D-078 / D-080 / D-083 / D-084
pytest identity / connect / source lineage
pytest atlas-vault-documentation/tests --no-cov
ruff / mypy
apps/web tsc -b && npm run build
```

Required: `POST_MERGE_VERIFICATION = PASS`, `NEW_SECURITY_HIGH = 0`,
`NEW_HIGH = 0`, `HIGH_OPEN = 0`.

---

## Lane H — D-049 final closure V2 (conditional)

**IF and only if all three exist:**

1. D085 authentic Run A = PASS (CASE A, not CASE B)
2. owner-authorized #351 merge
3. post-merge exact-main seal = PASS

**THEN:**

```
AUTHENTIC_USER_ESTATE_ACCEPTANCE = PASS
D_049_FINAL_ACCEPTANCE = PASS
D_049_STATE = CLOSED
D_042_EXECUTION_GATE = OPEN
```

Do not execute this transition early. Until then:

```
D_049_FINAL_ACCEPTANCE = FAIL
D_042_EXECUTION_GATE = CLOSED
```

---

## Lane J — future performance residual placeholder

Only if D-085 proves correctness PASS **and** performance is
acceptable-but-material (`MINOR` or `MATERIAL`, not `SEVERE`):

```
FUTURE_PACKAGE_CANDIDATE = AS-ESTATE-DISCOVERY-INCREMENTAL-001
PURPOSE = incremental / cached estate discovery after initial full scan
IMPLEMENTATION = NOT_STARTED
CRITICAL_PATH_BEFORE_D085 = NO
```

If D-085 performance is SEVERE, this is **not** a later optimization; it
remains a CASE B blocker. Do not implement it in this directive.

---

## Wait state

Forbidden until D-085 returns and a later directive authorizes work:

- new production implementation / new freeze / new competing PR
- broad CI reruns / synthetic estate campaign
- D-042 coding
- Documentation Health / Roadmap / Memory / Momentum / Portfolio /
  2.3 / OPT / AutoLab / Prime
