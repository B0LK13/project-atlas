# Prime Local 001 acceptance matrix

Candidate: `716e5f07` on `feat/prime-local-001`  
Prime source: `5d25a44bd22e1c1fe8321e141cd6c3932563d14c`  
Observed: 2026-09-14

This matrix distinguishes model-free contract evidence from real-provider,
independent-verification, and deployment evidence. `PASS` means the exact
candidate has executable evidence. `PARTIAL` means a bounded sub-contract is
proven but the required end-to-end claim is not. `OPEN` means the required
external or owner gate has not been satisfied.

| Scenario | Status | Evidence / precise boundary | Resume condition |
|---|---|---|---|
| LF/CRLF, Unicode separators, corrupt/oversize frames, ACK semantics | PASS | `tests/unit/test_prime_agent_adapter.py`; model-free smoke 14/14 | None |
| Pinned install, version and imports | PASS | `prime-local-001-runtime-manifest.json`; daemon smoke | None |
| Atlas admission, leases, task/session mapping | PASS | supervisor vertical slice and adapter suite | None |
| Real development with an authorized provider | OPEN | No valid Prime provider grant; no inference executed | Owner grants provider and records bounded usage |
| Native useful Prime children | PARTIAL | Version-pinned host admission broker and TypeScript hook tested; no real-provider child | Authorized real-provider run creates at least two useful children |
| Child budget/resource reconciliation | PARTIAL | Reservation/commit/release journal and slot tests | Reconcile real provider usage across parent/children |
| Continuation after completion/test failure/verdict | PARTIAL | Atlas supervisor continuation and repair fixtures; no real Prime task completed | Re-run against real Prime task |
| Studio/terminal disconnect | PARTIAL | Public daemon resident/reconnect contract proven model-free | Detached real development run and later readback |
| Worker/kernel crash recovery | PARTIAL | Upstream client-owned recovery proven; Atlas credential-bound route not enabled | Credential broker supplies non-persistent mission capability |
| Bridge/daemon/supervisor recovery and replay | PASS | Cursor, generation, snapshot and no-blind-replay tests | None for model-free contract |
| Parent/child slot deadlock prevention | PASS | Supervisor concurrency tests and bounded child broker | None |
| Stop/pause/deadline and no resurrection | PASS | Supervisor control/recovery tests | None |
| Host/secret/network isolation | PARTIAL | Bubblewrap denial probes and fail-closed launcher validation | Reviewed production profile plus adversarial worker run |
| Prompt-injection resistance | PASS | Existing Atlas adversarial suites; Prime worker-specific run remains bounded | Re-run with real worker if provider is granted |
| Independent non-author verification | OPEN | No independent verifier verdict on this candidate | Non-author verifier reviews candidate and artifacts |
| Knowledge canonical receipt/readback | OPEN | Local evidence exists; canonical Vault receipt unavailable | Canonical pipeline receives and reads back artifacts |
| A1/A2 UI authority boundaries | PASS | Existing Atlas control/read projection tests | None |
| Rollback preserving Atlas state | OPEN | Procedure documented; candidate canary not deployed | Authorized canary plus rollback evidence |
| Exact-head CI and deployment gates | OPEN | Not run against a remote/deployed candidate | CI, IV and deployment owner gates complete |

## Candidate evidence

The runtime identity and model-free daemon evidence are in
`prime-local-001-runtime-manifest.json` and
`PRIME-LOCAL-001-DAEMON-SMOKE.md`. The post-fix focused verification for this
candidate passed 67 tests, Ruff, Mypy, and the 14-test network-isolated smoke.
The full repository collection contains 6200 tests; a full run was not
completed and is not represented as green here.

## Owner actions only

1. Authorize a bounded Prime provider or local model endpoint for real-model
   validation; resume by running the real-development and child scenarios.
2. Provide the required independent-verifier and canonical Knowledge/Vault
   gates; resume by attaching their receipts to candidate `716e5f07`.
3. Approve a local canary/deployment route; resume by exercising rollback and
   exact-head CI/deployment checks.
