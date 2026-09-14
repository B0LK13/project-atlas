# B1 — in-flight process identity

## The finding

`adapters/base.py` computed the child's pid and start identity at spawn, but
they only reached `AttemptRecord` in `supervisor._settle_running`, on
`ADAPTER_RETURNED`. A supervisor killed mid-flight therefore left an attempt at
`ADAPTER_INVOKED` with `process_pid = None`.

`recovery.worker_still_alive()` returned a bare `False` for that — the same
`False` it returned for a process that had genuinely exited — and
`classify_attempt` turned it into the sentence *"the worker was launched, is
gone, recorded no outcome"*.

It was observed saying that about a worker that was still running.

## Reproducer

`repro.sh` creates a test-owned workspace, starts a program whose fixture
worker hangs, **SIGKILLs only the supervisor**, confirms the orphaned worker is
still alive, and runs `program reconcile`. `find_worker.py` locates the child by
reading `/proc/<pid>/cmdline` and requiring the fixture script to be an actual
argv element — `pgrep -f` was tried first and matched the watcher's own command
line.

```bash
./repro.sh /path/to/a/checkout /path/to/scratch
```

The checkout must have its own venv with the tree under test installed. An
editable install resolves `import project_atlas` to the *installation* tree, so
running the predecessor's reproducer from the repaired checkout's venv silently
tests the repaired code — that happened here once and produced a false pass.

## Before and after, same reproducer

| | Predecessor `4aac27ae` | Repaired |
| --- | --- | --- |
| Orphan worker | pid 878705, alive | pid 878730, alive |
| Durable `attempt.process_pid` | `None` | `None` (by design — see below) |
| `recovery_action` | `NEEDS_RECONCILIATION` | `WORKER_STILL_RUNNING` |
| Reason | "the worker was launched, **is gone**…" | "pid 878730 is alive and its start identity matches the one recorded at launch" |

Transcripts: `before-4aac27ae.txt`, `after-repair.txt`.

`attempt.process_pid` is still `None` in flight and that is correct. The worker
thread must never touch the state object, and `state.json` is only written at
checkpoints — which is exactly what a SIGKILL lands between. The identity lives
in its own single-attempt file until the adapter returns.

## The repair, on existing seams

1. **`AdapterRequest.process_started`** — a sibling of the existing
   `cancel_requested` callback, fired the instant the child exists with
   `(pid, start_identity)`, values `adapters/base.py` already computed there.
2. **`store.record_launch`** — one atomic, fsynced file per attempt under
   `<state>/launches/`, written on the worker thread. Cleared on settle, so no
   stale file names a pid the OS may reuse.
3. **`recovery.Liveness`** — `ALIVE` / `GONE` / `UNKNOWN`, with the reason
   returned alongside. Missing identity is `UNKNOWN`; absence must be shown.

## Fail-closed is unchanged

`UNKNOWN` routes to `NEEDS_RECONCILIATION` — never `RESUME_SESSION`, never a
relaunch, never a lease release. A worker whose fate is unestablished must not
get a sibling. `worker_still_alive()` still answers `False` for both `GONE` and
`UNKNOWN`, so no caller can read it as permission to reclaim a task.

If the durable write itself fails, the child is terminated and the error is
raised rather than swallowed: a live worker nobody has recorded is worse than
no worker.

## Other evidence here

- `targeted-suites.txt` — authority, concurrency, provenance, budget and
  taskcontract-authority suites re-run on the repaired tree.
- `multitask-run.json` — a three-task program with a dependency, run to
  `PROGRAM_COMPLETE` with no leftover launch records and a clean reconcile.
