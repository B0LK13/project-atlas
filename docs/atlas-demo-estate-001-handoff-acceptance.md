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
- `GAMMA_PROJECT_CONTEXT_READY = YES`; `GAMMA_NEXT_WORK_ITEM_SURFACED = NO`
  (see corrected finding below — the lens exists, the structured record
  it needs was never produced) — stated separately rather than as one
  blended `GAMMA_READY` flag, since the estate's own document does not
  blend them
- `FINAL_ATLAS_PIN = PENDING`
- `NATIVE_WINDOWS_FINAL_REHEARSAL = PENDING` (see below)

## Gamma next-work finding — corrected classification

**Correction (review):** the estate's original framing ("no existing Atlas
lens is contracted to surface this") is not quite right, and this record
initially repeated it uncritically. Checked further, directly:
`project_roadmap._load_roadmap_source()` reads `projects/<id>/roadmap.md`
in the *vault* and, via `_parse_fenced_record()`, parses a fenced JSON
block containing `roadmap_items`; `_next_unlock()` then selects the first
unfinished item and `project_next._collect_roadmap()` turns it into a
`roadmap_unlock` candidate. This mechanism genuinely is contracted to
surface exactly "here is the next ready item" — it is not
knowledge/pipeline-hygiene scoped the way `next_action.py` is.

So the lens is not missing. What's missing, verified directly: nothing in
the ingestion/discover pipeline (grepped `src/project_atlas/` for any
writer of `roadmap.md` or `roadmap_items` outside `project_roadmap.py`
itself — none exists) transforms a prose source document into that
structured `roadmap_items` record. The estate's actual gamma project has
`docs/ROADMAP.md` naming TASK-017 as "the next ready unit of work," plus a
requirements doc, an ADR, and a skipped spec test — all prose/convention,
not the hand-authored fenced-JSON format `_parse_fenced_record()` requires.
Populating `projects/atlas-showcase-gamma/roadmap.md` with a matching
record was not attempted here (would be inventing estate content from
this lane, not a code change, but still not this record's call to make
unilaterally) and nothing in the pipeline would do it automatically today
regardless.

Corrected:

- `BUG = NO`, `RANKING_GAP = NO` — unchanged; the lenses do exactly what
  they're contracted to do.
- `MISSING_LENS = NO` (corrected from `YES`) — `roadmap_unlock` already
  exists and is contracted for this. `SOURCE_ADAPTER_GAP = YES` — nothing
  derives a structured `roadmap_items` record from the prose
  requirements/ADR/roadmap documents a project like this actually has.
- `OWNER_PRODUCT_DECISION_REQUIRED = YES`, but the question is sharper
  than originally stated: should Atlas gain an ingestion/adapter step
  that derives `roadmap_items` from a documented "next ready work" 
  convention (e.g. a requirements doc + ADR + a correspondingly-skipped
  test file), feeding the *existing* `roadmap_unlock` lens — or is
  hand-authoring the structured record the intended workflow, in which
  case this estate's prose-only documents are themselves the gap, not
  Atlas? Both readings are live; this record does not resolve which.
- `GAMMA_PRODUCT_WORK_LENS = OWNER_ONLY`. Unchanged conclusion, corrected
  reasoning. This node does not block unrelated work.

No `src/` change is made in pursuit of this question from this record. No
TASK-017-specific workaround, ranking-heuristic change, hand-authored
`roadmap.md` record, or other Gamma mutation is made or proposed.

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
