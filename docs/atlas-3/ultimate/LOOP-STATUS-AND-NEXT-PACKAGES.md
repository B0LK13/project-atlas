# Ultimate Atlas — loop status and next packages (planning, 2026-09-09)

**Status: PLANNING / OWNER GATE.** This document is derived from repository
truth after ULT-01b-1 closed (PR #765: observation certified at `e3708077`,
operationally authorized at `f71b9f5d`, both docs-sealed). It maps the seven
elements of the target loop — observation, authority, planning, execution,
evidence, learning, improvement — to what exists, what is certified, and
what is gated; and it proposes the next packages in execution-ready form so
that the owner's authorization is the only remaining step. Nothing here
starts ULT-01b-2, ULT-01b-3 or any other package. `PROPOSED != AUTHORIZED`,
`OPEN_PR != LANDED`, `MERGE_AUTHORIZATION = NOT_GRANTED`.

The goal it serves: *a continuously self-verifying engineering organism in
which observation, authority, planning, execution, evidence, learning and
improvement form a single trustworthy loop that expands capability without
weakening governance, and involves a human only where judgment or authority
is genuinely irreducible.* The two irreducible human points today are package
authorization and merge authority; this document exists to make both
decisions small and evidence-backed.

## 1. Loop element map (repository truth, not aspiration)

| Element | Status | What exists (with the object it is bound to) | What is missing for the loop to close |
|---|---|---|---|
| **Observation** | **OPERATIONAL** | `project_atlas.execution_observation` observes live git (pins on a clean worktree, remote identity read raw and unambiguous, no repository-configured command executes, content-filter checkouts refused, submodule work trees excluded), host (fixed vocabulary, unmapped → UNKNOWN) and toolchain (`importlib.metadata`), seals an `ExecutionIdentity` and a content-bound `atlas.observation-receipt.v1` with no timestamp; certified at `e3708077` (IV/ADV P0=P1=P2=0, CI 4/4); CLI `atlas observe-execution` under `execution.observe` | Agent, context and capability dimensions are `UNKNOWN` by decision (ULT-01b-3, O2/O6); no `verify_identity_current` (`OBSERVED != CURRENT` is enforced by refusing to claim currency, not by re-observation) |
| **Authority** | **OPERATIONAL (model), PARTIAL (breadth)** | Frozen `authz.py` with sha256-pinned owner exceptions (`test_atlas3_demo_isolation_001.py`), `execution.observe` privileged and default-off under grant `OG-ULT-01B-1-AUTHZ-EXECUTION-OBSERVE-20260909`; explicit CLI elevation (`ATLAS_CLI_ELEVATE_CAPS`), SEC-009 read/privileged credentials; `orchestration/autonomy` leases (`AgentLease`, `grant_lease`) | Three unlinked capability models (ULT-00 finding); no capability broker; the lease substrate is not bound to an observed identity (ULT-01b-3 `capabilities` dimension); merge authority is human-only and correctly so |
| **Planning** | **PARTIAL** | AT3-082 `next_honesty` derives a next action from pulse/next lens with authority-claim rejection; AT3-096 `mission` composes declared nodes and leases; ULT-00/ULT-01b planning documents (this directory) are hand-derived from repository truth | Nothing in `src/` selects the highest-value package from observed state; planning is documents plus an owner decision. Closing this leg is a later package (`choose and execute the highest-value work`), and it must consume observation receipts and evidence, not declared JSON alone |
| **Execution** | **PARTIAL** | Package execution happens in governed worktrees by an agent under directives; `orchestration/autonomy` dispatcher observes candidate pins (no base tree, no tests); the unmerged stack #720–#739 (`scripts/atlas_dag/`, outside `src/`) prototypes a verifier pool, principal registry and evidence-invalidation graph — compose-as-prior-art by owner decision | No in-repo executor that takes an authorized package and produces a candidate object; the dispatcher's observation is superseded by `execution_observation` and should reuse it (ULT-01b-2) |
| **Evidence** | **OPERATIONAL** | AT3-103 proof v2: `ExecutionIdentity`, `EvidenceAttestation` (IV/ADV independence declared), `evaluate_proof_v2` binding every attestation to one HEAD/TREE and now to an observation receipt (`live_observation_wired`); evidence receipts with round history, negative-control JSON, exact-head CI; docs-only seals proving `src`/`tests` identity by hash | Attestations are still typed by the verifier from parameters (`iv-bind`/`adv-bind` take `observed_head/tree` as caller input) rather than read from a live observation (ULT-01b-2); no proof DAG / evidence invalidation when the base moves (out of ULT-01b; #735 `DEP_*` classes are prior art); STRUCTURAL JSON schemas only |
| **Learning** | **PARTIAL** | Each receipt carries a failure-pattern register (§8 of the AT3-103 and ULT-01b-1 receipts); negative-control scripts encode every closed finding as a mutation that must kill a test; session memory outside the repository records lessons (e.g. config-bypass vs autocrlf; edit verification) | No in-repository learning substrate that a later package or verifier consumes; failure patterns are prose in receipts, not a register with ids that controls scripts and verifier prompts cite |
| **Improvement** | **PARTIAL** | Verification rounds drive remediation (three rounds for AT3-103, three plus one for ULT-01b-1), each round a new exact object with fresh IV/ADV/CI; controls scripts grow with every closed finding | Improvement is triggered by verifier reports read by a human-directed agent; nothing detects that an existing certification is stale when its inputs change (proof DAG), and nothing proposes the remediation package from the evidence |

**Loop closure today:** observation → evidence → (human) authority → execution → evidence is real and certified for one slice. The links that are still human-typed rather than observed are: verifier attestations to observations (ULT-01b-2), agent/capability identity (ULT-01b-3), staleness (ULT-01b-2 `verify_identity_current`, later proof DAG), and package selection (planning package, later).

## 2. What ULT-01b-1 taught (feeds the learning leg)

Recorded so no later package rediscovers them; each has a control or test that
would fail if the lesson regressed.

1. "Environment constructed from nothing" is not enough when a pass-through variable (`HOME`) selects configuration the instrument reads — and hiding the configuration files (`GIT_CONFIG_NOSYSTEM`) broke honest Windows checkouts (`core.autocrlf`). Isolate identity (raw `--get-all`, one value) and command execution (`core.fsmonitor` pinned via environment-level config; bound content filters refused before `git status`), not files.
2. Porcelain commands rewrite (`remote get-url` applies `insteadOf`); read raw configuration. `git config --get` returns the LAST multivar value while fetch uses the FIRST — require exactly one.
3. `git status` executes clean filters for stat-dirty bound paths; a nested `git status` inside a submodule executes the submodule's configuration. Ask git which paths are bound (`ls-files ':(attr:filter=<driver>)'`) and exclude submodule work trees.
4. Ordering: containment checks before `mkdir`, symlink walks after it; scans of raw values before normalization lowercases them.
5. Frozen surfaces: verify the preimage against `origin/main` and record its sha before mutation; the applied change must equal the committed proposal byte-for-byte; the pin is exact and any later byte needs a new grant.
6. Verification discipline: every correction round is a new exact object with fresh full IV + ADV + exact-head CI; read the Windows job before calling a round certified; controls scripts must be run detached (a tool timeout mid-mutation skips the restore); re-grep every scripted edit before running anything expensive.

## 3. Proposed next packages (execution-ready; none authorized)

Ordered by value to loop closure per unit of risk. Each is sized to one
certified object with the same ladder as ULT-01b-1 (targeted → affected → full
→ committed controls → fresh IV → fresh ADV → exact-head CI → docs-only seal).

### P1 — ULT-01b-1-T: behavioural tests for pin-protected guards (tests only)

Closes the ADV round-4 finding that six authorization guards are killed only
by the sha-pin freeze guard (Z06 unknown-capability check in
`require_cli_elevated_operator`; Z08 `*`; Z09 case; Z10 prefix; Z11
unknown-cap in `elevated_operator`; Z16 read-credential intersection), the
round-3 filter-scan mutants W12 (regexp reduced to `clean`) and W20
(`--local`-only scan), and the ADV round-1/2 test-gap survivors (stdin closed,
stdout cap, NUL env, `--untracked-files=all`, path-digest value, FIFO
locator, bounded `--observation` reader). Content: new tests only, controls
script extended so each named mutant is killed by a behavioural test; no
`src/` change; `authz.py` untouched (pin holds). Owner gate: package id and
authorization. Risk: none to behaviour; value: the pin stops being the only
guard, which matters because the next authz grant will re-pin.

### P2 — ULT-01b-2: verifier attestations bound to live observation (O7 already decided: slice 2, additive flags only)

Design from repository truth:
- `verify_identity_current(vault, project_id, identity_digest, *, repo_root, ...)` in `execution_observation/`: re-observe with the same observer and compare `identity_digest` → `CURRENT` (equal), `STALE` (differs; both digests reported, nothing overwritten — the stored receipt is a past observation), `UNKNOWN` (observation refused, coded reason). No clock; freshness is a comparison of two observations, which is the only honest meaning of "current". Result is a derived record, not authority.
- `atlas iv-bind --observe` / `atlas adv-bind --observe` (additive flags, `atlas3/cli.py` only): `observed_head`/`observed_tree` are read from a fresh live observation (or `--observation <receipt>` verified by digest) instead of being typed by the caller; `bind_independent_verification` / `bind_adversarial_result` gain optional `observation_id` and `identity_digest` fields in the output and refuse (`TARGET_MOVED`) on any mismatch as today. `IMPLEMENTER != VERIFIER` unchanged.
- `EvidenceAttestation` (AT3-103) gains an optional `observation_id` bound to the same `identity_digest`; `evaluate_proof_v2` reports whether every attestation's observation equals the proof's observation (`attestation_observations_consistent`), never raising a stage to PRESENT.
- AT3-003 event emission for `execution.observed` / `verification.bound` with caller-supplied `observed_at` validated (the receipt itself stays timestamp-free).
- Capability: reuse `execution.observe` for the `--observe` flags (they launch git); no new literal, no authz change.
- Acceptance/adversarial matrix: mirrors ULT-01b-1 §10 plus: STALE cannot be sealed as CURRENT; a bind with a receipt for another identity refused; a typed `--observed-head` and `--observe` together → conflict; determinism of `verify_identity_current` across processes.
Owner gates: package authorization; policy decision whether `STALE` invalidates existing attestations (recommendation: report, do not invalidate — invalidation is the proof-DAG package).

### P3 — ULT-01b-3: agent, capabilities and context dimensions (needs O2 and O6/ULT-03a)

Agent: hash-verified skill from the single canonical manifest the owner names (O2). Capabilities: `lease_id` from an `ACTIVE` `orchestration/autonomy` lease projection, bound to the observed identity. Context: `content_digest` on context packs (ULT-03a owns the digest; this slice consumes it). Each dimension moves from `UNKNOWN` to `OBSERVED` only with a method ref and a verifiable source; anything else stays `UNKNOWN` with a reason. Owner gates: O2, O6 sequencing with ULT-03a, package authorization.

### P4 — Learning substrate (new; recommendation only)

An in-repository failure-pattern register (`docs/atlas-3/ultimate/FAILURE-PATTERNS.md` plus a small JSON index with stable ids) populated from the receipts' §8 lines, cited by controls scripts (`# FP-007`) and by verifier prompts. Docs-only; no runtime. Value: the learning leg gets a substrate that later planning can read. Owner gate: whether this lives in docs (recommended now) or becomes an `atlas3` lens later.

### Out of scope until authorized separately

Proof DAG / evidence invalidation when the base moves (#735 prior art); package-selection planning from observed state; environment enforcement (containers, egress, limits); model identity; principal registry / independence verification; capability broker unifying the three capability models.

## 4. Irreducible owner decisions

| # | Decision | Recommendation |
|---|---|---|
| L1 | Authorize P1 (tests-only) as a package with an id | Yes; smallest risk, removes the single-guard dependency on the sha pin |
| L2 | Authorize P2 (ULT-01b-2) under O7 as decided (additive flags only); confirm `execution.observe` covers `--observe` | Yes; reuse the capability, no authz change |
| L3 | STALE policy: does a `STALE` verification invalidate existing attestations, or only report? | Report only; invalidation belongs to the proof-DAG package |
| L4 | O2 (canonical skill manifest) and O6 sequencing (ULT-03a context digest before ULT-01b-3) | Decide before P3; P3 waits |
| L5 | Learning substrate location (docs register now vs `atlas3` lens later) | Docs register now |
| L6 | Merge of PR #765 (observation certified, authorization certified, both docs-sealed; base #743 unmerged) and of #743/#742/#764 as a stack | Owner-only; nothing in this document grants it |

## 5. Return line

```text
LOOP_STATUS                = DERIVED_FROM_REPOSITORY_TRUTH (2 elements operational, 5 partial; links still human-typed named)
ULT_01B_1                  = IMPLEMENTED_AND_OPERATIONALLY_AUTHORIZED (e3708077 / f71b9f5d; MERGE_AUTHORIZATION = NOT_GRANTED)
NEXT_PACKAGES              = PROPOSED (P1 tests-only, P2 ULT-01b-2, P3 ULT-01b-3, P4 learning substrate) — NOT AUTHORIZED, NOT STARTED
OWNER_DECISIONS_REQUIRED   = L1–L6
```
