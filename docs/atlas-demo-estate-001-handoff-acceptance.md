# ATLAS-DEMO-ESTATE-001 — lead-DAG-agent handoff acceptance

Status: this session's read-only acceptance of the estate-preparation lane's
handoff, recorded per its own request (`DEMO-SCENARIO.md` Scenario C: "this
finding is reported here for the lead DAG agent to turn into a separate
Atlas remediation node"; `ATLAS-CHECKOUT-NOTE.md` §8: "When the lead DAG
agent supplies the demo candidate ref..."). Everything below is
`VERIFIED_FROM_LOCAL_ARTIFACT` — read directly from `D:\Atlas-Demo\` in
this session, not accepted secondhand. No file under `D:\Atlas-Demo\` was
modified to produce this record; that estate remains a separate lane's
workspace.

## Estate preparation state

Read from `D:\Atlas-Demo\DEMO-ACCEPTANCE.md` and
`D:\Atlas-Demo\DEMO-SCENARIO.md`:

- `DEMO_ROOT_SAFE`, `RESET_REPRODUCIBLE`, `ESTATE_FINGERPRINT` = PASS
  (adversarial containment tests, double reset-reproducibility, fingerprint
  stability across both reset runs).
- Alpha (Scenario A) and Beta (Scenario B): all listed gates PASS,
  including two that specifically demonstrate honest non-answers over
  fabrication (`BETA_UNKNOWN` returning `[unknown] UNKNOWN`, `BETA_GAP`
  confirming a real doc/code gap rather than asserting one).
- Gamma (Scenario C): `GAMMA_PROJECT_CONTEXT` = PASS.
  `GAMMA_NEXT_WORK` is **not** PASS — see below. One correction to how a
  prior summary of this estate framed it: Gamma is not blanket
  `READY = YES`; its project-context gate passed, its next-work gate is an
  explicit, documented open item, not a rehearsal failure.
- Cross-cutting: `WINDOWS_CLI` = PASS but explicitly WSL-rehearsed only
  (does not confirm native-Windows-only concerns); `SECRET_SCAN` = PASS (0
  unapproved findings); `CROSS_PROJECT_LEAK` = PASS (0 hits, verified with
  genuinely distinctive per-project terms).
- Autonomy-specific gates (`GAMMA_DISPATCH`/`IMPLEMENTATION`/
  `INDEPENDENT_IV`/`REMEDIATION`/`OWNER_FRONTIER`) are explicitly
  `PENDING_ORCH_DEMO_GATE` — not attempted by the estate lane, correctly
  left for this session's actual ORCH work.
- `ATLAS-CHECKOUT-NOTE.md`: the estate's Atlas checkout is a dedicated
  local clone (`git clone --local`, no network remote beyond a read-only
  local source), currently on a provisional, uncertified snapshot
  (`ATLAS_HEAD` provisional = `4e71cce0d1c97f408347e256300a41590da4c352`).
  Explicitly not yet the showcase candidate; explicitly waiting on this
  session to supply a final ref.

Recorded classification:

- `ATLAS_DEMO_ESTATE_001 = PREPARATION_TERMINAL` (matches the estate's own
  completion-criteria section in `DEMO-ACCEPTANCE.md`, which distinguishes
  `ESTATE_PREPARATION_COMPLETE` from `FULL_AUTONOMOUS_DEMO_CERTIFIED` as
  deliberately separate claims)
- `ESTATE_REPRODUCIBLE = PASS`, `SECRET_SCAN = PASS`,
  `CROSS_PROJECT_LEAK_COUNT = 0`
- `ALPHA_READY = YES`, `BETA_READY = YES`
- `GAMMA_PROJECT_CONTEXT_READY = YES`; `GAMMA_NEXT_WORK_LENS = NOT_READY`
  (see finding below) — stated separately rather than as one blended
  `GAMMA_READY` flag, since the estate's own document does not blend them
- `FINAL_ATLAS_PIN = PENDING`
- `NATIVE_WINDOWS_FINAL_REHEARSAL = PENDING` (see below)

## Gamma next-work finding — accepted classification

From `DEMO-SCENARIO.md` Scenario C's source-contract investigation
(`project_next.py`, `project_roadmap.py`,
`intelligence/next_action.py` docstrings, checked directly, not assumed):
none of Atlas's existing read-only "next work" lenses is contracted to
surface a document-declared, ready-to-implement feature item (the
estate's `TASK-017` stand-in). Each is scoped, by its own docstring, to
pipeline/knowledge hygiene (pending reviews, coverage gaps, unknown/
conflict rollups, roadmap blockers) — not to "what should the development
agent build next."

Accepted:

- `BUG = NO`, `RANKING_GAP = NO` — the lenses are working exactly to
  their documented contract; there is no defect to fix.
- `MISSING_LENS = YES`, `PRODUCT_SEMANTIC_UNDERSPECIFIED = YES` — no
  existing contract defines what makes a requirement "ready," how it
  would be declared, or how it would be weighed against pipeline-hygiene
  signals.
- `OWNER_PRODUCT_DECISION_REQUIRED = YES`. The concrete question: should
  Atlas gain a distinct product-work lens capable of answering "what
  should the development agent build next?", separately from "what
  project/knowledge hygiene needs attention next?" — and if so, is it a
  new lens or a mode of an existing one (`next`/`context`/`brief`)?
- `GAMMA_PRODUCT_WORK_LENS = OWNER_ONLY`. This node does not block
  unrelated work; it is recorded and set aside, not chased into an
  unauthorized implementation.

No `src/` change is made in pursuit of this question from this record. No
TASK-017-specific workaround, ranking-heuristic change, or Gamma mutation
is made or proposed.

## Native Windows final rehearsal — packet (prep only, not executed)

`DEMO-SAFETY.md` records this estate was authored and rehearsed from a
WSL2/Linux session; PowerShell scripts were syntax-validated with `pwsh`
from there, but a full native-Windows execution pass
(`verify-demo.ps1` / `run-demo.ps1` actually run on a Windows host) is
explicitly "not yet claimed."

This session is itself a native Windows / PowerShell-capable host
(`win32`, `pwsh` available) and is therefore a candidate to run that
pass — but not yet, and not from this record. Per the estate's own
`ATLAS-CHECKOUT-NOTE.md` §8 ("do not falsely certify... present this
provisional HEAD as the final showcase version"), running the native
rehearsal against the current provisional, uncertified `ATLAS_HEAD` would
produce evidence bound to a SHA that is not the actual showcase
candidate — worse than no evidence, since it would look like a real
certification pass. Recorded packet for when a final HEAD is pinned:

- `EXACT_ATLAS_HEAD` — to be supplied by this session once the current
  docs-IV wave, Gamma owner decision (or explicit demo-scope exclusion),
  and Cursor-acceptance decision are all resolved (see prerequisites
  below); not the current provisional
  `4e71cce0d1c97f408347e256300a41590da4c352`.
- `COMMAND` — `scripts\verify-demo.ps1` and `scripts\run-demo.ps1`
  (already present under `D:\Atlas-Demo\scripts\`; not authored here).
- `HOST` — this session's own native Windows/PowerShell environment, or
  another explicitly Windows-native host if the owner prefers a fully
  separate one.
- `TARGET` — `D:\Atlas-Demo\atlas\project-atlas` after re-pin, per the
  checkout note's own re-pin procedure (`git fetch source-readonly <ref>`
  / `git checkout <ref>` / `git tag atlas-demo-v1`).
- `SPECIFIC_CONCERNS_TO_CONFIRM` (named directly in `DEMO-SAFETY.md`):
  real `D:\` drive semantics, native process handling in
  `reset-demo.ps1`'s stop-process step, Windows path-length limits,
  native `Invoke-WebRequest` behavior where used.
- `PASS_CRITERIA` — `verify-demo.ps1` reproduces the same PASS set already
  recorded from the WSL rehearsal, run natively, with a fresh
  `evidence\receipts\verify-demo-receipt.json`.
- `FAIL_CRITERIA` — any gate that passed under WSL fails natively (would
  indicate a real Windows-specific defect, not a rehearsal artifact).
- `EVIDENCE_PATH` — `D:\Atlas-Demo\evidence\receipts\` (existing
  convention, not a new path invented here).
- Not executed by this record. `AUTHENTIC_WINDOWS_HOST = YES` (once run)
  would not itself imply `AUTHENTIC_CUSTOMER_PILOT = YES`, per the
  estate's own stated honesty boundary.

## Prerequisites before any final Atlas showcase pin

Not satisfied yet, consistent with the estate's own "do not falsely
certify" instruction:

- Current docs-IV wave (#623 merged; #624/#625/#626 integrating) fully
  drained.
- P0/P1 = 0 on the pinned candidate; any Demo-path P2 explicitly
  non-blocking.
- ORCH001E truth integrated (done — #623).
- Cursor-acceptance decision resolved (packet prepared, PR #626;
  execution decision still owner-only).
- Gamma product-work-lens decision resolved, or explicitly excluded from
  the demo's claims for this showcase.
- Native-Windows final rehearsal run against the actual pinned candidate,
  not the provisional snapshot.

`MERGE_AUTHORIZATION = NOT_GRANTED`. This record does not pin
`ATLAS_HEAD`, does not execute any demo script, and does not mutate the
estate.
