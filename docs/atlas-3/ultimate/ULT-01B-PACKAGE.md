# ULT-01b — Live observation for the execution identity (work package)

| Field | Value |
|---|---|
| Status | **PROPOSED — READY FOR OWNER GATE. Implementation NOT started; no runtime authority granted.** |
| Predecessor | AT3-103 / ULT-01a: `ExecutionIdentity` v1, `EvidenceAttestation` v1, proof v2 (PR #743, integration-ready at `0ff843aa`) |
| Reconciled against | `origin/main` `e4dd17bc5956a7ebb2c044dbfd91749c796d38f1` plus the AT3-103 candidate tree (`0ff843aa` / `cc00a5c0`) |
| Precedence | Owner directives > re-derived `main` truth > AGENTS/CLAUDE/GOVERNANCE/SECURITY > Atlas 3 canon > this package |
| `MERGE_AUTHORIZATION` | NOT_GRANTED |
| `ULT_01B_IMPLEMENTATION_AUTHORITY` | NOT_GRANTED |

Every file:line reference below was read at the reconciled objects. Where
this package contradicts the ULT-00 sketch in `FIRST-PACKAGE-ULT-01A.md`
("observation wiring reusing `observe_binding_pins`; IV/ADV consume the
identity; proof DAG"), §2 says why and the repository evidence wins.

## 1. What ULT-01b is

ULT-01b moves Atlas from `EXECUTION IDENTITY CONTRACT EXISTS` to
`EXECUTION IDENTITY CAN BE POPULATED FROM TRUSTWORTHY LIVE OBSERVATION`.

Concretely: a small, isolated **execution observer** that reads the live
git object, host environment and installed toolchain through bounded,
validated, shell-free calls; seals an `ExecutionIdentity` from those
values through the existing `seal_execution_identity`; writes a
content-addressed **ObservationReceipt** that records *how* each dimension
was observed (or why it stayed `UNKNOWN`); and lets proof v2 report
`live_observation_wired: true` only when the identity it was handed is
bound to such a receipt.

It does not observe anything it cannot verify, does not read its own
clock, does not write outside `generated/ops/atlas3/`, and does not grant
or imply any authority.

```text
OBSERVED != CLAIMED
UNKNOWN != FAILURE
MODEL_OUTPUT != OBSERVATION
DECLARED_CAPABILITY != OBSERVED_CAPABILITY
STALE_OBSERVATION != CURRENT_OBSERVATION
ATTESTATION != AUTHORITY
SECRET != EVIDENCE_PAYLOAD
OBSERVATION != AUTHORITY
```

## 2. Corrections to prior planning (repository evidence wins)

| ULT-00 sketch said | Repository truth | Consequence |
|---|---|---|
| Reuse `dispatcher.observe_binding_pins` as the observation adapter | `observe_binding_pins` (`orchestration/dispatcher.py:690-695`) observes `base_main`, `HEAD`, `HEAD^{tree}` only — **it never derives `origin/main^{tree}`**, which `GitSource.base_tree` requires; `resolve_binding_pins` lets config silently override observation (`:712-714`); `_git_rev_parse` accepts 64-hex too (`:685`); and **no test anywhere executes it** (grep: zero references outside `src/`). | Do not build on the dispatcher. The only code that observes a base tree is `orchestration/autonomy/trust.py:1565-1571` (`LiveGitObserver.observe_main`), with `tree_of` (`:1585`), `repository_identity` (`:1608`), `require_full_pin` (`:118-122`) and `normalize_repository_identity` (`:124-141`), behind an injectable `GitRunner` protocol (`:1533`). Reuse those semantics; add the timeouts they lack. |
| Observation adapter could live near `atlas3/proof.py` | `src/project_atlas/atlas3/` has **zero** `subprocess` imports and **zero** clock reads across 47 modules; `atlas3/contracts.py:3` states "No wall-clock in generated content"; the isolated-runtime convention is enforced by source-scan tests (`test_atlas3_iv_bind_051.py:136-145`, `test_atlas3_adv_020_control_001.py`). | The observer lives in a **new package** `src/project_atlas/execution_observation/` depending only on `atlas_contracts` + stdlib. `atlas3/proof.py` stays a pure consumer. CLI registration goes through `atlas3/cli.py`, which already imports from `orchestration.origination.cli` (precedent for a non-atlas3 import at the seam). |
| ULT-01b also builds the proof DAG and makes IV/ADV consume the identity | A DAG is a proof-structure concern, unrelated to observation; bundling it would double the surface of a package whose whole point is a narrow trust boundary. IV/ADV consumption is a one-flag change on top of the observer and is a separable slice. | Proof DAG is **out** (later package). IV/ADV `--observe` is slice ULT-01b-2, after the observer exists. |
| `base_tree` observation is "wiring" | `GitSource` requires `base_head` **and** `base_tree` together (`execution_identity.py:72-89`), and proof v2 requires the candidate pair (`proof.py:268-272`, `CANDIDATE_OBJECT_REQUIRED`). | Without base tree and a clean candidate, no identity can be sealed at all: the git dimension is the load-bearing first slice, not a refinement. |

## 3. Reuse map (extend, do not duplicate)

| Need | Reuse | Where | Note |
|---|---|---|---|
| Repository identity | `normalize_repository_identity` | `orchestration/autonomy/trust.py:124-141` | Output shape `github.com/b0lk13/project-atlas` already satisfies `REPOSITORY_PATTERN`. The second normalizer `sdk/mutation_attribution.py:92-138` produces `https://…` and must **not** be used. |
| Pin validation | `require_full_pin` | `trust.py:118-122` | Strict 40-hex lowercase, coded `PIN_INVALID`. Not the dispatcher's 40-or-64 leniency. |
| Injectable git seam | `GitRunner` protocol + `FixtureGitObserver` | `trust.py:1533-1535`, `:1612` | The reason `trust.py` is testable and the dispatcher is not. Define the observer around a runner from day one. |
| Bounded subprocess template | `read_clipboard_text(runner=…, which=…)` | `capture_sources.py:123-157` | Explicit `shell=False`, explicit timeout, coded errors, two injection seams. Copy the shape. |
| Clean-worktree precondition | `_require_clean_worktree` | `orchestration/local_process_transport.py:290-314` | `git status --porcelain` non-empty → refuse. Reuse the semantics (import or lift), not a copy. |
| Sealing and digest | `seal_execution_identity`, `content_digest`, `short_id` | `atlas_contracts/execution_identity.py:277-286`, `canonical.py` | The only mint path; refuses caller-supplied digests. |
| Receipt shape | `EvidenceAttestation` / `ProvenanceRecord` field discipline | `atlas_contracts/attestation.py`, `provenance.py` | producer{kind,name,version}, command refs not commands, `content_hash` + derived id, no timestamp. |
| Safe storage | locator/symlink-walk/collision logic | `atlas3/proof.py:142-151, 380-401` | Lift `_assert_no_symlink_components` and the locator rules into a shared helper (`atlas3/contracts.py`), keep proof v2 byte-for-byte in behaviour, and add `Path.is_junction()` (3.12) to close the recorded Windows residual. |
| Atomic write | `write_json_atomic` | `atlas3/contracts.py:87-100` | `sort_keys`, `newline="\n"`, tmp + `os.replace`. Add the Windows ordering rule (mkdir before the resolved containment check) and bounded `PermissionError` retry recorded in `WORKLOG.md:11184-11228`. |
| Python version | `doctor._check_python` | `doctor.py:78-83` | In-process `sys.version_info`; needs a structured value, not the prose `detail`. |
| Installed distributions | `doctor._check_dependencies` | `doctor.py:90-99` | `importlib.metadata.version`, `PackageNotFoundError` explicit. The **only** honest toolchain source: there is no lock file and no `--version` probe anywhere in `src/`. |
| OS branching | `_is_windows(os_name)` | `agent_transport.py:151-152` | Injectable for tests. |
| Honesty vocabulary | `OBSERVED`/`UNKNOWN`, `EXTERNAL_BLOCKED`, `honesty_block()`, `TRUTH_BOUNDARY` | `execution_identity.py:47`, `atlas3/contracts.py` | No new words. |
| Ordering without clocks | integer `sequence` + content id | `ops_events.py:122,170,332-345` | If ordering is ever needed. v1 needs none. |

Not reused, deliberately: `orchestration/sdk/external_observers.py` ("observer" there means a CI/cloud poller — namespace collision to avoid); `atlas3.capabilities.REGISTRY` (process-global mutable taxonomy, not a grant store); `sanitize_inherited_env` (it is a two-key denylist, not an allowlist — the observer builds its child environment from nothing).

## 4. Observation trust model — what may become OBSERVED, and how

| Dimension | Source of truth | Method | Trust class | Slice |
|---|---|---|---|---|
| `source.repository` | `git remote get-url <ref-remote>` → `normalize_repository_identity` | subprocess, argv, timeout 10 s | OBSERVED | 1 |
| `source.base_head` / `base_tree` | `git rev-parse <base-ref>` / `<base-ref>^{tree}` | subprocess | OBSERVED | 1 |
| `source.candidate_head` / `candidate_tree` | `git rev-parse HEAD` / `HEAD^{tree}` **only after** `git status --porcelain` is empty | subprocess | OBSERVED | 1 |
| `environment.os` / `arch` / `python` | `platform.system()`, `platform.machine()` (normalized), `sys.version_info` | in-process syscalls | OBSERVED | 1 |
| `toolchain.tools[]` | `importlib.metadata.version()` for a declared set of distributions present in the environment, plus `git --version` parsed by strict regex | metadata read + one subprocess | OBSERVED (present distributions only) | 1 |
| `agent.agent_id` / `skill_sha256` | no verified `agent_id` exists outside a live SDK session (`agent_identity.py:12-16` is a self-declared string); `skill_sha256` is hash-verified by `skill_loader.py:36-39` but lives outside `src/` and outside lint/type scope; two incompatible skill manifests exist | — | **UNKNOWN** in slice 1 | 3 (owner decision O2) |
| `context.context_digest` | no context pack carries a content digest today (`compat_snapshot_id` is the literal `"atlas-1.0.0-compat"`, `compat_anchor.py:17`; `atlas3/start.py` has none) | — | **UNKNOWN** in slice 1 | 3 (needs a `content_digest` field on the pack; owner decision O6) |
| `capabilities.grant_ref` | `AgentLease.lease_id` (`orchestration/autonomy/models.py:396-434`) via the durable projection with `status == ACTIVE` (`lease_projection.py:63-76`: `ABANDONED` is a failure, not a grant) | file read of the projection | OBSERVED only inside a leased execution | 3 |
| `model` | not in the v1 contract; the only provider-observed model id in the repo is `openai_responses_poc.py:269` (experimental, `or model` fallback) | — | not a dimension | out |

Rules that make a value OBSERVED rather than claimed:

1. The value comes from a syscall, a subprocess whose stdout matched a strict
   regex, or `importlib.metadata`; never from configuration, an environment
   variable, a module `__version__` attribute, model output or a prior receipt.
2. Every subprocess is an argv list (`shell=False`), with an absolute
   executable resolved through `shutil.which` (wrappers `.cmd`/`.bat`
   refused on Windows; `.exe` only), `cwd=<resolved repo root>`, a child
   environment built from nothing (`PATH`, `SystemRoot`, `HOME`/`USERPROFILE`,
   `TEMP`/`TMP` only; every `GIT_*` variable dropped so `GIT_DIR`/`GIT_WORK_TREE`
   cannot redirect the observation), `timeout` ≤ 10 s, `check=False`, and
   stdout validated before use. No hooks run for the commands used.
3. Configuration may choose *what* to observe (the base ref name, the declared
   toolchain set) and is recorded in the receipt as configuration; it may
   never supply a *value*.
4. A dimension whose method fails, times out, or returns something the
   regex rejects becomes `UNKNOWN` with a reason code. `UNKNOWN` is a valid,
   honest result, not an error — except for the git dimension, where an
   identity cannot be sealed without base and candidate (see §5).

## 5. UNKNOWN policy and failure semantics

| Condition | Result | Code |
|---|---|---|
| Repo root missing `.git`, not a directory, or a symlink | no observation, nothing written | `GIT_UNOBSERVABLE` |
| `git` executable not found / not `.exe` on Windows | no observation | `GIT_EXECUTABLE_UNAVAILABLE` |
| subprocess timeout or non-zero exit for a required pin | no observation | `GIT_PIN_UNOBSERVABLE` (per pin, reported) |
| pin output fails the 40-hex regex | no observation | `PIN_INVALID` (reuse) |
| base ref absent (e.g. no `origin/main`) | no observation unless the caller named another base ref | `BASE_REF_UNOBSERVABLE` |
| shallow repository (`rev-parse --is-shallow-repository` = true) | observation proceeds; receipt records `shallow: true`; base ref must still resolve | — |
| `git status --porcelain` non-empty | **refused**: a candidate pair for a dirty tree would describe an object that did not run | `WORKTREE_NOT_CLEAN` |
| remote URL carries userinfo (`user:token@`), fails normalization, or scans as secret-shaped | `source.repository` unobservable → no identity; the raw URL is never logged, echoed or written | `REPO_IDENTITY_UNVERIFIABLE` |
| `platform.machine()` returns a value outside the normalization table | environment `UNKNOWN` (all three fields dropped: the block is all-or-nothing, `execution_identity.py:106-118`) | `ENVIRONMENT_UNOBSERVABLE` |
| a declared distribution is absent | omitted from `tools` (not an error); zero present → toolchain `UNKNOWN` | `TOOLCHAIN_UNOBSERVABLE` |
| `git --version` unparsable | git omitted from tools | — |
| receipt locator exists with a different digest / any path component is a symlink or junction | receipt not written | `PROOF_LOCATOR_COLLISION` / `PROOF_LOCATOR_UNSAFE` (reuse) |

Failure never leaves a partial receipt or a temp file. `UNKNOWN` blocks carry
no values (`UNKNOWN_WITH_VALUES` is enforced by the contract); the receipt
carries the reason code beside each `UNKNOWN`.

## 6. Provenance, freshness and object binding

**Provenance.** The `ObservationReceipt` (`atlas.observation-receipt.v1`,
`atlas_contracts`, `extra="forbid"`, frozen) carries, following the
attestation discipline:

```yaml
schema: atlas.observation-receipt.v1
schema_version: 1
project_id: <safe component>
identity: <the sealed atlas.execution-identity.v1 record, verbatim>
identity_digest: <== identity.identity_digest; verified on load>
observer:
  kind: tool                       # never model/agent
  name: atlas-execution-observer
  version: <project-atlas distribution version via importlib.metadata, or UNKNOWN>
observed:
  source:      {status: OBSERVED|UNKNOWN, base_ref: "origin/main", worktree_clean: true, shallow: false, method_refs: [...], reason: null|CODE}
  environment: {status, method: "platform+sys", arch_raw: "AMD64", reason}
  toolchain:   {status, method: "importlib.metadata+git --version", declared_set: [...], reason}
  agent:       {status: UNKNOWN, reason: NOT_OBSERVABLE_IN_THIS_SLICE}
  context:     {status: UNKNOWN, reason: NO_CONTEXT_DIGEST_SOURCE}
  capabilities:{status: UNKNOWN, reason: NO_ACTIVE_LEASE}
observed_is_current: false          # a receipt is a record of a past observation
authority: derived
merge_authorization: NOT_GRANTED
honesty: <honesty_block()>
content_hash: <canonical digest of everything above>
observation_id: obs-<content_hash[:16]>
```

`method_refs` are command *references* (`git rev-parse HEAD`, ≤512 chars),
never executed strings, and never include the remote URL. No environment
variable, path outside the repo root, or raw stdout is persisted.

**Time.** The observer never reads its own clock (`datetime.now`,
`time.time`, `utcnow` are forbidden in the package; a source-scan test pins
it, like `test_atlas3_iv_bind_051.py:136-145` does for writes). The receipt
has **no timestamp field**; "when" is answered by *which exact object* was
observed. If a caller has a genuine observation instant, it belongs on the
AT3-003 event envelope's `observed_at` (`atlas3/events.py:128`), validated
through `bitemporal._parse_instant` at the call site (the envelope itself
does not validate), and never in `valid_from`/`valid_to`
(`ARCHITECTURE.md:133-137`). Precedents: ADR-001 §2; `evidence.py:34`
"No wall-clock fields are emitted"; `ExecutionIdentity` and
`EvidenceAttestation` carry zero time fields.

**Freshness.** `OBSERVED != CURRENT`. A receipt on disk is history. The
repository's rule is live recompute at read time with the stored value
demoted (`agent_handoff.py:845-862`, "Forged freshness on disk is never
authority: live recompute above wins"; `runtime_22.py:300-324` refuses
stale→fresh laundering). ULT-01b applies it as `verify_identity_current`
(slice 2): re-observe, compare digests, return `CURRENT | STALE | UNKNOWN`,
never upgrade.

**Object binding.** `identity_digest` covers `candidate_head`/`candidate_tree`
(and the base pair), so a receipt is bound to one exact object by
construction. IV/ADV binding (`iv_bind.py:49-53`, `adv_bind.py`) keeps its
`TARGET_MOVED` semantics; slice 2 lets the observer supply
`observed_head/observed_tree` instead of the caller.

**Proof v2 linkage.** `evaluate_proof_v2` gains an optional
`observation_receipt` argument. When present, it is loaded strictly, its
`identity_digest` must equal the identity's, its `content_hash` must verify,
and its embedded identity must equal the supplied one byte-for-byte; then
the report carries `live_observation_wired: true` and
`observation_id`. Otherwise the report keeps `live_observation_wired:
false`. The constant at `proof.py:376` becomes computed, and the assertion
at `test_atlas3_proof_v2_103.py:355` becomes conditional. Per-dimension
`bindings()` stay honest: `OBSERVED` blocks bind, `UNKNOWN` blocks do not.

## 7. Security boundaries

- Secrets: the raw remote URL is scanned for userinfo and secret patterns
  *before* normalization and is never persisted, logged or placed in an
  error; `scan_text` findings name the pattern class only
  (`secrets.py:1-4`). The sealed identity and the receipt are scanned over
  raw string values, as proof v2 already does (`proof.py:192-215`).
- Environment: no `os.environ` value is ever persisted. The child
  environment is constructed, not inherited (`GIT_*` dropped; `ComSpec`
  never consulted — the observer does not launch through `cmd.exe`).
- Process: argv only, `shell=False`, absolute executable, bounded timeout,
  stdout parsed by regex; stdout prose is never interpreted (ADR-004;
  `orchestration/models.py:194-197`).
- Paths: repo root is `Path.resolve()`d and must contain `.git`; receipt
  paths are joined from `safe_relative_component`-validated parts only;
  every component under the vault is `lstat`-checked on the unresolved
  path before any `resolve()`, junctions included; containment re-checked
  after `mkdir` (Windows ordering rule); locator collision refuses overwrite.
- Authority: the receipt is `authority: derived`; it cannot carry
  `merge_authorization`, `certified_for_merge`, `execution_authorized`,
  `owner_authority` or `trust_score` (contract `extra="forbid"` plus the
  existing authority-field denylist); an observation never satisfies
  `INDEPENDENT_VERIFICATION` or `ADV` by itself.
- Capability gating: `authz.py:32-46` has no `observe` literal, and
  `READ_ONLY_CAPABILITIES` carries "SEC-009: read MUST NOT mutate", so a
  receipt-writing observer cannot hide behind a read literal. Owner
  decision O3: add `execution.observe` (default **out** of
  `DEFAULT_OPERATOR_CAPS`) or gate on `vault.write`.
- Isolation: nothing under `DENY` in `test_atlas3_demo_isolation_001.py`
  is touched; root `src/project_atlas/cli.py` is untouched
  (registration via `atlas3/cli.py`).

## 8. Platform concerns

- Architecture normalization is a contract, not an accident: `AMD64` ↔
  `x86_64`, `arm64` ↔ `aarch64`, `i386`/`i686` → `x86`. Unmapped values →
  environment `UNKNOWN`. Otherwise materially identical hosts would seal
  different identities (owner decision O4 fixes the table).
- OS token: `platform.system()` → `Linux` / `Windows` / `Darwin`; anything
  else → `UNKNOWN`.
- Windows executable resolution: `shutil.which("git")` must resolve to
  `git.exe`; `.cmd`/`.bat` wrappers refused (`agent_transport.py:179-196`
  precedent). `CREATE_NO_WINDOW` from `sdk/host.py:25-50` for child
  processes.
- Line endings: git stdout is stripped; the receipt is written with
  `newline="\n"`; no `Path.read_text` on identity-bearing bytes
  (`WORKLOG.md:13238-13240`).
- Junctions: `Path.is_junction()` (Python 3.12) added to the component
  walk; TOCTOU between walk and write remains a recorded residual unless
  the POSIX dirfd write from `vault_identity.py:139-189` is generalized
  (out of scope for slice 1; noted in §11).
- CI: ruff/mypy run Linux-only (`ci.yml:44-51`); Windows runs the suite.
  Every Windows branch needs an `os.name == "nt"`-gated test, and the
  observer's own tests must run against a temporary `git init` repository on
  all three runners (git is present on every CI image).

## 9. Package decomposition

| Slice | Content | Depends on | Owner gate |
|---|---|---|---|
| **ULT-01b-1 (first executable package)** | `src/project_atlas/execution_observation/` (`runner.py` with the `GitRunner`-style protocol + bounded subprocess runner; `git.py`; `host.py` for environment/toolchain; `receipt.py` contract in `atlas_contracts/observation_receipt.py`; `observe.py` orchestrating dimensions and sealing); shared path helper lifted from `proof.py` (+ junction check); storage under `generated/ops/atlas3/observation/v1/<project>/<digest16>.json`; `atlas observe-execution --vault --project --repo [--base-ref origin/main] [--json]` via `atlas3/cli.py`; proof v2 `observation_receipt` linkage; JSON schema; tests + negative controls + evidence receipt | AT3-103 merged (or stacked on #743) | O1, O3, O4, O5 |
| ULT-01b-2 | `verify_identity_current` (re-observe and compare; `CURRENT/STALE/UNKNOWN`); `atlas iv-bind --observe` / `atlas adv-bind --observe` supplying `observed_head/tree` from the observer; AT3-003 event emission with caller-supplied `observed_at` validated | 01b-1 | O7 |
| ULT-01b-3 | agent dimension (hash-verified skill from a single canonical manifest), capabilities dimension (`lease_id` from an `ACTIVE` projection row), context dimension (`content_digest` on context packs) | 01b-1, owner decisions O2, O6 | O2, O6 |
| out of ULT-01b | proof DAG; environment enforcement (containers, egress, limits); model identity; principal registry / independence verification; capability broker; any change to `evaluate_proof` v1 | — | — |

## 10. Acceptance and adversarial validation for ULT-01b-1

Functional:
- On a clean temporary repository with an `origin/main` ref, `observe_execution` seals an identity whose `source`, `environment` and `toolchain` blocks are `OBSERVED` and whose `agent`/`context`/`capabilities` are `UNKNOWN`; the receipt loads strictly and its embedded identity equals the sealed one.
- The same repository observed twice in two processes yields identical `identity_digest`, `observation_id` and receipt bytes.
- `evaluate_proof_v2(..., observation_receipt=receipt)` reports `live_observation_wired: true`; without the receipt, or with a receipt for another identity, `false` / `OBSERVATION_IDENTITY_MISMATCH`.
- Proof v1 stays byte-identical (the 3 + 8 golden digests still pass).

Negative (each with a control that fails a named test when the guard is removed):
- dirty worktree → `WORKTREE_NOT_CLEAN`, nothing written;
- missing base ref → `BASE_REF_UNOBSERVABLE`; shallow repo recorded honestly;
- runner returns abbreviated / uppercase / 64-hex / prose → `PIN_INVALID`;
- runner timeout / non-zero exit / `git` missing → coded refusal, nothing written;
- remote URL with `user:token@`, `ssh://`, `git@` forms → normalized or refused; the raw URL absent from every error, log and file (byte scan of the vault and of captured stderr);
- `GIT_DIR`/`GIT_WORK_TREE`/`GIT_CONFIG_*` set in the parent environment → observation unaffected (child env constructed);
- `platform.machine()` = `AMD64` and `x86_64` on two fake hosts → same `arch` token; an unmapped value → environment `UNKNOWN`;
- a declared distribution absent → omitted; all absent → toolchain `UNKNOWN`; a module `__version__` attribute is never consulted (control: monkeypatch `importlib.metadata.version` to raise and assert `UNKNOWN`, not a fallback);
- symlink or junction at any receipt path component → `PROOF_LOCATOR_UNSAFE`, nothing written; locator with another digest → `PROOF_LOCATOR_COLLISION`;
- receipt with tampered `content_hash`, tampered embedded identity, or an authority-shaped extra key → refused on load; proof v2 refuses it and keeps `live_observation_wired: false`;
- source-scan test: the package imports no `datetime`/`time.time`, and `atlas3/` still imports no `subprocess`;
- the observer's own `version` is marked as `importlib.metadata`-observed or `UNKNOWN`, never a literal.

Adversarial (ADV lane, on the exact object): S1 canonicalization of receipts; S2 instance/draft bypass through the new `observation_receipt` argument; S3 receipt/identity mismatch and mixed-object receipts; S4 authority smuggling via receipt fields and reason codes; S5 path safety of the new storage namespace (every component, chains, junctions, FIFOs, collisions); S6 runner adversary (a fake `git` on `PATH` printing crafted output, hanging, printing secrets — nothing must reach a file); S7 secret handling of remote URLs; S8 v1 regression; S9 Windows (`.cmd` on `PATH` refused, `AMD64` normalization, CRLF stdout); S10 determinism across processes and hash seeds; S11 mutation harness over every new guard, with the committed controls script extended.

Verification ladder: targeted → affected (proof v2, IV/ADV bind, atlas3 CLI, demo isolation, contracts) → full suite on three runners → committed negative controls → fresh IV → fresh ADV → exact-head CI, each bound to one HEAD/TREE; evidence receipt with the same discipline as AT3-103.

## 11. Residual risks (recorded; none blocks starting slice 1)

- TOCTOU between the component walk and the write (inherited from AT3-103); a dirfd-anchored write on POSIX is a later hardening.
- A compromised `PATH` can still put a hostile `git.exe`/`git` first; the observer validates output shape, not the binary. Recording the resolved absolute path and `git --version` in the receipt makes this auditable, not impossible.
- `importlib.metadata` reports what is installed in *this* interpreter; a different interpreter on `PATH` is a different toolchain. The receipt records `sys.executable`'s resolved path digest only if the owner accepts a path in the receipt (O5).
- Windows junction detection relies on `Path.is_junction()` semantics; still untested on real junction fixtures in CI.
- `origin/main` is a convention: a repository with another integration branch needs `--base-ref`, and the receipt makes that visible rather than assuming.

## 12. Irreducible owner decisions

| # | Decision | Recommendation |
|---|---|---|
| O1 | Package location/name: `src/project_atlas/execution_observation/` (new, stdlib + `atlas_contracts` only) vs inside `orchestration/` | New package; keeps proof v2's import graph minimal and avoids the `external_observers` vocabulary |
| O2 | Which skill manifest is canonical for `agent.skill_sha256` (`skill/skill-manifest.yaml` vs `skills/atlas-governed-work/skill.yaml`), and whether `skill_loader` semantics may be re-implemented inside `src/` for the agent dimension | Decide before ULT-01b-3; slice 1 keeps `agent` `UNKNOWN` |
| O3 | Capability literal for the observer: new `execution.observe` (excluded from `DEFAULT_OPERATOR_CAPS`) vs reuse `vault.write` | New literal, default off |
| O4 | Architecture normalization table (`AMD64`→`x86_64`, `arm64`→`aarch64`, …) | Adopt the table in §8; unmapped → `UNKNOWN` |
| O5 | Declared toolchain set and whether resolved executable paths appear in receipts | Distributions: `project-atlas`, `pydantic`, `PyYAML`, `jsonschema`, `pytest`, `ruff`, `mypy`; plus `git`; no paths in receipts (digest of the git executable path only) |
| O6 | Adding a `content_digest` to context packs (`context_pack.py`, not frozen) as a prerequisite for the context dimension — in ULT-01b-3 or in ULT-03a | ULT-03a owns it; ULT-01b-3 consumes it |
| O7 | Whether `atlas iv-bind --observe` / `adv-bind --observe` (slice 2) may change the IV/ADV CLI now, or waits for the verifier-mesh package | Slice 2, additive flags only |
| O8 | Base ref policy: `origin/main` only (trust.py precedent, `BRANCH_NAME_CONFUSION`) vs `--base-ref` override recorded in the receipt | Override allowed, value observed, choice recorded |

## 13. Return line for this planning package

```text
ULT_01B_SCOPE                    = RECONCILED_FROM_REPOSITORY_TRUTH
ULT_01B_ARCHITECTURE_DIRECTION   = EVIDENCE_BACKED (trust.LiveGitObserver semantics + GitRunner seam; new isolated package; receipt bound by identity_digest; no clock)
ULT_01B_FIRST_WORK_PACKAGE       = READY (slice ULT-01b-1, §9–§10)
ULT_01B_OWNER_DECISIONS          = EXPLICIT (O1–O8)
ULT_01B_IMPLEMENTATION           = NOT_STARTED
ULT_01B_READY                    = OWNER_GATE
MERGE_AUTHORIZATION              = NOT_GRANTED
```
