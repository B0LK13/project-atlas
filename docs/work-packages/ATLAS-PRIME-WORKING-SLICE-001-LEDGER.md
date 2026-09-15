# ATLAS-PRIME-WORKING-SLICE-001 — mission ledger (operator record)

Authoritative mission text: `docs/work-packages/ATLAS-PRIME-WORKING-SLICE-001.md`.
This ledger registers admission, absolute expiry, limits, the taskgraph and
cumulative usage. Updated as the mission progresses; routine progress lives
here, not in chat.

## Admission and absolute expiry

- Admission (mission effective): **2026-09-15T07:54:25Z** (owner issue via
  trusted operator route; goal started).
- **Absolute expiry: 2026-09-15T11:54:25Z** — hard stop, no automatic
  extension. Runtime budget mirrors this (4 h).
- Operator session: trusted local operator (Kimi), host Probook-450, user
  `gebruiker`. Canonical registry:
  `…/supervisor-autonomous-009/registry/.atlas/orchestration/program/agents.json`.

## Limits snapshot (registered before any dispatch)

| Limit | Value | State |
| --- | --- | --- |
| Wall clock | 4 h from admission → 11:54:25Z | running |
| Implementation codingworkers | 1 | not yet launched |
| Prime parent / direct children | 1 parent, ≤ 1 direct child | not yet launched |
| Reviewer launches | ≤ 2 (2nd only after concrete correction) | 0 used |
| Implementation tokens | ≤ 500 k in/out | 0 used |
| Review tokens | ≤ 100 k in/out, reserved before coding | reserved |
| Prime execution | ≤ 16 inference requests, ≤ 80 k in/out, ≤ 12 k output (incl. children/retries) | 0 used |
| Host RAM | ≥ 2 GiB available; 6 GiB combined pilot memory cap | 5.3 GiB available at admission ✓ |
| Model/route | installed `qwen3:1.7b-q4_K_M` (id `8f68893c685c`) via existing local relay; authenticated Codex route for coding/review | present ✓ |
| Spend | none: no purchases, overage, new providers, credential imports, downloads | — |

## Prior usage preserved (NOT this mission's budget; never reset)

- Diagnostics attempts (supervisor): 88fd8f0e ({}), 59cab7d5 (input
  2,477,957 / output 18,803), 519a148f (input 488,204 / output 1,229) —
  historical, separate receipts, intact.
- Interactive lane self-reported: 181,597 + 132,859 tokens (other lane's own
  session; reported-not-verified).
- Qwen pilot budgets remain separate and untouched by this mission.

## Taskgraph (implementation → local validation → review)

1. **Setup + kernel repair (model-free)**: mission-owned workspace from base
   `03bc4459` + certified worker delta (pins in handoff §8.2/§9); mission-owned
   kernel env with `prime-agent-runtime` (callable `rlm.spawn`,
   `rlm.create_session`, `rlm.host_request` + harness CRUD) replacing the
   failed `/tmp/…/kernel-venv`; preflight: interpreter/runtime validation,
   real launcher/sandbox kernel start, harmless operator cell + result,
   cleanup + boundary check, focused regression test. Admission: this owner
   mission §2.
2. **Local validation (model-free)**: review-route readiness — reuse
   verification-route-001 + ATLAS-REVIEW-SCHEMA-REPAIR-001 state; offline
   schema/contract checks; confirm supervisor can admit the review phase on
   the reserved allocation. Both preflight and review-contract checks green
   before any inference. Admission: mission §3.
3. **Prime pilot (the only inference-bearing phase)**: bounded coding task
   reserved for Prime — expose actionable kernel-readiness failures in the A1
   status projection + regression test (or one evidenced missing regression in
   that feature if the behavior already exists). Requires model-originated
   structured ipython call, real-kernel execution, genuine patch, tests,
   supervisor-collected result. ≤ 1 read-only child allowed. Admission:
   mission §4.
4. **Review**: freeze exact delta/runtime/config/schema/criteria; supervisor
   dispatches non-author reviewer (≤ 2 launches); verdict published via
   trusted route; receipt + subject binding read back. Admission: mission §5.

Phases start only via supported admission; no phase is dispatched while a
predecessor check is red.

## Coordination with the other lane (binding)

- Other lane active areas (do not disturb, do not reset): worktree WIP
  (`verification.py`, `test_orchestration_program_verification.py`, edits in
  `acceptance.py`, `cli.py`, `models.py`, `supervisor.py`, `prime_agent.py`,
  `control.py`), and `…/prime-local-001/verification-route-001/` including
  states v1–v6, `schema-preflight/`, and receipt `eaa3a36e…`.
- This lane's planned write areas (mission-owned, isolated): new worktree
  `…/prime-local-001/working-slice-001/` (branch `feat/prime-working-slice-001`,
  base `03bc4459` + certified delta); mission env `…/prime-local-001/working-slice-001/env/`;
  new test file `tests/unit/test_prime_kernel_preflight.py`; A1 projection
  change in `control.py` ONLY inside the mission worktree (Prime's task).
- Shared-file rule: no edits in the other lane's uncommitted files; if a
  shared file must change, change it in the mission worktree and record the
  divergence here.

## Evidence locations

- Mission program/state (to be created under):
  `…/prime-local-001/working-slice-001/state/…` + registry assignment.
- Kernel env + preflight artifacts: `…/prime-local-001/working-slice-001/env/`.
- Repair target record: capability-1 transcript pin `00a458ab…` (handoff §8.5).
- Historical diagnostics receipts: unchanged (handoff §7–§9).
