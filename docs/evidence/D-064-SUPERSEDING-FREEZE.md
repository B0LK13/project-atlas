# D-064 — Superseding D-049 Local freeze (HIGH remediations)

**Directive:** D-PROJECT-ATLAS-CLOUD-D049-OVERNIGHT-064-FINAL  
**PR:** https://github.com/B0LK13/project-atlas/pull/346  
**Branch:** `cursor/d049-knowledge-estate-discovery-d036`

## Invalidated prior freeze (do not Local-validate)

The D-063 Local-ready freeze is **INVALIDATED_BY_EVIDENCE** after overnight red-team:

```
PRIOR_FROZEN_D049_HEAD = 9c71cc2c71779678f79037c0c279390355015d63
PRIOR_FROZEN_D049_TREE = 10539a861dc9a5b32ebf00862d6710a66f3725cd
FROZEN_CANDIDATE_STATUS = INVALIDATED_BY_EVIDENCE
```

Validated HIGHs at prior tip:

| Code | Severity | Symptom |
|---|---|---|
| `SYMLINK_LOOP_UNBOUNDED` | HIGH | Mutual directory symlinks raised `RuntimeError: Symlink loop` from `Path.resolve`, crashing discovery instead of bounded ignore |
| `GIT_REMOTE_PASSWORD_ECHO` | HIGH | `fingerprint.git_remote` echoed `https://user:SECRET@…` into discovery reports / CLI / API / Web surfaces |

Do **not** rewrite `docs/evidence/D-063-LOCAL-FREEZE.md` history. This receipt supersedes it for Local targeting.

## Superseding production tip (Local validates THIS)

```
SUPERSEDING_D049_HEAD = 0509287c8915f3fe06644d5a00bcc219bd290add
SUPERSEDING_D049_TREE = 728f3af450961db00d9a310293907cd3125272f6
SUPERSEDING_CANDIDATE_READY = YES
LOCAL_D049_REVALIDATION_READY = YES
FROZEN_CANDIDATE_STATUS = VALID   # superseding tip only
```

Base remains:

```
BASE = 072f1395ee310a876e93d633264f3ece43cecc3c
CURRENT_MAIN = 072f1395ee310a876e93d633264f3ece43cecc3c
```

Remediation commit subject:

`fix(d049): remediate D-064 HIGH symlink-loop and git-remote secret echo`

Production semantic change surface:

- `src/project_atlas/estate_discovery.py`
  - catch `(OSError, RuntimeError)` on resolve paths; unresolvable reparse → escape/ignore
  - `sanitize_git_remote_url()` strips credential userinfo before fingerprints/reports
- `tests/unit/test_as_d049_064_high_remediation.py` (focused repro locks)

Evidence-only commits may sit above `0509287` on the PR branch (overnight metrics / IV).  
If branch tip differs, Local still checks out the HEAD/TREE above:

```bash
git fetch origin cursor/d049-knowledge-estate-discovery-d036
git checkout 0509287c8915f3fe06644d5a00bcc219bd290add
git rev-parse HEAD
# expect 0509287c8915f3fe06644d5a00bcc219bd290add
git rev-parse HEAD^{tree}
# expect 728f3af450961db00d9a310293907cd3125272f6
```

## Cloud status at superseding freeze

```
CODER_ALPHA_ACCEPTANCE = PASS
CODER_ALPHA_REGRESSION_HIGH = 0
D_049_EXECUTION_GATE = OPEN
D_049_STATE = IN_PROGRESS
D_049_ACCEPTANCE = NOT_YET_EVALUATED
D_049_TECHNICAL_CANDIDATE = PASS
D_042_EXECUTION_GATE = CLOSED
HIGH_OPEN = 0
WINDOWS_REPARSE_IV_REQUIRED = YES
AUTHENTIC_USER_ESTATE_ACCEPTANCE = NOT_YET_PROVEN
```

## Independent IV (Cloud)

See `docs/evidence/d064-overnight/INDEPENDENT_IV.md`.

All required IV questions answer **NO**. Overnight hard counters remain zero after remediation re-check.

## No tip mutation after this freeze receipt

After the superseding freeze receipt commit lands, do not mutate production semantics on this PR for cosmetic cleanup. Further Cloud docs-only evidence is allowed; Local target remains `0509287` / `728f3af4`.

Do **not** merge PR #346 on Cloud evidence alone. Local Windows IV required.
