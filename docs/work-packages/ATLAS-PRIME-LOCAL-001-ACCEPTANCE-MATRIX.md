# ATLAS-PRIME-LOCAL-001 acceptance matrix

Candidate date: 2026-09-14. Candidate commit:
`2bb84afb` on branch `feat/prime-local-001`. Prime source pin:
`5d25a44bd22e1c1fe8321e141cd6c3932563d14c`.

This matrix separates observed evidence from open gates. A fixture, install
smoke, or agent self-report never upgrades an open real-model or governance
criterion.

| Scenario | Current state | Evidence / exact boundary |
| --- | --- | --- |
| LF/CRLF, Unicode separators, malformed and oversized frames | PASS | `tests/unit/test_prime_agent_adapter.py`; strict parser contract |
| ACK is not treated as result | PASS | adapter waits for `agent_end`; focused adapter tests |
| Pinned runtime install/build/version | PASS | runtime manifest and daemon smoke; `npm ci`, build, version `0.9.4` |
| Guarded model-free upstream contract smoke | PASS | `scripts/prime-local-001-model-free-smoke.sh`; network-isolated run, 2 files, 14/14 tests, 6.36 s against the pinned runtime |
| Real development with an authorized provider | OPEN | no Prime provider grant; no model call made |
| Real native Prime children through Atlas admission | PARTIAL | version-pinned Unix-socket hook, mission/task/attempt/parent + role/scope binding, bounded reservation, fsync journal, commit/release registry, and fail-closed tests exist; real provider child execution remains open |
| Multiple independent Atlas agent identities | PASS (control-plane) | supervisor vertical-slice plus independent verifier identity; fixture only |
| Write-conflict serialization/refusal | PASS (Atlas) | existing supervisor overlap/lease tests; Prime adds no second scheduler |
| Parent/child slot accounting | PARTIAL | broker enforces bounded child slots, child deadline and cumulative reserved budget units; parent waits for child release within the attempt deadline; public daemon usage snapshots are recorded when available, while cumulative provider usage reconciliation remains open |
| Event-driven continuation and repair | PARTIAL (Atlas control loop) | existing supervisor cycle/retry/acceptance tests; Prime-specific real repair open |
| Studio/terminal disconnect | PARTIAL (daemon contract only) | resident daemon smoke; real detached Prime development and later readback remain open |
| Daemon restart attach/snapshot/cursor | PASS (upstream contract) | isolated smoke; adapter still requires reconciliation before uncertain replay |
| Worker/kernel crash recovery | PARTIAL | client-owned upstream attach works; child admission lifecycle is journaled before reserve effects; Atlas provider-bound recovery is not integrated |
| Replay generations and duplicate events | PASS (adapter contract) | cursor monotonicity tests and daemon smoke |
| Budget/deadline/stop behavior | PASS (Atlas controls) | existing supervisor limits/cancellation tests; Prime records public token snapshots when available and keeps billing UNKNOWN unless only a client estimate is reported |
| Prime autonomous budget configuration | PASS (fail-closed contract) | adapter rejects omitted/unbounded autonomous limits and timeouts beyond the Atlas task deadline; bounded config is sent in the documented daemon session config |
| Secret and host isolation | PARTIAL | exact bwrap argv denies host SSH, other Atlas/cache paths, and loopback Ollama access; preflight rejects pass-through wrappers and broad `/`, `/home`, `/root`, and writable `/etc` mounts; complete reviewed production profile and adversarial Prime worker run remain open |
| Independent non-author verification | PASS (fixture control-plane) | verifier agent differs from implementer; required human IV remains open |
| Knowledge canonical receipt/readback | OPEN | Prime evidence binding exists; Knowledge Plane receipt pipeline not connected |
| A1 read-only / A2 mutation routing | PASS (reused Atlas route) | no new Studio mutation path added; full UI reconnect proof open |
| Rollback without mission loss | OPEN | candidate rollback instructions exist; deployment canary/rollback gate not run |
| Exact-head CI and deployment gates | OPEN | not run or authorized from this candidate branch |

The current proven state is therefore a model-free, locally tested Atlas
adapter slice—not full product acceptance. Post-fix verification for commit
`2bb84afb` passed the Prime-focused adapter/supervisor tests, Ruff, Mypy, and
the 14-test network-isolated Prime smoke. The full repository collection is
6200 tests; no incomplete full-suite run is represented as green.
