# ATLAS-PRIME-LOCAL-001 Capability Map

Status: inventory captured on 2026-09-14 from `feat/prime-local-001`.

## Pins and current truth

| Item | Current fact | Evidence / boundary |
| --- | --- | --- |
| Atlas base | `250eb1cb9c088712c1dde33554845e51c4b45e18` | clean candidate worktree; no Prime files present |
| Prime source | `5d25a44bd22e1c1fe8321e141cd6c3932563d14c` | detached checkout at `/tmp/prime-agent-source-001` |
| Prime package | source workspace `@earendil-works/pi-coding-agent`, version `0.9.4` | inherited source identifier; not treated as public distribution identity |
| Prime lock hash | `409e354743d7e56af2bbc6276675e0dfc3699fb29e6247a2a352692963052f3f` | `/tmp/prime-agent-source-001/package-lock.json` |
| Node floor | `22.8.0` | upstream development/quickstart contract; observed host `v22.23.2` |
| Python kernel | explicit `PRIME_AGENT_KERNEL_PYTHON` required for the chosen environment | upstream quickstart; no assumption that system Python is sufficient |
| RPC framing | LF JSONL; CRLF accepted after stripping one trailing CR | upstream RPC contract |
| RPC ACK | accepted/queued only; not execution success | upstream RPC contract |
| resident semantics | public daemon route creates daemon-owned resident sessions; adapter stores attach snapshots and monotonic generation cursors, while restart replay reconciliation remains open | upstream daemon/RPC contracts, adapter contract tests, and `evidence/PRIME-LOCAL-001-DAEMON-SMOKE.md` |
| native child admission | version-pinned Prime hook calls an Atlas-owned Unix-socket broker before reserve/commit; broker binds mission/task/attempt/parent and bounds child slots | `patches/prime-agent-5d25a44-atlas-child-admission-v1.patch`, broker contract test; real provider execution and cumulative ledger reconciliation remain open |
| Atlas state owner | existing `program` supervisor | `src/project_atlas/orchestration/program/` |
| Prime integration state | absent at inventory time | `rg` over source/docs/tests found no Prime adapter or runtime enum |
| named runtime reports | `runtime-008`, `supervisor-autonomous-009`, `probe-004`, `q10-accept` not present as current repo state | old venv/binary matches excluded |
| host/provider inventory | 8 logical CPUs, 10 GiB RAM, Intel integrated graphics; loopback Ollama reachable with an empty catalog; no Prime grant identified | `evidence/PRIME-LOCAL-001-RESOURCE-PROVIDER-INVENTORY.md`; no provider call made |

## Reuse map

| Capability | Existing Atlas route | Prime slice integration point | Required proof |
| --- | --- | --- | --- |
| task DAG and dependencies | `program.models`, `program.supervisor` | none; Prime receives one admitted task | supervisor acceptance/concurrency tests |
| admission and ownership | enrollment, leases, profiles, supervisor dispatch | `PrimeExecutorAdapter.preflight/run` receives already-bound request | denial and lease tests |
| durable attempts | `program.store`, checkpoints, recovery | Prime session/active-session IDs and command identity in attempt evidence | manifest/recovery tests |
| execution adapter | `adapters.base.RuntimeAdapter` | new `prime_agent.py` adapter | protocol, ACK, result, lifecycle tests, supervisor vertical-slice test |
| runtime inventory | `program.runtimes` | add explicit Prime support row with honest tier | model-free probe and support matrix |
| provider policy | `program.profiles`, `credentials` | environment allow-list only; no secret persistence | credential and local-only tests |
| acceptance/verification | `program.acceptance`, supervisor verifier path | worker report is evidence only | non-author acceptance tests |
| knowledge/context | existing task-context and event routes | add Prime bindings as evidence, not canonical memory | receipt/readback tests |
| Studio | existing Mission Control read projection | expose existing state only; no new mutation path | A1/A2 and reconnect tests |

## First vertical slice

The first slice is a real Atlas program task using a Prime adapter against a
disposable workspace. Its objective is deliberately small and objectively
testable: add a deterministic, unit-tested Prime RPC frame parser/adapter
contract to Atlas without changing the Prime wire protocol. The task is
accepted only from the workspace diff and its declared tests; a prompt ACK or
Prime self-report is never acceptance.

The slice is model-free until a valid provider grant is present. A later
real-provider run must produce a useful patch for the same task and is reported
separately from installation and protocol smoke evidence.

## Remaining child boundary

Prime recursive child spawning is not enabled by prompting convention. The
version-pinned compatibility hook now forces each native spawn through the
Atlas broker, which binds mission/task/attempt/parent and reserves bounded
child capacity. Real provider execution, role-specific child scopes, and
cumulative ledger reconciliation still require separate validation.
