# D-049 pre-merge readiness (Cloud independent review)

DIRECTIVE: `D-PROJECT-ATLAS-CLOUD-D049-PREMERGE-066`

Reviewer posture: reconstruct repository state independently. Do not treat
PR branch tip as the production target. Do not inherit prior implementer
conclusions as truth. Production semantics were not mutated. #346 was not
merged.

## Pins (independently reconstructed)

| Item | Value |
| --- | --- |
| CURRENT_MAIN | `072f1395ee310a876e93d633264f3ece43cecc3c` |
| MAIN_TREE | `ad29628bbf7552ebe8b4a71b0192d3004129375f` |
| PR_346 | https://github.com/B0LK13/project-atlas/pull/346 |
| PR_STATE | OPEN (draft) |
| PR_MERGEABLE | MERGEABLE / CLEAN |
| FROZEN_HEAD | `0509287c8915f3fe06644d5a00bcc219bd290add` |
| FROZEN_TREE | `728f3af450961db00d9a310293907cd3125272f6` |
| BRANCH_TIP | `d3a9458f478c3c06be0086622c3f262ec9938175` |
| BRANCH_TIP_TREE | `fe5046fa12a35010cacfd9aaa5b0c205b821f38f` |
| TREE_MATCH_FROZEN | YES (`0509287^{tree}` == `728f3af450961db00d9a310293907cd3125272f6`) |
| MAIN_IS_ANCESTOR_OF_FROZEN | YES |
| FROZEN_IS_ANCESTOR_OF_TIP | YES |

Production trees `src/`, `apps/`, `tests/`, and `pyproject.toml` are
byte-identical between `0509287` and tip `d3a9458`:

```
src  a9eea5967d74401d85ed8afdc9c0d2b3a56eee54
apps 425b20bb1667744656d65356a0e661e6bb80cff5
tests 969f6137255a75168ad372548b5167e4c43bdb02
pyproject.toml 9a7729d2e465d1855bf49aa7d1c119874120d48e
```

## Lane A — freeze integrity

Every commit after `0509287` on #346 is documentation / evidence only
(`docs/evidence/**`). No `src/`, `apps/`, `tests/`, or `pyproject.toml`
change after freeze.

PRODUCTION_SEMANTIC_CHANGES_AFTER_FREEZE = 0

LOCAL_VALIDATION_TARGET_STALE = NO

## Lane B — final diff review (main → `0509287`)

Production-semantic delta is the D-049 estate-discovery surface plus
wiring:

- `src/project_atlas/estate_discovery.py` (new)
- `src/project_atlas/cli.py` (estate `discover` / `review` / `connect`)
- `src/project_atlas/api_server.py`, `app_service.py`
- `src/project_atlas/web_api/discovery.py` (read-only projection)
- `apps/web` Discovery page / hook / nav (projection only)

Independent answers (code-traced on exact `0509287`, not tip):

| Question | Verdict |
| --- | --- |
| Does DISCOVERY become AUTHORITY? | No. Scan writes ops report/cache only. Ingest is a separate command. `atlas discover connect` is an explicit connect gate with TOCTOU revalidation. API/Web are read-only projections. |
| Does heuristic evidence silently become identity? | No. Heuristic layers are never `EXACT`. `matched_project_id` is a report field only. Vault identity is not written by discovery. |
| Is CONNECTED emitted without durable bind proof? | No on the fresh-scan path. `CONNECTED` requires `prove_connected()` (`EXACT`/`STRONG_EVIDENCE` plus governed bind-root equality or live `.atlas/connect.json`). `vault/projects/*` presence alone is rejected. Knowledge/Obsidian always `connected=False`. |
| Can userinfo/passwords reach output (required forms)? | No for the required URL matrix. See Lane C residual. |
| Unconsidered traversal / recursive-loop variant? | Linux self-loop, two-node loop, nested loop, broken target, dangling absolute, and outside-root symlink were independently probed. No crash, no unauthorized descent, `unsafe_path_escapes_allowed=0`. Windows reparse/junction remains Local D-065. |

Copied-marker observation (not a HIGH): a copied marker with the same
governed `project.id` + UUID can classify `match_state=EXACT` at a
different root. That is marker-claim matching, not identity minting.
`CONNECTED` still requires bind proof; non-connected EXACT requires
review. This is honest classification, not DISCOVERY→AUTHORITY.

API/Web stale-report observation (MEDIUM, not HIGH): `/v1/discovery`
projects the on-disk ops report without re-running `prove_connected`.
Labeled `UI != AUTHORITY`. Connect path revalidates live. Does not
promote discovery to authority.

FINAL_DIFF_REVIEW = PASS (no new HIGH on production-semantic delta)

## Lane C — D-064 remediations (independent)

### HIGH 1 — SYMLINK_LOOP_UNBOUNDED

Walk never descends reparse/symlink children. `Path.resolve` `RuntimeError`
is caught in the walk, `_reparse_escape`, and `_under_authorized`.
Independent Linux probes:

| Variant | Result |
| --- | --- |
| self-loop | no crash; ignored as reparse/escape |
| two-node loop | no crash; not descended |
| nested loop | no crash; not descended |
| broken / dangling target | ignored as escape; no descent |
| outside-root target | not listed as project; `unsafe_path_escapes_allowed=0` |
| authorized root containing a self-loop child | no crash |

D064_SYMLINK_FIX_REVIEW = PASS (Linux). Windows reparse/junction = Local D-065.

### HIGH 2 — GIT_REMOTE_PASSWORD_ECHO

`_git_remote_url` sanitizes before fingerprint/report/CLI/API/Web.

Required / likely forms independently probed (synthetic planted token only):

| Form | Echoed? |
| --- | --- |
| `https://user:password@host/repo.git` | No |
| `https://token@host/repo.git` | No |
| `http://user:password@host/repo.git` | No |
| `ssh://user@host/repo` | No (username stripped; no password) |
| `git+https://user:password@host/repo.git` | No |
| encoded userinfo (`p%40ss…`) | No |
| scp-like `git@host:org/repo.git` | Unchanged (no password convention) |

Residual (not in the required matrix): a *quoted* git-config URL value
(`url = "https://user:…@host/repo.git"`) is not parsed by `urlsplit`,
so userinfo is left in `fingerprint.git_remote`. Default `git remote add`
writes unquoted URLs. Classified MEDIUM residual, not NEW_SECURITY_HIGH.
Does not automatically invalidate the candidate (Lane I Case C).

KNOWN_SECRET_ECHO_PATHS (required matrix) = 0

D064_SECRET_FIX_REVIEW = PASS (required forms) + one documented MEDIUM residual

## Lane D — exact frozen HEAD validation

All commands were run against worktree `/tmp/d049-frozen` at
`0509287c8915f3fe06644d5a00bcc219bd290add` /
`728f3af450961db00d9a310293907cd3125272f6` with
`PYTHONPATH=/tmp/d049-frozen/src`. Not against PR tip.

| Gate | Command | Result |
| --- | --- | --- |
| D-049 / D-063 / D-064 | `pytest tests/unit/test_as_coder_alpha_049_estate_discovery.py tests/unit/test_as_d049_063_truth_hardening.py tests/unit/test_as_d049_064_high_remediation.py` | 30 passed |
| Identity / lineage / connect | `pytest tests/unit/test_source_identity.py tests/unit/test_as_coder_alpha_connect_001.py tests/unit/test_as_coder_alpha_057_copied_uuid.py tests/unit/test_claim_identity.py` | 46 passed |
| Broader Coder Alpha | `pytest tests/unit -k 'coder_alpha or d049 or connect or source_identity'` | passed (1 skipped) |
| Control Plane | `pytest atlas-vault-documentation/tests` | 171 passed |
| ruff | `python -m ruff check .` | All checks passed |
| mypy | `python -m mypy src` | Success: 185 source files |
| Web typecheck | `npx tsc -b` (no `typecheck` script; `build` uses `tsc -b`) | exit 0 |
| Web build | `npm run build` | `tsc -b && vite build` exit 0 |

EXACT_FROZEN_HEAD_VALIDATION = PASS

## Lane E — CI reconciliation

Mandatory matrix (`.github/workflows/ci.yml`): `quality` ubuntu 3.12 full,
ubuntu 3.13 compat, windows 3.12, plus `control-plane`. Concurrency
`cancel-in-progress: true`.

| Run | SHA | Conclusion | Notes |
| --- | --- | --- | --- |
| 31742695767 | `0509287` (exact frozen) | cancelled | Newer evidence push cancelled in-progress pytest. `control-plane` succeeded; ruff/mypy succeeded on ubuntu 3.12 before pytest cancel. |
| 31743617530 | `df23f34` (evidence-only descendant) | success | All 4 mandatory jobs green. Production trees identical to `0509287`. |
| 31744546692 | `d3a9458` (current tip, evidence-only) | success | All 4 mandatory jobs green. Production trees identical to `0509287`. |

CI_COVERAGE_OF_0509287 = COMPLETE

Proof: production-tree identity (`src`/`apps`/`tests`/`pyproject.toml`
SHAs equal) plus green mandatory matrix on identical-tree descendants
31743617530 and 31744546692. Direct-SHA pytest on `0509287` was
cancelled only due to newer evidence pushes. Cloud Lane D re-ran the
semantic suite on the exact SHA.

Do not treat the tip CI badge as a substitute for Lane D; they agree
because the production tree did not change.

## Lane F — security / privacy mini-audit

Threat-model review of the D-049 surface on `0509287`:

| Threat | Observation |
| --- | --- |
| Malicious tree / filenames / markers | Invalid/unreadable markers → CONFLICTING. Reads are size-capped. Binary NULs rejected. |
| Credential-bearing metadata | Required remote forms sanitized before report. Quoted-URL residual = MEDIUM. |
| Symlink / junction escape | Linux: no descend; outside targets ignored. Windows = Local D-065. |
| Huge tree | `max_depth=8`, candidate caps 500/500, truncation recorded, `scan_complete` honest. |
| Cross-project contamination | Knowledge association is nesting/name-hint only; Obsidian not auto-assigned; connect refuses knowledge/Obsidian/CONFLICTING/AMBIGUOUS. |
| Stale report / cache | Cache unused for skip. Connect TOCTOU revalidates. API/Web project ops report (UI ≠ authority). |
| Discovery report file-content leak | Report carries paths, signals, sanitized remotes, marker id/uuid — not file bodies. `_safe_read_text` used for markers/config/package names only. |
| Logs / exceptions | CLI logs exception type/message; connect errors do not embed raw remotes in the reviewed paths. |
| API/Web raw remotes | Projection of already-sanitized fingerprint field. |

NEW_SECURITY_HIGH = 0

SECURITY_MINI_AUDIT = PASS with one MEDIUM residual (quoted git-config URL)

## Lane G — merge content audit

Changed paths main `072f139` → frozen `0509287` classified:

| Class | Paths |
| --- | --- |
| PRODUCTION | `src/project_atlas/estate_discovery.py`, `cli.py`, `api_server.py`, `app_service.py`, `web_api/__init__.py`, `web_api/discovery.py` |
| WEB | `apps/web/src/App.tsx`, `ProdNav.tsx`, `hooks/useEstateDiscovery.ts`, `pages/production/DiscoveryPage.tsx` |
| TEST | `tests/unit/test_as_coder_alpha_049_estate_discovery.py`, `test_as_d049_063_truth_hardening.py`, `test_as_d049_064_high_remediation.py` |
| EVIDENCE | `docs/evidence/D-049-*`, `D-062-*`, `D-063-*`, `d064-overnight/*` |
| GOVERNANCE | `WORKLOG.md`, `docs/productization/install/LIMITATIONS.md` |

D-062 acceptance receipts unlock D-049; they are in-scope, not unrelated.
Post-freeze tip adds only more evidence under `docs/evidence/`.

UNRELATED_SCOPE_COUNT = 0

Expected merge payload: PR #346 (tip may include evidence commits).
Expected post-merge *production* tree: identical to `0509287` for
`src/`, `apps/`, `tests/`, `pyproject.toml`. Full commit tree will
differ if evidence commits are included.

## Decision fields

```
PRODUCTION_SEMANTIC_CHANGES_AFTER_FREEZE = 0
FINAL_DIFF_REVIEW = PASS
D064_SYMLINK_FIX_REVIEW = PASS
D064_SECRET_FIX_REVIEW = PASS
EXACT_FROZEN_HEAD_VALIDATION = PASS
CI_COVERAGE_OF_0509287 = COMPLETE
SECURITY_MINI_AUDIT = PASS
NEW_SECURITY_HIGH = 0
UNRELATED_SCOPE_COUNT = 0
POST_MERGE_RUNBOOK_READY = YES
LOCAL_RESULT = PENDING
D049_CLOUD_RECONCILIATION = WAITING_FOR_LOCAL
D_049_ACCEPTANCE = NOT_YET_EVALUATED
AUTHENTIC_USER_ESTATE_ACCEPTANCE = NOT_YET_PROVEN
D_042_EXECUTION_GATE = CLOSED
REPOSITORY_SEMANTIC_MUTATION = NO
NEXT_ACTION = WAIT FOR LOCAL D-065 WHILE MAINTAINING MERGE-READY EVIDENCE
```

Companion docs:

- `docs/evidence/D-049-POST-MERGE-RUNBOOK.md` (prepare only; do not execute)
- `docs/evidence/D-049-ACCEPTANCE-RECONCILIATION.md`
- `docs/evidence/D-049-AUTHENTIC-ESTATE-ACCEPTANCE-PLAN.md`
- `docs/evidence/d049-premerge/VALIDATION-COMMANDS.md`
