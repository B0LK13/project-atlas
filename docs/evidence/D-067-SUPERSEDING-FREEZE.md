# D-067 superseding freeze

DIRECTIVE: `D-PROJECT-ATLAS-CLOUD-D049-REMEDIATION-067`

Invalidates merge candidate `0509287c8915f3fe06644d5a00bcc219bd290add` /
`728f3af450961db00d9a310293907cd3125272f6` because Local D-065 independently
validated two HIGHs on that exact target.

History of `0509287` is preserved. It is no longer merge-eligible.

## Superseding production candidate

```
D067_SUPERSEDING_HEAD = ccacaa5bcb094f35017c7195264fef55e382cb49
D067_SUPERSEDING_TREE = d26768fe753c888cd45001987da2afe977c79d45
PARENT = 0509287c8915f3fe06644d5a00bcc219bd290add
BRANCH = cursor/d049-d067-high-remediation-6f85
```

This commit is the production freeze. Later evidence-only commits on the
same branch must not be treated as the Local IV target.

`D067_CANDIDATE_READY = YES`
`LOCAL_D067_REVALIDATION_READY = YES`

## Reproduction (before mutation, exact `0509287`)

```
HIGH_1_CACHE_REPRO = PASS
HIGH_2_DEPTH_REPRO = PASS
```

`cache/` decoy project was discovered; other ignore hosts were not.
A project beyond `max_depth=8` was omitted while `scan_complete=true`
and human CLI printed no `SCAN INCOMPLETE`.

## Remediations (narrow)

| Item | Change |
| --- | --- |
| HIGH 1 | Exact ignore name `cache` added beside `.cache` |
| HIGH 2 | `depth_limit_reached` when a non-ignored, non-reparse directory child exists at `depth >= max_depth` |
| CLI help | cwd default + `max_depth=8` (not a new flag) + `SCAN INCOMPLETE` |
| MEDIUM | unwrap one matching git-config quote pair before `urlsplit` |

Passing D-065 surfaces (symlink/reparse, identity, stale cache, Obsidian,
API/Web parity of match semantics) were not reopened.

## Local D-067 revalidation (narrow — do not replay all of D-065)

Target exact `ccacaa5` / `d26768` only.

1. `cache/` fake-project exclusion
2. substring controls (`project-cache`, `cache-service`, `cached`, `cachex`, `my-cache-project`) remain discoverable
3. depth 8+ truncation honesty (`scan_complete=false`, `depth_limit_reached=true`)
4. human CLI `SCAN INCOMPLETE` + depth line
5. `atlas discover --help` names cwd default and `max_depth=8`
6. CLI JSON / API / Web scan-completeness parity
7. quoted git-config URL userinfo not echoed
8. bounded smoke: junction/reparse, identity isolation, stale report, Coder Alpha regression

## Merge rule

`PR_346_MERGE_RECOMMENDATION = BLOCKED`

Required before any merge eligibility:

- Cloud D-067 PASS (this freeze)
- Cloud independent IV PASS
- CI PASS on `ccacaa5`
- Local narrow revalidation PASS on exact HEAD/TREE
- `HIGH_OPEN = 0`

`D_042_EXECUTION_GATE = CLOSED`
`AUTHENTIC_USER_ESTATE_ACCEPTANCE = NOT_EVALUATED`
