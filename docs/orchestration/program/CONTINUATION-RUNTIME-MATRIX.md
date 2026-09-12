# Supported-runtime matrix — durable continuation layer

The rule this table exists to enforce: **executable presence is not adapter
support.** A runtime appears as supported only where a real adapter was written
against its verified interface *and* this layer's behaviour was demonstrated
through it.

| runtime | adapter exists | used to validate THIS layer | status here |
| --- | --- | --- | --- |
| `local-command` (labelled FIXTURE) | yes | **yes — all 43 tests** | `VALIDATED_FIXTURE_ONLY` |
| `claude-code` | yes (`adapters/claude_code.py`) | **no** | `PRESERVED_NOT_EXERCISED` |
| `codex` | yes (`adapters/codex.py`) | **no** | `PRESERVED_NOT_EXERCISED` |
| Cursor | no execution adapter | no | `NOT_SUPPORTED` |
| GitHub Copilot | no execution adapter | no | `NOT_SUPPORTED` |
| any other CLI | no | no | `NOT_SUPPORTED` — there is deliberately no generic any-CLI adapter |

## What `VALIDATED_FIXTURE_ONLY` does and does not claim

`FIXTURE_RUN != REAL_RUNTIME_COMPATIBILITY.`

**Established:** restart reconciliation, no-replay of completed work,
quarantine of uncertain external effects, checkpoint resume at the next step,
blocked-task fallback, empty-queue waiting, wake-and-launch-exactly-once,
pause/resume, refusal on corrupt checkpoints and stale leases,
authority-and-budget recheck before dispatch, process cleanup by pid plus start
identity, and zero model calls.

**Not established:** that any of this behaves identically when the worker is a
real agent runtime. The fixture adapter is deterministic; a real runtime is
not, and it can be cancelled, rate-limited, or made to return an unparseable
result in ways no fixture reproduces.

## Why the real profiles are preserved but not launched

`MODEL_BACKED_DISPATCH = DISABLED_PENDING_R12_AND_IV.` The Claude Code and
Codex profiles are untouched and still load, resolve and validate. They are not
launched here because:

* launching them costs a paid model call, which is not authorized;
* R-12 (cleanup by process identity in a shared session) is open;
* this layer has not had independent verification.

Envelope budgets default `max_model_calls` to **0**, and an
`UNCERTAIN_EXTERNAL_EFFECT` task may not budget a model call at all
(`ENVELOPE_MODEL_CALLS_FORBIDDEN`) — so the switch cannot be routed around by
an envelope that simply asks for one.

## Every worker's explicit limits

Carried by the profile (`profiles.py`) and narrowed, never widened, by a task:
credentials mechanism (names only, never values), capabilities, workspace
scope, allowed mutation prefixes, concurrency, per-task duration, attempt count
and estimated spend. The continuation envelope adds the per-task budget and
deadline, both rechecked immediately before each dispatch.

Suspended, mismatched and duplicate-role workers launch nothing — the
enrollment filter removes them before binding, and a dispatch with zero
bindable agents fails closed rather than running unbound.
