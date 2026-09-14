# Prime Local 001 daemon smoke

Observed on 2026-09-14 against the installed runtime built from
`5d25a44bd22e1c1fe8321e141cd6c3932563d14c`.

The Atlas `PrimeDaemonClient` connected to a fresh local Unix socket, checked
the public `prime-agent.daemon` protocol v7 handshake, and created a
`lifecycle: resident` session. The daemon returned active session
`4ce6406e3e74`, after which the client issued the documented
`set_rlm_max_depth` command with `maxDepth: 0`. The client disconnected without
completing a prompt; no model, provider, credential, or inference request was
used. The isolated daemon was then terminated by its recorded process
identities.

The guarded model-free smoke script was executed against the same runtime in
the network-isolated Bubblewrap profile: 2 Vitest files and 14 tests passed in
6.36 seconds. It validated only RPC JSONL framing and prompt/response
semantics inside a temporary empty HOME and minimal environment; no provider
or model was used by this smoke.

On the same installed runtime, the Atlas adapter preflight passed against the
manifest-bound `/home/gebruiker/prime-local-001-runtime/prime-agent.sh` and
the available `/usr/bin/bwrap` launcher, followed by `prime-agent.sh
--version` returning `0.9.4`. This is a model-free identity and launchability
check only; the wrapper still requires a reviewed, complete sandbox argv for
actual unattended execution.

The same runner then executed inside a fresh Bubblewrap scope using read-only
system/runtime mounts, a temporary `/tmp`, a hidden `/home`, and
`--unshare-all` networking. It returned `0.9.4`. This proves the selected
model-free sandbox launch path, not that arbitrary model-generated commands
are fully security-isolated; that requires the reviewed production profile and
adversarial execution gate.

Adversarial probes in that same scope returned `secret=DENIED` for the host
SSH directory, `other-workspaces-and-policy=DENIED` for the Atlas candidate and
unrelated cache state, and `network=DENIED` for a loopback connection attempt
to the host Ollama port. These are observed denials for this exact Bubblewrap
argv, not a blanket security claim for arbitrary future sandbox profiles.

This proves the public daemon transport and resident create contract only. The
adapter's model-free contract suite additionally proves attach snapshot/cursor
capture and monotonic rejection of stale or duplicate same-generation events.

An isolated runtime probe then created a resident session, disconnected the
client, stopped the supervisor using the supervisor PID announced in the
daemon handshake, restarted the same pinned runtime against the same session
directory, and successfully attached the original active session. Observed
result: `attach_success: true`, `snapshot_present: true`, and
`replay.status: complete`; the replay cursor reported a new event generation
with sequence `0`. No prompt or model call was made. A preceding launcher-only
stop was intentionally retained as a negative result: it left Prime's own
supervisor alive and the next attach returned a shutting-down error. This
demonstrates why Atlas records process-start identity and supervisor generation
instead of trusting a launcher PID alone.

It does not prove real-model development, worker/kernel crash recovery, or
Atlas independent verification.

A separate isolated worker-crash probe killed only the worker PID returned by
`create`. The daemon then returned `Session worker is failed` for both
`get_state` and `attach`; its public `retry_worker` command returned
`Waiting for a client with fresh runtime context`. This is recorded as a
negative capability result: daemon-owned resident workers do not receive an
automatic recovery claim from this adapter. Atlas therefore leaves the
attempt uncertain and does not replay the prompt. A future recovery slice
must use Prime's documented client-owned recovery context, bind it to Atlas
admission and credential policy, and test it independently.

The documented recovery route was then exercised separately, still without a
prompt or model call: a `client_owned` session was created with stable client
identity, its worker was killed, and a subsequent attach supplied
`owned_session_recovery_context` plus a fresh non-secret `recoveryConfig`. The
attach succeeded, returned a snapshot, and reported the worker as `ready`.
This proves the upstream recovery contract, not Atlas integration of it. The
standard adapter remains daemon-owned `resident` by design until launch
environment values can be supplied through the existing credential boundary
without being persisted in command evidence.

The host's available `bwrap` harness was also exercised with read-only system
mounts, a writable disposable workspace mount, and no home-directory mount;
the scope probe could read the workspace and could not read `/home/gebruiker/.ssh`.
The adapter now fails closed unless the resolved launcher is `/usr/bin/bwrap`
with the required namespace, process-lifetime, temporary-filesystem, and
mount/chdir controls. A pass-through wrapper such as `/bin/true` is rejected
by preflight; the presence of `bwrap` alone is not treated as a security grant.
Preflight also rejects broad `/`, `/home`, and `/root` bind sources and
writable `/etc` mounts, so a profile cannot turn the launcher check into a
host-wide writable mount.

The Atlas supervisor vertical-slice test also passes with a disposable v7
daemon fixture: Atlas creates the lease and dispatch intent, the Prime adapter
starts the daemon and sends the bounded task, and Atlas—not the worker report—
observes workspace acceptance and records the task as `CERTIFIED`. This is
control-plane integration evidence only; the daemon fixture performs no model
inference and is not real-provider development evidence.

The built Prime TypeScript compatibility hook was also exercised against the
Atlas Python broker over a mission-local Unix socket. One reserve, commit, and
release request completed in order with the mission/task/attempt/parent,
role/scope, and child resource-limit bindings intact. This proves the
cross-language admission framing and lifecycle only; it does not prove that a
real provider produced a child or that actual cumulative provider usage has
been reconciled.

The adapter's contract suite also exercises the documented
`get_session_stats` daemon command. When Prime returns its `tokens` and `cost`
fields, they are stored as usage evidence; `cost` is explicitly labelled a
client-side estimate and is never presented as provider billing. Missing or
invalid stats produce an explicit not-reported/unknown status rather than a
zero usage claim. The model-free smoke did not invoke inference, so it does
not establish real provider usage.

Native child admission records are additionally written to a mission-local
append-only JSONL journal with `fsync` before a reserve response is released.
Commit and release transitions are journaled as separate records. The journal
is evidence and recovery input; it is not an acceptance receipt and does not
replace Atlas's durable attempt state.
Each journal entry also carries the pre-dispatch workspace, candidate SHA, and
tree SHA binding captured by the Atlas adapter.

The adapter's launch probe recognizes a non-empty journal only when every
record is valid and bound to the same mission, task, and attempt. An empty,
malformed, or foreign journal remains UNKNOWN rather than authorizing a replay.

Post-fix remeasurement for candidate commit `7da4b1c2e1ba95281e7d37ab4995536947f15c8c`:
the Prime adapter and supervisor-focused suite passed 67 tests, Ruff and
Mypy passed, and the network-isolated model-free smoke passed 14/14 tests.
The adapter test also directly rejected an existing `/bin/true` pass-through
wrapper after validating the runtime manifest. These results are bound to this
candidate commit; they do not promote the earlier model-free evidence to
real-provider, child-execution, or deployment evidence.
