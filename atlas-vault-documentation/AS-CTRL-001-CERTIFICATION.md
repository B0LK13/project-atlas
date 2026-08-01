# AS-CTRL-001 Certification

## Final disposition

AS-CTRL-001 CERTIFIED — managed agents are launched through a verified control plane that binds them to the certified atlas-governed-work skill, the correct project and logical Vault, automatically captures governed session context, enforces the complete documentation lifecycle, supports exact-once offline recovery, safely coordinates concurrent agents and rejects completion or repository integration without a valid Atlas session receipt.

## Scope

This certification covers the generic managed adapter, the certified `atlas-governed-work` dependency, same-Vault concurrent sessions, offline spool handoff, postflight enforcement, environment binding, protected-path checks, and the repository receipt gate. AS-SKILL-001 evidence is reused for skill-level acknowledgement, readiness promotion, and adversarial skill/Vault probes.

## Managed launcher evidence

Evidence: `evidence/AS-CTRL-001-managed-launch.json`.

The production command surface was exercised as:

```text
python atlas-vault-documentation/scripts/atlas_agent.py run --project-root <fixture> --vault-root <vault> --agent generic --task-id AS-CTRL-001-CERT-N -- <child>
```

Two concurrent sessions completed against the same logical Vault. Each had a unique agent/session/event identity, automatic `session-start`, three child events, complete capture/normalize/verify/route counts, matching skill hash, and a valid receipt. The child process also verified all injected governance environment variables before documenting work.

The launcher performs bootstrap, readiness authorization, acknowledgement, capability checking, automatic session-start, child execution, and postflight. Missing validation/completion and pending-spool states remain rejected by the receipt gate; the focused tests cover these negative paths.

## Concurrency recertification note

The original managed-launch test failure is preserved in
`evidence/AS-CTRL-001-concurrency-reconciliation.json`. It was a genuine
shared-directory ordering race: verification observed another session's raw,
normalized, or temporary failure file during its provider side-effect
snapshot. The first normalization-only lock was insufficient because capture
could still occur during verification. The final fix widens the per-Vault
cross-process lock over capture through normalization and routing.

After the final fix, the focused concurrency test passed 10 consecutive
isolated executions, and the complete 146-test control-plane suite passed.
No persistent processes, locks, temporary harness directories, or pending
spool events remained.

## Repository enforcement

`atlas_agent.py repository-gate` rejects meaningful changes without a receipt, wrong-project or stale-skill receipts, and direct changes under protected Atlas paths. The manual-dispatch workflow `.github/workflows/atlas-documentation-gate.yml` exposes this gate to CI.

| Probe | Result |
|---|---|
| source change without receipt | rejected, exit 4 |
| protected Atlas path change | rejected, exit 4 |
| valid receipt with validation/completion evidence | accepted by gate contract |

## Validation results

```text
./.venv/bin/python -m pytest atlas-vault-documentation/tests/test_agent_control.py -q   PASS (12)
./.venv/bin/python -m pytest atlas-vault-documentation/tests -q                         PASS (146)
./.venv/bin/python -m pytest -q                                                          PASS (54)
./.venv/bin/python -m mypy src atlas-vault-documentation                              PASS (112 files)
./.venv/bin/python -m ruff check .                                                      PASS
./.venv/bin/python -m compileall -q src atlas-vault-documentation                      PASS
./.venv/bin/python atlas-vault-documentation/scripts/atlas_agent.py verify-instructions --json PASS
./.venv/bin/python atlas-vault-documentation/scripts/run_ctrl_certification.py         PASS
```

AS-SKILL-001 remains the authoritative source for skill package validation, receipt-bound readiness promotion, offline exact-once synchronization, and negative skill-context gates. Its certified receipt records 10 focused, 143 subproject, and 54 parent tests; the current control-plane regression is 12, 146, and 54 respectively.

## Acceptance matrix

| Requirement | Status | Evidence |
|---|---|---|
| AS-041 certified skill dependency | PASS | AS-SKILL-001 receipt; preflight checks |
| AS-042 generated bootstrap distribution | PASS | adapter verification; drift test |
| AS-043 logical Vault identity/UUID | PASS | preflight tests; AS-SKILL negative gates |
| AS-044 managed launcher/preflight | PASS | managed-launch evidence and test |
| AS-045 unique governed sessions | PASS | concurrent managed-launch evidence |
| AS-046 automatic mandatory lifecycle | PASS | session-start evidence; focused suite |
| AS-047 managed offline synchronization | PASS | AS-SKILL certified exact-once spool evidence |
| AS-048 strict postflight receipt enforcement | PASS | missing validation/completion tests |
| AS-049 repository/CI documentation gates | PASS | repository-gate probes and workflow |
| AS-050 concurrent same-Vault operation | PASS | two-session evidence; router concurrency tests |

## Compatibility and residual risk

The generic CLI adapter is promoted and certified. Other adapters remain subject to their own readiness records. The repository gate is exposed as a manual-dispatch CI workflow because this workspace does not provide a live pull-request change range or external receipt service. The certified same-Vault lock applies to the managed `agent_control.event_client.document()` path; direct invocation of `capture_event.py` or `normalize_event.py` outside that path is not covered by the concurrency lock and remains an operational risk. Distributed locking, remote orchestration, and cross-user authorization remain deferred.

## Certification receipt

`AS-CTRL-001-CERTIFICATION-RECEIPT.yaml` is the machine-readable final receipt.
