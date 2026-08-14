# D-071 D-049 final reconciliation (Local still pending)

DIRECTIVE: `D-PROJECT-ATLAS-CLOUD-D049-FINAL-RECONCILIATION-071`

This is **current-state** Cloud reconciliation. It does not rewrite
historical D-063 / D-064 / D-066 receipts. Those remain contemporaneous
records of invalidated or superseded candidates.

```
REPOSITORY_PRODUCTION_MUTATION = NO
D068_FINAL_RESULT = PENDING
D049_CLOUD_RECONCILIATION = WAITING_FOR_LOCAL
D_049_ACCEPTANCE = NOT_YET_EVALUATED
D_042_EXECUTION_GATE = CLOSED
AUTHENTIC_USER_ESTATE_ACCEPTANCE = NOT_EVALUATED
```

Do not collapse:

```
D067_CANDIDATE_READY
D068_WINDOWS_REVALIDATION
PR_348_MERGE_ELIGIBILITY
POST_MERGE_VERIFICATION
AUTHENTIC_USER_ESTATE_ACCEPTANCE
D_049_FINAL_ACCEPTANCE
```

into one PASS.

## Lane A — PR topology (verified)

| Ref | HEAD | TREE | Role |
| --- | --- | --- | --- |
| `origin/main` | `072f1395ee310a876e93d633264f3ece43cecc3c` | `ad29628bbf7552ebe8b4a71b0192d3004129375f` | current main |
| D-067 freeze | `ccacaa5bcb094f35017c7195264fef55e382cb49` | `d26768fe753c888cd45001987da2afe977c79d45` | production semantics |
| #348 tip | `d7624753d9fa506bf3b4664ecfbad2af408d9834` | `2250a7bf1162db778b26a41d94e6e6f7d6b9480c` | freeze + D-067 evidence |
| #346 tip | `d3a9458f478c3c06be0086622c3f262ec9938175` | (D-064 evidence on `0509287`) | superseded production lane |
| #347 tip | `88ac905c975903cfb04c09b6d9f48ed5444aa28a` | evidence-only from main | housekeeping |
| #349 / D-069 | `7c8560b9e62f3fe64d75d5036a3f7d8119fc78c0` | `fac05d07d83ebab1fa4552e4c13109d78366cdad` | integration evidence |

Ancestry (measured):

```
ccacaa5 ancestor of #348     YES
ccacaa5 ancestor of #346     NO
ccacaa5 ancestor of 7c8560b  YES
main ancestor of #348        YES
main ancestor of #347        YES
7c8560b ancestor of #348     NO
346 vs 348 merge-base        0509287
348 vs 7c8560b merge-base    ccacaa5
```

```
ACTIVE_PRODUCTION_PR = 348
SUPERSEDED_PRODUCTION_PRS = 346
EVIDENCE_ONLY_PRS = 347, 349
```

#348 is the intended production merge lane because it contains `ccacaa5`
as an ancestor and its production trees equal the D-067 freeze. #346
diverged at `0509287` and does **not** contain `ccacaa5`.

## Lane B — production freeze integrity

Compared `ccacaa5` → `#348` tip `d762475`:

Changed paths (4), all `docs/evidence/`:

- `docs/evidence/D-067-INDEPENDENT-IV.md`
- `docs/evidence/D-067-LOCAL-REVALIDATION-RUNBOOK.md`
- `docs/evidence/D-067-SUPERSEDING-FREEZE.md`
- `docs/evidence/d067-premerge/VALIDATION-COMMANDS.md`

Production trees equal:

| Path | blob/tree |
| --- | --- |
| `src/` | `62d346252197c8812f933e0e09e6ddba602b0f59` |
| `apps/` | `6a9938729fac2a07542298586a171f7070a31dda` |
| `tests/` | `e5fef7136f71b3308a5feba003c59b4a774b57f1` |
| `pyproject.toml` | `9a7729d2e465d1855bf49aa7d1c119874120d48e` |
| `apps/web/package.json` | `ab745a8f93d370a85540887e6293596c6917eec2` |
| `.github/workflows` | `9c0449082d9e423b8afc0bfc24b17143f8b514a3` |

```
PRODUCTION_SEMANTIC_CHANGES_AFTER_D067_FREEZE = 0
UNCLASSIFIED_PATHS = 0
LOCAL_RESULT_APPLICABLE_TO_PR348 = YES
```

D-069 claim revalidated: `ccacaa5` → `7c8560b` is 23 `docs/evidence/`
paths, production trees identical, `UNCLASSIFIED_PATHS = 0`.

## Lane C — Local ingestion gate

```
LOCAL_D068_TARGET_HEAD = ccacaa5bcb094f35017c7195264fef55e382cb49
LOCAL_D068_TARGET_TREE = d26768fe753c888cd45001987da2afe977c79d45
D068_FINAL_RESULT = PENDING
VALIDATION_TARGET_STALE = NO   # required target; Local result not yet ingested
```

When Local returns, accept only if HEAD/TREE match exactly.
Wrong target → `VALIDATION_STALE`. FAIL/PARTIAL → `REMEDIATION_REQUIRED`.

## Lane D — lifecycle truth (do not rewrite)

```
9c71cc2 / 10539a86     D-063 candidate     INVALIDATED by D-064
0509287 / 728f3af      D-064 candidate     INVALIDATED by D-065
                       D065_WINDOWS_IV = FAIL
                       D065_HIGH_COUNT = 2
ccacaa5 / d26768       D-067 candidate     CURRENT semantic freeze
d762475                #348 tip            evidence-only above freeze
072f139                main                not yet merged
```

Historical D-064 / D-066 texts that still name `0509287` as then-current
are preserved as contemporaneous records, not current authority.

## Lane E — CI proof

Exact-freeze run `31779400311` on `ccacaa5`:

| Job | Conclusion |
| --- | --- |
| `quality (ubuntu-latest, 3.12, full)` | success |
| `quality (ubuntu-latest, 3.13, compat)` | success |
| `quality (windows-latest, 3.12, windows)` | success |
| `control-plane` | success |

```
D067_CI = PASS
D067_CI_RUN = 31779400311
D067_CI_COVERAGE = COMPLETE
```

#348 tip `d762475` also has the same four jobs green
(`31780224531`). That tip's production trees equal `ccacaa5`, so the
exact-code CI seal remains `31779400311`. Tip CI is inherited only with
this tree proof; it is not a substitute freeze identity.

## Lane F — #348 scope audit

D-067 production delta (`0509287` → `ccacaa5`) is exactly:

- `src/project_atlas/estate_discovery.py`
- `src/project_atlas/cli.py`
- `src/project_atlas/web_api/discovery.py`
- `apps/web/src/hooks/useEstateDiscovery.ts`
- `apps/web/src/pages/production/DiscoveryPage.tsx`
- `tests/unit/test_as_d049_067_high_remediation.py`

`main` → `#348` also includes the prior D-049 wave (estate discovery,
D-063/D-064 remediations, tests, web nav, WORKLOG, evidence). Those are
the intended D-049 production lane, not unrelated features.

`WORKLOG.md` is governance. No Conversational Capture / D-042 / OPT /
roadmap feature files.

```
UNRELATED_SCOPE_COUNT = 0
```

## Lane G — obsolete PR disposition (do not execute)

```
PR_346_DISPOSITION = CLOSE_AS_SUPERSEDED_BY_348
PR_347_DISPOSITION = CLOSE_AS_EVIDENCE_PRESERVED
PR_348_DISPOSITION = HOLD_THEN_OWNER_AUTHORIZE_MERGE
PR_349_DISPOSITION = CLOSE_AS_EVIDENCE_PRESERVED
```

Do not merge #346: it would reintroduce the invalidated `0509287`
production lineage and does not contain `ccacaa5`.

Do not independently merge #347 / #349: unique evidence is preserved on
this D-071 branch (historical files copied as-is; current state is this
receipt). Prefer one production history via #348.

## Merge target recommendation

After Local D-068 PASS on exact `ccacaa5` / `d26768` with
`NEW_HIGH=0` and `HIGH_STILL_OPEN=0`:

```
AUTHORIZED_PR = 348
SEMANTIC_FREEZE = ccacaa5 / d26768
PREFERRED_MERGE = merge commit (not squash)
EXPECTED_PARENT_1 = 072f1395ee310a876e93d633264f3ece43cecc3c
EXPECTED_PARENT_2 = <authorized #348 tip at authorization time>
```

Prefer merge-commit so `ccacaa5` remains an ancestor of `main`.
Squash would require re-recording the post-merge tree and would drop
freeze-commit ancestry.

Owner authorization remains a separate action. This receipt is not
authorization.
