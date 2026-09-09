# ULT-01b-1 — Live execution observation (first slice of ULT-01b)

Isolated runtime package `src/project_atlas/execution_observation/`
(Ultimate Atlas planning alias ULT-01b-1; canonical AT3 id owner-assigned).
Populates the AT3-103 `ExecutionIdentity` from trustworthy live observation
and produces a content-bound `atlas.observation-receipt.v1`. Does not mutate
certified 2.x surfaces; `src/project_atlas/atlas3/` stays subprocess- and
clock-free (this package is the only place observation launches a process).

- Observed (git, argv-only, bounded, child env constructed from nothing —
  no inherited `GIT_*`; git's configuration files are read as git reads them
  because content interpretation (`core.autocrlf`, `core.symlinks`,
  `safe.directory`) is part of the checkout, while no configuration can
  rewrite the identity or execute a command: `core.fsmonitor` is pinned off
  through environment-level config, the remote is read raw via
  `git config --get-all` and must be exactly one value (`--get` would report
  the last url while a fetch contacts the first → `REMOTE_URL_AMBIGUOUS`),
  and a checkout with any configured content filter bound to a tracked path
  (or an untracked path visible to the index-based attribute scan) is
  refused before `git status` (`REPO_CONTENT_FILTERS_CONFIGURED`; git-lfs
  checkouts are therefore not observable in this slice; a purely untracked
  path bound only through an untracked `.gitattributes` is instead refused
  by `git status` as `WORKTREE_NOT_CLEAN`, and git runs no filter for
  untracked paths); submodule work trees are not observed
  (`--ignore-submodules=dirty`; a moved gitlink is dirty, a dirty submodule
  work tree is not part of the observed object); configuration that only
  shapes what git *reports* without executing anything (`core.excludesFile`,
  `core.ignoreStat`, index bits) can make git's own cleanliness view more
  permissive — the same principal controls `.git`; pins are unaffected;
  local-path/hostless remotes refused; a symlinked root is resolved and the
  real tree is what is observed):
  repository identity (remote URL normalized, never persisted), base head +
  tree (`origin/main` by default; `--base-ref` override recorded), candidate
  head + tree **only on a clean worktree**; shallow-ness recorded.
- Observed (in-process): `os`/`arch`/`python` normalized to a fixed vocabulary;
  an unmapped value leaves the block `UNKNOWN`.
- Observed (`importlib.metadata` + `git --version`): the declared toolchain
  set; absent distributions recorded as absent; module `__version__` never
  consulted; executable paths never persisted (digest only).
- `UNKNOWN` in this slice, by owner decision: agent (O2 → ULT-01b-3), context
  (O6 → ULT-03a), capabilities (→ ULT-01b-3).
- Contract: `atlas_contracts.observation_receipt` — embeds the sealed identity,
  cross-checks every dimension against the identity's `OBSERVED|UNKNOWN`
  blocks, `content_hash` + `observation_id` self-verify, **no timestamp**
  (`observed_is_current: false` — `OBSERVED != CURRENT`), observer must be a
  `tool`, method refs can never carry URLs or userinfo, no authority field.
- Storage: `generated/ops/atlas3/observation/v1/<project>/<digest16>.json`
  through the shared locator helper (lifted from proof v2): `lstat` walk on
  the unresolved path incl. Windows junctions, `mkdir` before the resolved
  containment check, locator collision refused — including a different
  receipt for the same identity (a past observation is never replaced).
- Proof v2: `evaluate_proof_v2(..., observation_receipt=...)`; a receipt bound
  to the same identity sets `live_observation_wired: true` and
  `observation_id`; it can never make a stage PRESENT. Proof v1 unchanged.
- CLI: `atlas observe-execution --vault --project --repo [--base-ref] [--remote]`
  and `atlas proof --observation <file>`. Root `cli.py` untouched.
- **Authorization (O3 realized under owner directive
  `GOAL = COMPLETE_ULT_01B_1_OPERATIONAL_AUTHORIZATION`):** `execution.observe`
  is registered in `src/project_atlas/authz.py` — a certified frozen surface —
  under the owner-approved sha256-pinned exception
  `OG-ULT-01B-1-AUTHZ-EXECUTION-OBSERVE-20260909` (preimage
  `505ca5bb…`, blob `c6dd713a`; the applied change is exactly
  `docs/evidence/ULT-01B-1-authz-execution-observe.patch`). It is a member of
  `ALL_CAPABILITIES` and `PRIVILEGED_CAPABILITIES` and of nothing else: not
  `DEFAULT_OPERATOR_CAPS`, not `READ_ONLY_CAPABILITIES`. The CLI fails closed
  without `ATLAS_CLI_ELEVATE_CAPS=execution.observe`
  (`authz-cli-elevation-required` / `-incomplete`); with it the real live
  path runs and stores the receipt. A read credential can never carry it;
  the default local operator never has it; no existing capability widened.
- OBSERVED != CLAIMED · UNKNOWN != FAILURE · MODEL_OUTPUT != OBSERVATION ·
  DIRTY_WORKTREE != VALID_CANDIDATE_OBSERVATION · OBSERVATION != AUTHORITY ·
  SECRET != EVIDENCE_PAYLOAD · MERGE_AUTHORIZATION = NOT_GRANTED
