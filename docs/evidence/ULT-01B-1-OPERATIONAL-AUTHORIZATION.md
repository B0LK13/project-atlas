# ULT-01b-1 — Operational authorization of `execution.observe`: evidence receipt

| Field | Value |
|---|---|
| Package | ULT-01b-1 (operational-authorization closure; observation certified separately in `ULT-01B-1-LIVE-EXECUTION-OBSERVATION.md`) |
| PR | #765 |
| Directive | `GOAL = COMPLETE_ULT_01B_1_OPERATIONAL_AUTHORIZATION` (O3 architectural decision approved; frozen-surface authority limited to registering the capability) |
| Owner grant | `OG-ULT-01B-1-AUTHZ-EXECUTION-OBSERVE-20260909`, recorded in `WORKLOG.md` and pinned in `tests/unit/test_atlas3_demo_isolation_001.py` |
| Frozen preimage (verified before mutation) | `src/project_atlas/authz.py` blob `c6dd713adc0f447ee465a35caaced4689ab6c295`, identical on the branch and `origin/main` (`b87b4a22`); sha256 `505ca5bbb9879e49f27f9ea0f43dd9b450bc3576343f789273d547f0b2d0f5ac` |
| Applied change | exactly `docs/evidence/ULT-01B-1-authz-execution-observe.patch` (index `c6dd713a..4fd84eb4`; 5 insertions, 0 deletions) |
| Post-mutation pin | sha256 `3f6500e597028265ee3aa4ec589d327b2258fbb035bc16cf961bb1ef3d4847e4` |
| Certified object | **HEAD `f71b9f5db72e9c7a0664f42f3c8b323525d4e70e` / TREE `48d5c9b813d7552114bb61c7e61bcf1c4b0dfcc4`** (`src` `122e67e7…`, `tests` `83b93892…`) |
| This receipt's commit | docs-only; `src`/`tests` hash-identical to the certified object |
| `MERGE_AUTHORIZATION` | **NOT_GRANTED** |
| `ULT_01B_SLICE_2` / `ULT_01B_SLICE_3` | **NOT_STARTED** |

## 1. Reconciliation against fresh repository truth

Before any mutation: `git fetch`; `authz.py` blob equal on `HEAD` (`0d9b4ed2`,
the round-3 docs seal) and `origin/main`; sha256 recorded above; `git apply
--check` of the committed proposal succeeded against that exact preimage. The
patch was re-read and judged semantically minimal for the stated boundary:
it touches only the `Capability` literal, `ALL_CAPABILITIES` and
`PRIVILEGED_CAPABILITIES`; it does not touch `DEFAULT_OPERATOR_CAPS`,
`READ_ONLY_CAPABILITIES`, `elevated_operator`, `require_cli_elevated_operator`,
`mint_api_session`, token files or bearer handling. Nothing in the intent
required deviating from it, so it was applied unchanged.

## 2. Authorization semantics (pinned by tests)

```text
execution.observe ∈ ALL_CAPABILITIES
execution.observe ∈ PRIVILEGED_CAPABILITIES
execution.observe ∉ DEFAULT_OPERATOR_CAPS
execution.observe ∉ READ_ONLY_CAPABILITIES
DEFAULT_OPERATOR_CAPS, READ_ONLY_CAPABILITIES  == frozen sets (verbatim copy)
PRIVILEGED_CAPABILITIES == frozen set ∪ {execution.observe}
ALL_CAPABILITIES        == frozen set ∪ {execution.observe}
```

`tests/unit/test_authz_execution_observe_01b.py`: default and read-only
operators cannot observe; CLI elevation is explicit and never self-granted
(`authz-cli-elevation-required`, `-incomplete`); an elevated profile is the
defaults plus exactly the required capability; read credentials from
`mint_api_session` never carry it, and a launch operator holding it receives
the existing distinct privileged credential (SEC-009 model, unchanged).

## 3. CLI path (real repository, `tests/integration/test_execution_observation_live_01b.py`)

Without `ATLAS_CLI_ELEVATE_CAPS` → `AUTHZ_DENIED` /
`authz-cli-elevation-required:execution.observe`, nothing written. With an
allow-list naming other privileged capabilities → `AUTHZ_DENIED` /
`authz-cli-elevation-incomplete:execution.observe`, nothing written. With
`ATLAS_CLI_ELEVATE_CAPS=execution.observe` → exit 0; identity sealed from live
git/host/toolchain; receipt stored under
`generated/ops/atlas3/observation/v1/<project>/<digest16>.json`; second run
returns the same `observation_id` and leaves the stored bytes unchanged;
`observed_is_current=false`, `authority=derived`,
`merge_authorization=NOT_GRANTED`.

## 4. Round-3 trust properties preserved by hash

The observer (`execution_observation/{git,runner,host,store}.py`) and the
receipt contract are byte-identical to the round-3 certified object
`e3708077`; only comments changed in `atlas3/cli.py` and
`execution_observation/observe.py`. The round-3 protections — ambiguous
multi-valued remotes, executable fsmonitor configuration, configured content
filters, dirty worktrees, git-environment redirection, secret-bearing remote
identity, platform normalization — are re-exercised by the unchanged suites
and controls at this object (§5) and re-verified by IV/ADV (§7).

## 5. Implementer-run gates at the certified object

| Gate | Result |
|---|---|
| ruff | `All checks passed!` |
| mypy `src` | `Success: no issues found in 415 source files` |
| Observation + authz suites (receipt contract, observer unit, live integration, authz gate) | 126 passed, 0 failed |
| Authorization / security suites (SEC-009 API auth, SEC-ADV004-B, AS-2.1 wave2 + track-B, AS-2.0 collab/inbox sec, atlas3 CLI, demo isolation incl. the DENY guard with the new pin) | 172 passed, 0 failed |
| Full suite (junit) | 6094 collected, 6082 passed, 8 skipped, 4 xfailed, 0 failed |

## 6. Negative controls (falsification)

`docs/scripts/ult_01b_1_negative_controls.py` now applies 35 mutations
(the 30 round-3 controls plus five authorization controls), each restored
byte-identical under a sha256 assertion. Baseline: 126 tests, 0
failures. Every one of the 35 controls kills at least one test (35/35); 35 distinct failing sets (`pairwise_distinct: True`, `each_nonempty: True`). Per-control failing-test names:
`docs/evidence/ULT-01B-1-negative-controls-f71b9f5d.json`.

| Authorization control | Kills | Failing tests |
|---|---|---|
| OC-AG execution.observe granted to the default operator | 4 | `test_default_launch_mints_no_privileged_credential`, `test_default_operator_cannot_observe`, `test_default_privilege_model_is_unchanged_except_the_one_registration`, `test_execution_observe_is_registered_privileged_and_default_off` |
| OC-AH execution.observe carried by read credentials | 4 | `test_default_privilege_model_is_unchanged_except_the_one_registration`, `test_execution_observe_is_registered_privileged_and_default_off`, `test_read_credentials_never_carry_execution_observe`, `test_read_only_operator_cannot_observe` |
| OC-AI execution.observe demoted from privileged | 3 | `test_default_privilege_model_is_unchanged_except_the_one_registration`, `test_execution_observe_is_registered_privileged_and_default_off`, `test_read_credentials_never_carry_execution_observe` |
| OC-AJ CLI observation gate removed (default operator observes) | 1 | `test_cli_is_denied_without_the_dedicated_capability` |
| OC-AK CLI elevation allow-list not checked for completeness | 2 | `test_cli_is_denied_without_the_dedicated_capability`, `test_cli_elevation_is_explicit_never_self_granted` |

`docs/scripts/at3_103_negative_controls.py`: 28/28 kill.

## 7. Independent and adversarial verification

| Round | Object | IV | ADV | CI (exact head) |
|---|---|---|---|---|
| authorization | `f71b9f5db72e9c7a0664f42f3c8b323525d4e70e` / `48d5c9b813d7552114bb61c7e61bcf1c4b0dfcc4` | PASS_WITH_NONBLOCKING_FINDINGS (**P0=P1=P2=0**, P3×3) | PASS_WITH_FINDINGS (**P0=P1=P2=0**; harness 22 mutants, 21 killed, 0 survived) | green (run 34344389532, 4/4 incl. Windows) |

Both verifiers used their own three-value vocabulary; a P3-only result is the
qualifying outcome. The implementer does not self-certify: the verdict lines
are quoted from the verifiers' reports, each bound to the exact HEAD/TREE.

**IV** reproduced the governance chain independently: the preimage at the
parent equals `origin/main` (blob `c6dd713a`, sha256 `505ca5bb…`); the
committed patch applied in a temporary worktree at the parent is
byte-identical to the file at the head (5 insertions, 0 deletions); the
post-image sha256 `3f6500e5…` equals the pinned exception; the DENY guard
passes at the head and fails after one appended byte; membership and
set-equality with the preimage hold; the AST differs in exactly three
top-level literals; credential minting and bearer resolution exercised
directly (default launch mints no privileged token; an elevated launch
operator's read credential never carries the capability; no API/MCP/web
route gates on it); the CLI matrix, idempotent live receipt and proof-v2
linkage reproduced on a real repository; the observer blobs are identical to
`e3708077` and the round-3 properties re-probed live; proof v1 goldens 11/11.
P3: pre-existing allow-list whitespace/comma tolerance (no widening); the
WORKLOG owner-grant record lands only in this docs-only seal; carried nits.

**ADV** attacked the surface: every non-exact allow-list token (`*`, case,
prefix, glob, trailing dot, zero-width and Cyrillic confusables, other
separators, quoted, 10 MB junk) refused; no principal other than an explicitly
elevated CLI operator (and the privileged credential minted for such an
operator, the existing SEC-009 design) resolves the capability; the freeze
guard rejects byte edits, copies, hardlinks, symlinks and renames of
`authz.py` (path and sha are bound together); the CLI has no argv, config or
vault-file path to elevation, writes nothing on denial and never echoes the
allow-list value; `proof --observation` links without launching git; every
round-3 trust property held live at this head; `provider.live`/`vault.write`
gating untouched. P3s: six authorization guards (unknown-capability check in
`require_cli_elevated_operator`, `*`, case, prefix, unknown-cap in
`elevated_operator`, read-credential intersection) are killed only by the
sha-pin freeze guard, not by a behavioural test — code holds on probe;
`str.strip()` also strips NBSP; the security suites emit pre-existing
`ResourceWarning`s from their own HTTP fixtures under `-W error` (identical at
the parent).

## 8. Exact-head CI at `f71b9f5d` (run 34344389532)

All four jobs `success` (conclusion read from the run, not assumed):

| Job | Result (CI's own pytest summary line) |
|---|---|
| `quality (ubuntu-latest, 3.12, full)` | ruff / mypy green; `6082 passed, 8 skipped, 4 xfailed` |
| `quality (ubuntu-latest, 3.13, compat)` | `6082 passed, 8 skipped, 4 xfailed` |
| `quality (windows-latest, 3.12, windows)` | `6025 passed, 62 skipped, 3 deselected, 4 xfailed`; line-ending golden fixture `1 passed` |
| `control-plane` | success |

## 9. Residual register

| Residual | Class | Owner / next package |
|---|---|---|
| A launch operator elevated with `execution.observe` receives a privileged API credential bound to that operator (existing SEC-009 behaviour for every privileged capability); the read credential never carries it | DOCUMENT_CONTRACT | — |
| `ATLAS_CLI_ELEVATE_CAPS` is an environment allow-list: whoever controls the CLI process environment can elevate (pre-existing model, SEC-ADV004-B-001); observation still runs only on a clean checkout and writes only under the vault | DOCUMENT_CONTRACT | — |
| The pinned exception covers exactly sha256 `3f6500e5…`; any later `authz.py` change (including formatting) re-trips the DENY guard and needs a new owner grant | DOCUMENT_CONTRACT | — |
| Round-3 P3 residuals (`ULT-01B-1-LIVE-EXECUTION-OBSERVATION.md` §7) are not absorbed by this package | DEFER_WITH_RESIDUAL | follow-up test package |
| Six authorization guards hold on probe but are protected only by the sha-pin freeze guard rather than by behavioural tests (ADV Z06/Z08/Z09/Z10/Z11/Z16: unknown-capability check, `*`, case, prefix, unknown-cap in `elevated_operator`, read-credential intersection) | DEFER_WITH_RESIDUAL (tests only; kept out of this docs-only seal) | first follow-up test package |
| `ATLAS_CLI_ELEVATE_CAPS` parsing tolerates surrounding whitespace, empty items and NBSP (pre-existing `str.strip()`/`split(",")`); only the exact token grants | DOCUMENT_CONTRACT | — |
| Security suites emit `ResourceWarning: unclosed socket` from their own HTTP-server fixtures under `-W error` (pre-existing, identical at the parent) | DEFER_WITH_RESIDUAL | test hygiene package |

## 10. Claims

**Proven at `f71b9f5d`:** `execution.observe` is registered through the
governed authz system under a pinned owner grant; it is privileged and
default-off; the observation CLI fails closed without explicit elevation and
runs the real live path with it; no read credential or default operator
receives the capability; no existing capability widened; credential minting,
API authentication and bearer handling untouched; the live observer and
receipt contract are hash-identical to the round-3 certified object; proof v2
linkage and proof v1 unchanged; the DENY guard still fires on any further
`authz.py` byte change.

**Not made:** merge authority; ULT-01b-2 or ULT-01b-3 progress; any change to
default privilege; absorption of the round-3 P3 residuals.
