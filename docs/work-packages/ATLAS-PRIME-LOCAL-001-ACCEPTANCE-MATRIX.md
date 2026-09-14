# ATLAS-PRIME-LOCAL-001 acceptance matrix

Candidate date: 2026-09-14. Candidate commit:
`eddb4634` on branch `feat/prime-local-001`. Prime source pin:
`5d25a44bd22e1c1fe8321e141cd6c3932563d14c`.

This matrix separates observed evidence from open gates. A fixture, install
smoke, or agent self-report never upgrades an open real-model or governance
criterion.

## Pin registry (2026-09-14)

Registered separately; none of these identifiers are interchangeable:

- Local candidate: branch `feat/prime-local-001`, HEAD `af3e4691`,
  tree `e6f3ce4d7dcd3b794c38b10500b3d244142504cc`. This line moves with
  every verification pass; the candidate line above is rebound each time.
- Local runtime (host-patch development checkout):
  `prime-local-001-runtime` at upstream pin
  `5d25a44bd22e1c1fe8321e141cd6c3932563d14c` plus the uncommitted
  version-pinned hook (patch id
  `prime-agent-5d25a44-atlas-child-admission-v1`, sha256 pinned in
  `prime_agent.py` and verified by adapter preflight).
- Prior-program runtime (model-free line only): `runtime-008` Python
  supervisor checkout pinned at `95594566`. Its P0-P6 evidence stays on
  that pin and is not silently re-run against this branch.
- Prior-program candidates: `b327323179b5` (independent review verdict
  PASS, evidence P6) and `6ded02a6` (P5-rest projection stacked on it,
  self-sealed by its own tests only). That IV covers `b3273231` alone;
  it does not cover `6ded02a6`, and it does not cover this branch.
- Remote: origin `B0LK13/project-atlas` HEAD/main `b87b4a226f`; the
  branch `feat/prime-local-001` has no remote ref (unpublished).
  GitHub CI is billing-blocked; no CI run exists for any commit here.

| Scenario | Current state | Evidence / exact boundary |
| --- | --- | --- |
| LF/CRLF, Unicode separators, malformed and oversized frames | PASS | `tests/unit/test_prime_agent_adapter.py`; strict parser contract |
| ACK is not treated as result | PASS | adapter waits for `agent_end`; focused adapter tests |
| Pinned runtime install/build/version | PASS | runtime manifest and daemon smoke; `npm ci`, build, version `0.9.4` |
| Guarded model-free upstream contract smoke | PASS | `scripts/prime-local-001-model-free-smoke.sh`; network-isolated run, 2 files, 14/14 tests, 6.36 s against the pinned runtime |
| Real development with an authorized provider | OPEN | no Prime provider grant; no model call made |
| Task-level admission with native recursion disabled | PASS (broker contract) | broker tests pin mission/task/attempt/parent + role/scope binding, bounded reservation, fsync journal, commit/release registry; native recursion stays DISABLED in shipped configs — this row is not a native child-admission claim |
| Real native Prime children through Atlas admission | PARTIAL | host route (`rlm.run` host_request → `runRlmChild` → reserve/commit/release hook) is patched and broker-backed; the model-free host-route tests and the provider grant are still missing; broker fixture tests are not runtime enforcement; real provider child execution remains open |
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
| Independent non-author verification | PARTIAL | verifier agent differs from implementer (fixture control-plane PASS); prior-program IV verdict PASS covers `b3273231` only — it does not cover `6ded02a6` and does not cover this branch; a fresh non-author review of this line remains required, and the required human IV remains open |
| Knowledge canonical receipt/readback | OPEN | Prime evidence binding exists; Knowledge Plane receipt pipeline not connected |
| A1 read-only / A2 mutation routing | PASS (reused Atlas route) | no new Studio mutation path added; full UI reconnect proof open |
| Rollback without mission loss | OPEN | candidate rollback instructions exist; deployment canary/rollback gate not run |
| Exact-head CI and deployment gates | OPEN | branch unpublished; GitHub CI billing-blocked so no run exists for any commit here; rerunning the old `95594566`-run would not test any head of this branch; CI must run on the frozen candidate head after billing recovery |

The current proven state is therefore a model-free, locally tested Atlas
adapter slice—not full product acceptance. Post-fix verification for commit
`eddb4634` passed the Prime-focused adapter/supervisor tests, Ruff, Mypy, and
the 14-test network-isolated Prime smoke. The full repository collection is
6200 tests; no incomplete full-suite run is represented as green.
