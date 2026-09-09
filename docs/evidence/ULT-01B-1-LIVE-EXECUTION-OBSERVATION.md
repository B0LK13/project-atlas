# ULT-01b-1 — Live execution observation: evidence receipt

| Field | Value |
|---|---|
| Package | ULT-01b-1 (first slice of ULT-01b; planning source `docs/atlas-3/ultimate/ULT-01B-PACKAGE.md`, PR #764) |
| PR | #765, stacked on AT3-103 (#743, base `feat/at3-103-execution-identity-proof-v2` @ `0ff843aae4df1d7af08349a8a0f82ec55189cdd9`) |
| Directive | `GOAL = IMPLEMENT_TRUSTWORTHY_LIVE_EXECUTION_OBSERVATION`, `PACKAGE = ULT-01b-1`, owner decisions O1–O8 |
| Merge-base with `origin/main` | `e4dd17bc5956a7ebb2c044dbfd91749c796d38f1` (`origin/main` at receipt time `1b6953678238e911aa169fa7b5227451a3f626a3`; candidate unrebased by convention, stacked on #743 which is itself unmerged) |
| Certified object | **HEAD `e370807737e2f50553ca3dab2d1480c996365c1c` / TREE `594dc44d451b06a52ba70272c36c1ad3caeb669b`** (`src` `851943cd…`, `tests` `ef1a7692…`) |
| This receipt's commit | docs-only; `src` and `tests` trees are hash-identical to the certified object, so round-3 certification transfers by hash, not by assertion |
| `MERGE_AUTHORIZATION` | **NOT_GRANTED** |
| `ULT_01B_SLICE_2` / `ULT_01B_SLICE_3` | **NOT_STARTED** |

## 1. Candidate history — every verification is bound to one exact object

| Round | HEAD | TREE | IV | ADV | CI (exact head) | Status |
|---|---|---|---|---|---|---|
| 1 | `0ed995846e9617147b001fbbd027f91b08fece7c` | `40d78264ff61c85a73ea20f2e2e19e9904c38fba` | PASS_WITH_NONBLOCKING_FINDINGS (P2×1) | PASS_WITH_FINDINGS (P2×1, same finding) | green (run 34329114548) | SUPERSEDED_BY_REMEDIATION |
| 2 | `c549affe4059e0ba934c573c5dc4206ae5ddfe7c` | `2e0ee49239e208e5b3f1fe8032c73e1ca73a2efa` | PASS_WITH_NONBLOCKING_FINDINGS (P0=P1=P2=0, P3×5) | PASS_WITH_FINDINGS (P2×2: multi-valued remote url read last-wins; repo-local `core.fsmonitor` executed) | **failure** (run 34332446481: Windows job red — `GIT_CONFIG_NOSYSTEM` bypassed `core.autocrlf`, honest checkouts observed dirty; ubuntu 3.12/3.13 and control-plane green) | SUPERSEDED_BY_REMEDIATION |
| 3 | `e370807737e2f50553ca3dab2d1480c996365c1c` | `594dc44d451b06a52ba70272c36c1ad3caeb669b` | PASS_WITH_NONBLOCKING_FINDINGS (**P0=P1=P2=0**, P3×4) | PASS_WITH_FINDINGS (**P0=P1=P2=0**; P3 only) | green (run 34336249016, 4/4 incl. Windows) | CERTIFIED CANDIDATE |

Predecessor evidence is retained as history; none of it transfers to round 3
(`TARGET MOVED`). Both verifiers used their own three-value vocabulary; a
P3-only result is the qualifying outcome and the P3 residuals are recorded in
§7. The implementer does not self-certify: the verdict lines above are quoted
from the verifiers' reports, each bound to the exact HEAD/TREE.

## 2. What the certified object contains

- `src/project_atlas/execution_observation/` — new isolated package
  (`runner.py`, `git.py`, `host.py`, `observe.py`, `store.py`): the only place
  observation launches a process. `src/project_atlas/atlas3/` stays
  subprocess- and clock-free (pinned by test; import graph checked by IV/ADV).
- `src/atlas_contracts/observation_receipt.py` — `atlas.observation-receipt.v1`:
  embeds the sealed `ExecutionIdentity`; every dimension is cross-checked
  against the identity's `OBSERVED | UNKNOWN` blocks; `content_hash` and
  `observation_id` self-verify; **no timestamp**; `observed_is_current` is a
  strict bool that must be `false`; `authority = "derived"`,
  `merge_authorization = "NOT_GRANTED"` are Literals; observer must be a
  `tool`; method refs can never carry `://` or `@`. JSON schema (STRUCTURAL).
- Git observation (`git.py`): argv only, `shell=False`, stdin closed, bounded
  timeout, stdout capped; child environment **constructed from nothing** (no
  inherited `GIT_*`; git's configuration files are read as git reads them,
  because content interpretation is part of the checkout) with
  `core.fsmonitor` pinned off at environment level; configured content
  filters bound to any path refuse the observation before `git status`
  (`REPO_CONTENT_FILTERS_CONFIGURED`); submodule work trees not observed
  (`--ignore-submodules=dirty`; a moved gitlink is dirty); work-tree
  top level must equal the resolved root; candidate pins **only on a clean
  worktree**; base pins from `origin/main` by default with a recorded
  `--base-ref` override (O8); pins validated by `trust.require_full_pin`;
  remote read raw via `git config --get-all remote.<name>.url` and required
  to be exactly one value (`REMOTE_URL_AMBIGUOUS`), normalized by
  `trust.normalize_repository_identity`, never persisted or echoed; userinfo
  other than the bare `git@` user, hostless, local-path and `file://` remotes
  refused; shallow-ness recorded; `.exe`-only executable on Windows.
- Environment (`host.py`): `platform`/`sys` normalized to a fixed vocabulary
  (O4); unmapped → block `UNKNOWN` with reason, never guessed.
- Toolchain (`host.py`): declared set (O5) via `importlib.metadata` plus the
  parsed `git --version`; absent recorded as absent; executable paths never
  persisted (path digest only).
- Agent, context, capabilities: `UNKNOWN` with reason codes (O2, O6; ULT-01b-3).
- Storage (`store.py`) under `generated/ops/atlas3/observation/v1/<project>/<digest16>.json`
  through `write_locator_json` in `atlas3/contracts.py` (lifted from proof v2
  and shared with it): lexical containment gate before `mkdir`, `lstat` walk
  refusing symlinks and Windows junctions before and after `mkdir`, resolved
  containment re-check, collision never overwritten (a different receipt for
  the same identity is refused; a past observation is never replaced).
- Proof v2: `evaluate_proof_v2(..., observation_receipt=...)` — a receipt bound
  to the same identity digest sets `live_observation_wired: true` and
  `observation_id`; a receipt can never make a stage PRESENT;
  `observed_is_current: false` is reported. **Proof v1 byte-identical**
  (3 + 8 golden digests re-run each round).
- CLI: `atlas observe-execution` (fails closed `AUTHZ_DENIED` /
  `authz-unknown-capability:execution.observe` until the owner registers the
  capability) and `atlas proof --observation <file>`. Root `cli.py` untouched.
- Owner gate carried honestly (O3): `src/project_atlas/authz.py` is
  byte-identical to `origin/main`; the exact registration change is
  `docs/evidence/ULT-01B-1-authz-execution-observe.patch` (applies cleanly).
- Docs: `docs/atlas-3/ULT-01B-1.md`, PACKAGE-MATURITY entry
  `ult-01b-1-execution-observation`, backlog line, and
  `docs/scripts/ult_01b_1_negative_controls.py` with this receipt's control
  output `docs/evidence/ULT-01B-1-negative-controls-e3708077.json`.

## 3. Implementer-run gates at the certified object

| Gate | Result |
|---|---|
| ruff | `All checks passed!` |
| mypy `src` | `Success: no issues found in 415 source files` |
| New suites (receipt contract, observer unit, live integration on real temporary repositories) | 118 passed, 0 failed |
| Affected (18 files: AT3-103 suites, proof v1, foundation, capabilities, atlas3 CLI, contracts, demo isolation, IV/ADV bind, ADV control, program docs, CLI surface contract, backlog labels, SEC-009 authz, the three new suites) | 452 passed, 0 failed |
| Full suite (junit) | 6086 collected, 6074 passed, 8 skipped, 4 xfailed, 0 failed |

Counts come from `--junitxml`; this repository's pytest prints no summary line.

## 4. Negative controls (falsification)

`docs/scripts/ult_01b_1_negative_controls.py` applies 30 source mutations,
one at a time, under a sha256 assertion that the mutation changed the file and
that the source was restored byte-identical. Baseline: 118 tests, 0 failures.
Every one of the 30 controls kills at least one test (30/30); 30 distinct failing sets (`pairwise_distinct: True`, `each_nonempty: True`). Full per-control failing-test names:
`docs/evidence/ULT-01B-1-negative-controls-e3708077.json`.

| Control | Kills |
|---|---|
| OC-A dirty worktree accepted | 4 |
| OC-B pin validation dropped | 5 |
| OC-C userinfo remote accepted | 4 |
| OC-D child env inherited | 3 |
| OC-E windows wrapper accepted | 1 |
| OC-F unmapped arch guessed | 1 |
| OC-G toolchain invalid version accepted | 1 |
| OC-H receipt dimension/identity consistency dropped | 1 |
| OC-I receipt hash recomputation skipped | 6 |
| OC-J method refs may carry urls | 6 |
| OC-K proof linkage identity check dropped | 1 |
| OC-M store symlink walk dropped | 1 |
| OC-O root must be toplevel dropped | 2 |
| OC-P base-ref validation dropped | 1 |
| OC-Q timeout not distinguished | 2 |
| OC-R secret scan of receipt dropped | 1 |
| OC-S receipt observer kind widened to model | 4 |
| OC-T unsafe project id accepted | 1 |
| OC-U core.fsmonitor pin dropped (repo/global hook command would run) | 2 |
| OC-V remote read through get-url (insteadOf applied) | 23 |
| OC-W hostless/local-path remote accepted | 3 |
| OC-X same-identity different receipt overwritten | 1 |
| OC-Y raw remote url secret scan dropped | 1 |
| OC-Z observed_is_current strictness dropped | 1 |
| OC-AA store digest argument unvalidated | 1 |
| OC-AB base-ref length ceiling dropped | 1 |
| OC-AC multi-valued remote url accepted (first taken) | 2 |
| OC-AD bound content filter scan dropped | 2 |
| OC-AE submodule work trees observed (nested git status spawned) | 2 |
| OC-AF filter driver name not validated | 1 |

`docs/scripts/at3_103_negative_controls.py` (28 controls, NC-N/U/V/AB
re-anchored onto the shared helper in `contracts.py`) remains 28/28 kill at
this object, so the lift of the locator helper out of `proof.py` did not
weaken any AT3-103 guard.

## 5. Exact-head CI at `e3708077` (run 34336249016)

All four jobs `success` (conclusion read from the run, not assumed):

| Job | Result (CI's own pytest summary line) |
|---|---|
| `quality (ubuntu-latest, 3.12, full)` | ruff / mypy green; `6074 passed, 8 skipped, 4 xfailed` |
| `quality (ubuntu-latest, 3.13, compat)` | `6074 passed, 8 skipped, 4 xfailed` |
| `quality (windows-latest, 3.12, windows)` | `6017 passed, 62 skipped, 3 deselected, 4 xfailed`; line-ending golden fixture `1 passed` — the round-2 Windows failure (`WORKTREE_NOT_CLEAN` on every live observation test) is gone at this head |
| `control-plane` | success |

The round-2 run 34332446481 at `c549affe` is retained as history: ubuntu 3.12 / 3.13 / control-plane green, Windows **failure** (five live observation tests refused honest checkouts as dirty because `GIT_CONFIG_NOSYSTEM=1` bypassed the system `core.autocrlf=true`).

## 6. Independent and adversarial verification — findings and closures

### Round 1 on `0ed99584` (superseded)

IV and ADV converged on one P2: `HOME` was passed through to the child, so the
operator's `~/.gitconfig` (`url.<base>.insteadOf`, directly or via
`[include] path=`) rewrote the observed, digest-bound repository identity,
because the remote was read through `git remote get-url`, which applies
rewrites; a global `core.fsmonitor` could also run under `git status`.
P3s (ADV): NUL in a reported toplevel escaped as a raw `ValueError`; empty
`remote.origin.url` yielded identity `origin`; a local-path remote yielded a
path fragment; a secret-shaped remote path segment was lowercased by
normalization before the receipt secret scan; base refs of 106+ characters
failed late as `RECEIPT_UNSEALABLE`; scp port folded into the path (inherited
from `normalize_repository_identity`, still open — §7). P3s (IV): the store
keyed collisions on `identity_digest` only, so a different receipt for the
same identity silently overwrote the stored one; `OBSERVATION_PROJECT_MISMATCH`
in proof v2 was unreachable; a local-path remote (including a username) was
persisted as the repository identity; the symlinked-root decision was
undocumented; `worktree_clean` is a constant `True` in a sealed receipt
(dirty states raise earlier; kept, documented); the planning's "containment
re-checked after `mkdir`" was not implemented; no WORKLOG entry.
Implementer-found while remediating: `observed_is_current` Literal accepted
`0`; receipt `base_ref` accepted `..`; store digest argument unvalidated;
unreadable stored receipt reported as absent.
**All closed in round 2** (`c549affe`): `GIT_CONFIG_GLOBAL=<devnull>` and
`GIT_CONFIG_NOSYSTEM=1` fixed in the constructed child environment; remote
read raw via `git config --get remote.<name>.url`; hostless / local-path /
`file://` remotes refused; raw URL secret-scanned before normalization; NUL
toplevel → `GIT_ROOT_MISMATCH`; `MAX_BASE_REF_LENGTH = 100`; strict
`observed_is_current`; receipt `base_ref` refuses `..`; store digest validated
(`OBSERVATION_DIGEST_INVALID`); unreadable → `OBSERVATION_RECEIPT_UNREADABLE`;
different receipt for the same identity → `OBSERVATION_LOCATOR_COLLISION` with
stored bytes intact; lexical gate before `mkdir`; dead branch removed. Seven
new controls (OC-V…OC-AB) falsify the new guards.

### Round 2 on `c549affe` (superseded)

IV: no P0/P1/P2; P3s: `observed_is_current=0` refused by `StrictBool` rather
than by `OBSERVED_IS_NOT_CURRENT` (refusal holds); `normalize_repository_identity`
canonicalization nits (trailing slash defeats `.git` stripping; `:/` gives an
empty segment; owner-only URL accepted); single-label intranet hosts refused as
hostless; `worktree_clean` constant; no WORKLOG entry.
ADV: two P2s, both in `git.py`. **A1** — `git config --get` returns the LAST
value of a multi-valued `remote.<name>.url` while a fetch contacts the FIRST,
so a repo-local `--add`, an `[include]`/`[includeIf]` append or a worktree-config
append recorded a repository git would never contact. **A2** — a repo-local
`core.fsmonitor` command was executed by the observer's `git status`
(`core.hooksPath`, aliases, pager, sshCommand, credential helpers, external
diff were not). P3s: refused legitimate remote forms (ssh with port,
`localhost`, IPv6); identity splits and case-collisions in the pre-existing
normalizer; receipt `base_ref` ceiling 128 vs observer 100; a locator equal to
the namespace writes a file named `v1` (helper-level only); a dangling-symlink
locator reads as absent; wrong `content_hash` on load raises a raw pydantic
error; TOCTOU window characterized (300 races, 0 escapes, 4 refusals).
Exact-head CI: the Windows job failed — `GIT_CONFIG_NOSYSTEM=1` bypassed the
system `core.autocrlf=true` the fixture checkouts were made under, so every
honest Windows checkout observed as `WORKTREE_NOT_CLEAN`.
**All three closed in round 3** (`e3708077`): remote read with
`--get-all -z`, exactly one value required; `core.fsmonitor` pinned off through
environment-level config (overrides every file level); configured content
filters (`filter.<driver>.clean|smudge|process`, e.g. git-lfs) bound to any
tracked or untracked path — evaluated by git itself via
`ls-files --cached --others ':(attr:filter=<driver>)'`, nothing executed —
refuse the observation before `git status`; submodule work trees excluded
(`--ignore-submodules=dirty`) so no nested `git status` is spawned; the two
config-bypass variables removed so content interpretation follows git
(reproduced on Linux: a clone made under `core.autocrlf=true` observes clean
under that configuration and dirty under `autocrlf=false`). Live tests carry
positive controls proving the hook and filter commands do fire under the
operator's own `git status`. P3s recorded in §7.

### Round 3 on `e3708077` (certified candidate)

IV: no P0/P1/P2. P3s: the package doc's "any bound path is refused before
`git status`" overclaims — a path that is itself untracked and bound only
through an untracked `.gitattributes` is invisible to `ls-files ':(attr:…)'`
(index-based attributes) and is refused later by `git status` as
`WORKTREE_NOT_CLEAN` without the filter executing (git does not run filters
for untracked paths; IV's positive control confirmed); `core.excludesFile`
not named as a report-shaping vector; a `filter.<d>.required` driver with no
clean command makes git's own `status` exit 128 → `GIT_UNOBSERVABLE`
(coded, nothing executed, code name uninformative); carried nits. Both doc
P3s are corrected in this receipt's docs-only commit (`ULT-01B-1.md`).
ADV: no P0/P1/P2; both round-2 P2s CLOSED from the attacking side (multivar
across levels, include/includeIf/worktree-config appends, NUL/newline values,
parent `GIT_CONFIG_COUNT`/`GIT_CONFIG_PARAMETERS` dropped; fsmonitor script,
hook versions and builtin daemon never started; every other configurable
command — hooksPath, pager, editor, sshCommand, credential helper, external
diff/textconv, merge driver, aliases, askPass, gpg — never executed under the
exact argv set; blocking FIFOs in `include.path`/`core.attributesFile`/
`core.excludesFile` → `GIT_OBSERVATION_TIMEOUT`). Content-filter refusal held
in every binding form (committed/untracked/nested/info/attributesFile/macros/
includeIf-only/worktree-only/HOME-only drivers, process-only, smudge-only)
with the control proving plain `git status` would have executed the clean
filter. `--ignore-submodules=dirty`: moved gitlink refused even under
`diff.ignoreSubmodules=all`, `submodule.<n>.ignore=all` and `.gitmodules
ignore=all`; submodule-local fsmonitor/filter never run; nested plain repo
→ `WORKTREE_NOT_CLEAN` with its hooks never run. Reversal residuals rated P3:
HOME `core.excludesFile`, `core.ignoreStat` (only after an index refresh under
it) and index bits can make git's own cleanliness view more permissive; no
config changed a pin or identity. P3s → §7. Harness: 124 mutants, 92 killed;
two surviving load-bearing filter-scan mutants (W12 regex reduced to `clean`;
W20 `--local`-only scan) hold on probe and need tests.

## 7. Residual register (recorded, not fixed; none blocks)

| Residual | Class | Owner / next package |
|---|---|---|
| Trust boundary: the `git` executable first on `PATH` (or passed via `git_executable`) is the observer's instrument; only its path digest is bound. An internally consistent hostile git produces a sealed identity. Provenance of the binary is outside this slice | DOCUMENT_CONTRACT | recorded in `ULT-01B-1.md`; toolchain attestation is ULT-01b-2/ULT-07 material |
| Repo-local configuration is inherent to observing through git: a repo-local `url.insteadOf` no longer changes the identity (raw config read), but repo-local `core.fsmonitor`/hooks are git's own execution surface under `git status`; the observation runs only on a clean worktree the operator already controls | DOCUMENT_CONTRACT | — |
| TOCTOU between the `lstat` walks and `mkdir`/tmp-write/`os.replace` (no `O_NOFOLLOW`/dirfd anchoring); requires concurrent write access inside the vault | DEFER_WITH_RESIDUAL | storage hardening package (inherited from AT3-103) |
| Windows junction refusal via `Path.is_junction()` is reasoned and exercised only by Windows CI's test run; not exercised on a real junction | DEFER_WITH_RESIDUAL | Windows stranger validation |
| `observed_is_current` is fixed `false`: freshness is a consumer decision (`OBSERVED != CURRENT`); no receipt can claim currency | DOCUMENT_CONTRACT | ULT-01b-2 consumes; never sets |
| `normalize_repository_identity` (pre-existing, `orchestration/autonomy/trust.py`) folds an scp-style port into the path and lowercases the whole identity; two remotes differing only in case collapse (intended); an scp-form remote with a port (`git@host:2222/owner/repo`) folds the port into the path (`host/2222/owner/repo`) rather than being refused, while `ssh://host:22/…`, `https://host:443/…` and IPv6 literals are refused | DOCUMENT_CONTRACT / DEFER_WITH_RESIDUAL | trust normalization package |
| A gitignored-only dirty file is "clean" (git's own definition via `--untracked-files=all`); ignored build output cannot enter the tree, so the candidate tree pin is unaffected | DOCUMENT_CONTRACT | — |
| Unparsable `git --version` records git as absent from the toolchain and proceeds (`UNKNOWN != FAILURE`); injected text never persisted | DOCUMENT_CONTRACT | — |
| `execution.observe` is not registered in `authz.py` (certified frozen surface); the CLI fails closed until the owner applies `ULT-01B-1-authz-execution-observe.patch` with a sha256-pinned DENY exception | OWNER_GATE | owner |
| Agent, context and capability observation are `UNKNOWN` by decision (O2, O6) | DOCUMENT_CONTRACT | ULT-01b-3 / ULT-03a |
| IV/ADV observation integration (verifier attestations bound to an observation) | NOT_STARTED | ULT-01b-2 (O7) |
| JSON schema is STRUCTURAL; the nested `identity` object is validated by the identity contract, not by the receipt schema | DEFER_WITH_RESIDUAL | future SDK work |
| Content-filter checkouts (git-lfs and any bound `filter.<driver>`) are refused in this slice rather than observed; observing them would execute the driver | DOCUMENT_CONTRACT | a later slice may observe them under an explicit owner decision |
| Configuration that changes what git *reports* without executing anything (`core.ignoreStat`, `core.checkStat`, sparse/skip-worktree/assume-unchanged index bits, `core.excludesFile`) can hide worktree changes from `git status`; the candidate tree pin is unaffected, and the same principal controls `.git` outright | DOCUMENT_CONTRACT | — |
| Git version: the attribute pathspec magic used by the filter scan requires a git that supports `:(attr:…)` pathspec magic with `ls-files --others` (verified on the git in this environment and in CI, not against a minimum version); an older git fails closed as `GIT_UNOBSERVABLE` | DOCUMENT_CONTRACT | — |
| Single-label intranet hosts, ssh remotes with an explicit port, `localhost` and IPv6 literals are refused (fail-closed, unobservable); identity splits (`repo.git/`, `:/owner`), owner-only URLs and case-collisions on case-sensitive hosts in the pre-existing `normalize_repository_identity` | DEFER_WITH_RESIDUAL | trust normalization package |
| Receipt contract accepts `base_ref` up to 128 chars while the observer caps 100 (contract is the wider gate; observer-produced receipts never exceed 100) | DEFER_WITH_RESIDUAL | next contract change |
| `write_locator_json` with a locator equal to its namespace writes a file named after the namespace (reachable only through the helper, not through `store_observation_receipt` or proof v2) | DEFER_WITH_RESIDUAL | storage hardening |
| `load_stored_receipt`: a dangling-symlink locator reads as absent (`exists()` follows the link); a stored receipt whose `content_hash` is wrong raises a raw pydantic error rather than `OBSERVATION_RECEIPT_UNREADABLE` | DEFER_WITH_RESIDUAL | next `store.py` change |
| `observed_is_current=0` is refused by `StrictBool` before `OBSERVED_IS_NOT_CURRENT` can name it (refusal holds either way) | DOCUMENT_CONTRACT | — |
| `worktree_clean` in a sealed receipt is always `true` (dirty states refuse earlier); recorded as a fact of the observed object, not a variable | DOCUMENT_CONTRACT | — |
| Mutation-harness survivors at round 2 (ADV: 106 mutants, 80 killed): redundant guards, junction/TOCTOU-only branches, and test gaps for guards that hold on probe (stdin closed, stdout cap, NUL env, `--untracked-files=all`, path-digest value, FIFO locator, bounded `--observation` reader) | DEFER_WITH_RESIDUAL (tests only) | first follow-up test package |
| Content-filter scan reach: a purely untracked path bound only through an untracked `.gitattributes` is not listed by `ls-files ':(attr:…)'`; it is refused by `git status` as `WORKTREE_NOT_CLEAN` and git runs no filter for untracked paths (IV positive control) | DOCUMENT_CONTRACT | — |
| Over-refusal: smudge-only drivers, bindings on ignored or sparse-excluded paths, and every git-lfs checkout with tracked LFS-bound files are refused rather than observed; the 16-driver cap counts system/global drivers (git-lfs installs three) | DOCUMENT_CONTRACT / DEFER_WITH_RESIDUAL | a later slice under an explicit owner decision |
| A repository with no `remote.<name>.url` of its own but one supplied by HOME/system config is observed with that configured identity (git's own view; the receipt records `remote_name`, not the level) | DOCUMENT_CONTRACT | — |
| `filter.<d>.required` without a clean command: git's own `status` exits 128 → `GIT_UNOBSERVABLE` (nothing executed; code name does not say why) | DEFER_WITH_RESIDUAL | next `git.py` change |
| Two load-bearing filter-scan guards have no falsifying test (ADV W12: regexp reduced to `clean` only; W20: scan restricted to `--local`); both hold on direct probe | DEFER_WITH_RESIDUAL (tests only; kept out of this commit to keep `tests/` at the certified hash) | first follow-up test package |
| Blocking files planted via `include.path` / `core.attributesFile` / `core.excludesFile` (FIFO) stall git until the bounded timeout (`GIT_OBSERVATION_TIMEOUT`) | DOCUMENT_CONTRACT | — |

## 8. Failure-pattern candidates (for future Skill / Verifier / Eval material)

```text
FP — "environment constructed from nothing" while a pass-through variable
     (HOME) still selects configuration the instrument reads       (round 1, S2)
FP — porcelain command used where a raw read exists (get-url vs config --get) (round 1)
FP — normalization applied before the security scan of the raw value (round 1, S3)
FP — Literal-typed field accepting a coercible value (0 for false)  (round 1, S4)
FP — "absent" and "unreadable" collapsed into one return value       (round 1, S8)
FP — filesystem check ordered after the side effect it guards (mkdir) (round 1/2, S5)
FP — control anchor drifts silently after a refactor (re-anchor and assert) (rounds 1–2)
FP — implementation guard exists without falsifying test           (round 1, S11)
```

## 9. Claims

**Proven at `c549affe`:** live git, environment and toolchain observation
populate an `ExecutionIdentity` whose every OBSERVED value equals the
instrument's output (`OBSERVED != CLAIMED`); unmapped or unobservable
dimensions are `UNKNOWN` with a reason and never a guess (`UNKNOWN !=
FAILURE`); nothing in the receipt comes from model output (`MODEL_OUTPUT !=
OBSERVATION`); the receipt carries no timestamp and can never claim currency
(`STALE_OBSERVATION != CURRENT_OBSERVATION`); the receipt has no authority
field and `merge_authorization` is fixed `NOT_GRANTED` (`OBSERVATION !=
AUTHORITY`); the raw remote URL, executable paths and secret-shaped values are
never persisted or echoed (`SECRET != EVIDENCE_PAYLOAD`); candidate pins exist
only for a clean worktree (`DIRTY_WORKTREE != VALID_CANDIDATE_OBSERVATION`);
`trust.py` normalization/pin rules and the proof v2 locator helper are reused
(`REUSE_BEFORE_REIMPLEMENT`); proof v1 byte-identical (`PROOF_V1_BEHAVIOR =
PRESERVED`); `atlas3/` subprocess- and clock-free (`ATLAS3_PURE_BOUNDARY =
PRESERVED`); the receipt is content-bound and deterministic across processes
and hash seeds; proof v2 links a receipt to its identity by digest
(`PROOF_V2_LIVE_OBSERVATION_LINKAGE = OPERATIONAL`); no inherited environment
variable or global/system git configuration can shape an observed value.

**Not made:** merge authority; independent verification by the implementer;
agent/context/capability observation; IV/ADV attestation ingestion
(ULT-01b-2); a freshness claim; provenance of the `git` binary; protection
against a writer who already holds write access inside the vault or the
repository's own `.git`; Windows execution beyond CI's test run; SLSA or any
compliance claim; `ULT_01B_SLICE_2` or `ULT_01B_SLICE_3` progress.
