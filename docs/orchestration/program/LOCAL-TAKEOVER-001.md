# Local supervisor and continuation acceptance

ATLAS-END-TO-END-IMPLEMENTATION-TAKEOVER-001 continues the frozen
`e3b375588d013f1e5552adcb872201633ba1e4ef` /
`aa8562ba08cf3c8e1dd07fb7300ebd309cf8e81f` design. The final candidate and
results are bound in the external evidence manifest, not inferred from this
document or transferred from the predecessor.

## Requirement mapping

| Requirement | Enforcement and executable evidence |
| --- | --- |
| F-01 containment | `path_safety`, guarded queue/loader/store/continuation/capsule/reconciliation and workspace checks; `test_program_containment_takeover.py` |
| Equivalent evidence paths | Shared decision, registry, SDK pause/stop/lock and service-identity helpers; guarded local-command marker/transcript writes and projection reads |
| F-02 ownership | Restart rejects an unknown/reused PID before witness/ACT, rechecks the witness at drain/start boundaries; `test_program_pid_reuse_takeover.py` and restart regression |
| Concurrent ownership | Kernel locks for resident state, queue, and operator restart, released on exit without deleting lock inodes; `test_program_dispatcher_lock_takeover.py` |
| Current authority | Absolute registry binding, fresh enrollment checks and envelope validation on actual dispatch; enrollment/authority regression and revoked demonstration |
| Continuation | Actual dispatch consults reconciliation; uncertain, contradictory, terminal or lost execution evidence refuses launch; no-attempt eligibility is not execution |
| Evidence preservation | Explicit uncertainty survives boundary projection; commands come from observed transcripts, not reconstructed diffs |
| Pause and restart | Separate real dispatcher processes preserve pause and completed output; `test_takeover_continuation_end_to_end.py` |

## Operator boundary

Supply `--governed-root` explicitly when state, queue, programs and workspaces
are siblings. The root is an operator-selected directory; it is never inferred
from the common ancestor of paths found in queue data. With no explicit root,
dispatcher state and standalone queue roots are their own narrow boundaries.
Absolute operator bindings inside the selected root are supported. Untrusted
relative components reject absolute paths, `..`, backslashes, symlinks,
reparse points and multiply linked regular files. Do not migrate old state by
broadening the root until it fits.

The registry is a separate explicit operator binding; it is made absolute once
and read again before dispatch. A missing, changed or revoked enrollment does
not authorize a fallback to the placeholder profile.

Example local operator surface (replace placeholders with reviewed paths):

```sh
ENV/bin/atlas program queue --action admit --governed-root ROOT \
  --queue-root ROOT/queue --program ROOT/program.json --state-root ROOT/state \
  --admitted-by OPERATOR --reference APPROVAL
ENV/bin/atlas program dispatcher --action run --governed-root ROOT \
  --state-root ROOT/state --queue-root ROOT/queue --registry REGISTRY \
  --checkout CHECKOUT --max-seconds 30
ENV/bin/atlas program dispatcher --action pause --state-root ROOT/state
ENV/bin/atlas program dispatcher --action resume --state-root ROOT/state
ENV/bin/atlas program continuation --action reconcile --governed-root ROOT \
  --state-root ROOT/state --queue-root ROOT/queue
```

Pause withholds new work and lets a running task finish. A program-level pause
must also be cleared through the program control command; dispatcher resume
does not silently clear a different scope's pause. Restart defaults to delegate
mode. Supervised restart requires an explicit operator-written argv in
`state/.atlas/orchestration/program/dispatcher/restart-command.json`, including
the same governed root, queue and registry. Identity refusal requires operator
inspection; do not delete the heartbeat or uncertainty record to force a run.

## Reproduce with a non-editable installation

From the checked-out candidate, build wheels with `python -m pip wheel . -w
WHEELS`, preserve every wheel and its SHA256, and install with a fresh venv using
`ENV/bin/pip install --no-index --find-links WHEELS project-atlas==2.0.0`.
Run `ENV/bin/pip check`, inspect `project_atlas.__file__`, and compare installed
package bytes with `src/project_atlas` and `src/atlas_contracts` before tests.

Run each scenario into a distinct nonexistent directory:

```sh
ENV/bin/python CHECKOUT/scripts/atlas_takeover_demo.py \
  --checkout CHECKOUT --root NEW_DEMO_ROOT --scenario complete
# Repeat with new roots for --scenario revoked and --scenario uncertain.
```

Expected task launch sequences: complete `[1,0,1,0]`; revoked and uncertain
`[1,0,0,0]`. Each scenario uses four actual dispatcher processes. Workers are
bounded fixture commands and all child PIDs must be gone afterwards. Inspect
`result.json`, the preserved first-task output, checkpoints, capsule and process
identities rather than accepting a PASS string alone. The uncertain scenario
is labelled fault injection, never an observed external incident.

## Limits and decisions

- Proven local runtime support is the bounded `local-command` fixture adapter.
  The resident rejects non-fixture effective/verifier profiles and enrollment
  substitutions before supervisor construction or runtime discovery, with
  `MODEL_DISPATCH_DISABLED`. A zero-model label alone is not enforcement.
  Generated instruction files are not runtime compatibility evidence. Codex,
  Claude, IDE and remote model execution require separate acceptance.
  Bounded source review also identified evidence-path concerns in non-fixture
  adapters. They are not part of this accepted runtime profile; keep model
  dispatch disabled and require sink-specific repairs and zero-model negative
  probes before any separate real-runtime acceptance.
- Pause/restart continues between tasks. A checkpoint requesting an adapter
  to resume inside a task is refused unless that execution path is implemented;
  this delivery does not invent a step-resume adapter or replay a partial task.
- Containment validates paths and rejects planted links. It is not an OS
  sandbox for arbitrary commands or hostile simultaneous directory replacement.
  Lock ownership assumes cooperating processes on a filesystem with working
  OS file locks. Platform-specific acceptance is recorded separately.
- Reboot, logout and power-loss recovery remain separate evidence claims.
  Local acceptance authorizes no service installation or live activation.
- Managed documentation uses the approved local spool when the shared Vault
  is unavailable. Synchronization and a strict receipt remain distinct from
  source/test acceptance and must not be fabricated.
