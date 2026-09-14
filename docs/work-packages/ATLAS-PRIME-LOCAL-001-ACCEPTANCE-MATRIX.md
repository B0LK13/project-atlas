# ATLAS-PRIME-LOCAL-001 acceptance matrix

Candidate date: 2026-09-14. Candidate commit:
`913bc791` on branch `feat/prime-local-001`. Prime source pin:
`5d25a44bd22e1c1fe8321e141cd6c3932563d14c`.

This matrix separates observed evidence from open gates. A fixture, install
smoke, or agent self-report never upgrades an open real-model or governance
criterion.

## Pin registry (2026-09-14)

Registered separately; none of these identifiers are interchangeable:

- Local candidate (FROZEN for the gap-closure round): branch
  `feat/prime-local-001`, HEAD
  `913bc791637acc9afecb8a2429f5ba4e8f2dc709`, tree
  `f34a1684fc005ca2aed5ebecd03d29bc98cfe3d4`, closed by commits
  `3f3ee03b..913bc791`. Any later commit is outside this freeze and
  reopens impact analysis. Earlier in the day the line moved per
  verification pass; the freeze above is the one this matrix describes.
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
| Real native Prime children through Atlas admission | PARTIAL | host route (`rlm.run` host_request → `runRlmChild` → reserve/commit/release hook) is patched and broker-backed; model-free host-route tests exist (TS harness, faux provider: deny-before-model-call, admit with fencing, commit-failure release, silent-broker fail-closed, inert-without-env; 5/5) and the broker pins model allow-list, recursion depth, fencing, dedup, parent binding; the provider grant and real provider child execution remain open |
| Multiple independent Atlas agent identities | PASS (control-plane) | supervisor vertical-slice plus independent verifier identity; fixture only |
| Write-conflict serialization/refusal | PASS (Atlas) | existing supervisor overlap/lease tests; Prime adds no second scheduler |
| Parent/child slot accounting | PASS (broker contract) | bounded slots with a two-thread one-slot race test, immediate denial while the single slot is held (no deadlock), request dedup, cumulative never-refunded budget, fencing; cumulative provider usage reconciliation remains open |
| Event-driven continuation and repair | PARTIAL (Atlas control loop) | existing supervisor cycle/retry/acceptance tests; Prime-specific real repair open |
| Studio/terminal disconnect | PARTIAL (daemon contract + reconnect-stable projection) | `_runtime_metadata` projection proven reconnect-stable for Prime metadata (two reads identical, viewer close touches nothing, state mtimes unchanged); real detached Prime development and later readback remain open |
| Daemon restart attach/snapshot/cursor | PASS (upstream contract) | isolated smoke; adapter still requires reconciliation before uncertain replay |
| Worker/kernel crash recovery | PARTIAL | client-owned upstream attach works; child admission lifecycle is journaled before reserve effects; Atlas provider-bound recovery is not integrated |
| Replay generations and duplicate events | PASS (adapter contract) | cursor monotonicity tests and daemon smoke |
| Budget/deadline/stop behavior | PASS (Atlas controls) | existing supervisor limits/cancellation tests; Prime records public token snapshots when available and keeps billing UNKNOWN unless only a client estimate is reported |
| Prime autonomous budget configuration | PASS (fail-closed contract) | adapter rejects omitted/unbounded autonomous limits and timeouts beyond the Atlas task deadline; bounded config is sent in the documented daemon session config |
| Secret and host isolation | PARTIAL (contract + live probe) | `scripts/prime-local-001-sandbox-probe.sh` denies host SSH canary, taskstore/policy paths, loopback, and out-of-scope writes (4/4) inside the bwrap scope; 13 validator tests pin `/`, `/home`, `/root`, writable `/etc`, symlink-resolution, and the `--bind=<src>` attached-form evasion fix; complete reviewed production profile and adversarial Prime worker run remain open |
| Independent non-author verification | PARTIAL (round IV PASS on record) | fresh non-author review of the frozen round `3f3ee03b^..cc25b838` re-ran the full battery itself: verdict PASS, 0 blockers (`docs/orchestration/program/evidence/PRIME-LOCAL-001-IV-REVIEW.md`); supervisor accepted the exact verdict into program evidence; prior-program IV covers `b3273231` only; the required human IV remains open |
| Knowledge canonical receipt/readback | OPEN (local capture bound) | attempt completion appends an evidence-grade capture row (`sync_state: pending_local_evidence_not_canonical`, fsync'd 0600 JSONL inside evidence_dir only); Knowledge Plane receipt pipeline not connected; canonical receipt stays OPEN |
| A1 read-only / A2 mutation routing | PASS (reused Atlas route) | no new Studio mutation path added; reconnect-stable read projection proven; full UI reconnect proof open |
| Rollback without mission loss | PARTIAL | cancel-after-certification preserves journal, metadata, and capture evidence byte-intact (test-bound); the runbook's deployment canary/rollback gate is not run; candidate rollback instructions exist |
| Exact-head CI and deployment gates | OPEN | branch unpublished; GitHub CI billing-blocked so no run exists for any commit here; rerunning the old `95594566`-run would not test any head of this branch; CI must run on the frozen candidate head after billing recovery |

The current proven state is therefore a model-free, locally tested Atlas
adapter slice—not full product acceptance. Verification for the frozen
commit `913bc791` (clean-tree worktree at that exact head): 266 tests passed
across the 18 Prime + orchestration-program files, Ruff clean, Mypy strict
clean (458 files), the 14-test network-isolated Prime smoke passed against
the pinned runtime with the regenerated admission patch, the sandbox probe
denied 4/4, and the runtime-side admission regression passed 5/5 on the
faux provider. The full repository collection is 6200 tests; no incomplete
full-suite run is represented as green.
