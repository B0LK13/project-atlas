# Prime Local 001 Runbook

This runbook describes the current candidate state. It does not install a
system service, enable a user unit, import credentials, or claim cloud/offline
inference.

## Pinned install

```bash
scripts/prime-local-001-install.sh /path/to/new/prime-local-001
```

The script refuses a non-empty unrelated directory, checks out the exact
Prime Agent source SHA, runs `npm ci` and `npm run build` with Node >=22.8.0,
and writes `atlas-prime-runtime-manifest.json` with secret-free identities.
The captured candidate manifest is
`evidence/prime-local-001-runtime-manifest.json`.
Keep source, runtime, session, config, workspace, temporary data, and evidence
in separate paths. Set `PRIME_AGENT_CODING_AGENT_DIR` and
`PRIME_AGENT_SESSION_DIR` to mission-owned paths; never point them at the
operator's normal `~/.prime/agent` state.

Run the model-free upstream contract smoke with
`scripts/prime-local-001-model-free-smoke.sh /path/to/runtime`. It validates
the source pin, uses a temporary empty HOME and minimal environment without
provider credentials, and runs only the pinned RPC JSONL/ACK semantics tests.
Do not use the aggregate
upstream `npm test` for this smoke: it includes provider E2E tests and can
trigger network calls or local model downloads.

Run the Atlas regression suite from the repository root with
`PYTHONPATH=. ./.venv/bin/python -m pytest -q`. The explicit module invocation
keeps the repository's `tests.*` package imports stable; the bare virtualenv
console script does not add the repository root to `sys.path` on this host.
The Prime-focused checks remain separately identifiable from this full suite.

## Atlas adapter

Use `adapter: "prime-agent"` in an Atlas profile and set
`adapter_options.executable` to the pinned runner or release executable and
`adapter_options.sandbox_argv` to the reviewed Bubblewrap launch profile.
On the unattended Linux path, Prime preflight requires the resolved launcher
to be `/usr/bin/bwrap` and requires `--die-with-parent`, `--new-session`,
`--unshare-all`, `--proc`, `--dev`, `--tmpfs`, `--ro-bind`, and `--chdir`.
Arbitrary existing executables (including pass-through shell wrappers) are
rejected; a worktree alone is not accepted as isolation. Deployment may add
stricter mounts and limits, but may not remove this minimum contract.
Also set `adapter_options.runtime_manifest` to the manifest produced by the
pinned install. Preflight verifies its exact `upstream_sha` and
`source_commit_verified` flag before any daemon or RPC launch.
Atlas writes the task intent and lease before calling the adapter. Prime's
RPC prompt response is only an acceptance/queueing ACK. Only the observed
`agent_end` event is reported as terminal execution; Atlas acceptance still
checks the workspace and tests.

The adapter supports the pinned public daemon protocol v7 when
`adapter_options.daemon_socket` is configured. It creates
`lifecycle: "resident"` sessions, closes only Atlas's client socket, and can
attach a retry to the returned active-session id. The model-free handshake and
resident create are recorded in `evidence/PRIME-LOCAL-001-DAEMON-SMOKE.md`.
The adapter records Prime's public event generation/sequence cursor and attach
snapshot. A reconnect-style attach advertises the saved cursor, and duplicate
or older same-generation events cannot move recorded progress backwards. This
is a cursor/attach contract, not proof of complete replay across a daemon
restart: Prime's replay status and snapshot still require reconciliation before
an uncertain mutation is retried. A worker crash in a daemon-owned resident
session currently remains `UNKNOWN`; Prime requires a documented client-owned
fresh runtime context for worker retry, which this slice does not fabricate.
Full worker/kernel crash recovery and real-model detached development remain
separate gates. No invented `resident`
flag is used; `lifecycle` is the documented daemon command field.

The pinned runtime's Python kernel is explicit in the manifest. Set
`PRIME_AGENT_KERNEL_PYTHON` only to an executable in an existing environment
that already contains a current `prime-agent-runtime` and Prime's default
Python packages; Prime validates that at kernel startup. When it is unset,
Prime bootstraps and owns its isolated kernel venv. A host `python3` being
present is not evidence that either mode is ready.

The existing read-only control projection exposes Prime's adapter identity,
session/generation cursor, candidate/tree binding, usage status, and child
registry from the evidence-owned metadata. It remains an observation surface:
pause, resume, cancellation, reconciliation, and all other mutations still
use the existing Atlas control route.

`adapter_options.daemon_lifecycle: "client_owned"` is an explicit recovery
opt-in. Preflight permits it only for a profile with no credential environment;
the adapter then sends only non-secret `recoveryConfig` fields and an empty
launch environment. Profiles needing provider credentials remain on the
resident path until the existing credential broker can provide a non-persistent
mission capability.

To enable native children, a profile must additionally set
`allow_children: true`, provide `child_admission.patch_id` equal to
`prime-agent-5d25a44-atlas-child-admission-v1`, set a bounded
`child_admission.max_children` (1–8), set `max_child_seconds` and
`max_budget_seconds`, and point `runtime_manifest` at the manifest containing
the exact patch hash. The broker binds the Atlas agent role and a hash of the
resolved workspace/tool/mutation scope. An unpatched, unmanifested, or
incompletely budgeted runtime is refused before launch.

For a local inference profile, set `adapter_options.inference_mode` to
`local-only`, provide `local_endpoint`, `provider`, and `model`, and use a
`NOT_APPLICABLE` credential with an empty environment allow-list. Preflight
queries only the loopback `/v1/models` catalog and requires the selected model
to be advertised; it does not perform inference. An unreachable endpoint or
missing model is rejected before dispatch, with no cloud fallback.

When Atlas resumes an explicit Prime session, the adapter reads only the
matching prior daemon evidence file to seed `resumeCursor`; a cursor belonging
to another session is ignored. The adapter never replays an uncertain mutating
command solely because a transport connection was lost.
Daemon command IDs are deterministic from the stable client identity and
canonical command body, so reconnecting the same semantic request does not
mint a new ID merely because a local counter was reset.

## Stop and rollback

Pause/cancel/deadline actions must be issued through `atlas program control`.
An uncertain Prime attempt is reconciled from evidence and is never blindly
replayed. Rollback removes only the candidate adapter/runtime registration
from the candidate branch; it does not delete Atlas state, taskstores, logs,
or evidence.

## Current evidence boundaries

The pinned source was installed and built model-free. Version/build and
parser/adapter contract tests are separate from provider inference. No real
provider, local model endpoint, credential, or production deployment has been
used by this work package.
