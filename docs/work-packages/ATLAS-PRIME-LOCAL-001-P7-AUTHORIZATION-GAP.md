# ATLAS-PRIME-LOCAL-001 — P7 authorization gap (2026-09-14)

Status: NO real-model grant exists for Prime work. This file records the one
minimal authorization that is missing; it grants nothing and invents nothing.
Until every field below is filled by an explicit owner decision, Prime stays
model-free: zero paid calls, zero token import, and the reserved Kimi probe
(0/1, authorization 007) remains untouched — it is not a Prime grant.

## The single missing authorization

| Field | Required content | Current state |
| --- | --- | --- |
| Provider + model | Named provider and exact model id the Prime worker may resolve (must also be added to `child_admission.child_models` for any child admission) | NONE — no provider grant; adapter preflight requires an explicit `provider` + `model`, but no grant authorizes a paid call |
| Credential route | One of the existing allow-listed env routes (`PRIME_API_KEY`, `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`) supplied via the program credential broker for the mission only; no personal config import; no new credential search | Route exists in code (`credentials.py` allow-list); no credential is authorized for Prime missions |
| Task / workspace | Named mission + supervisor-created workspace (worker-writable scope holds only `prime-result.json`) | Mechanism exists; no real mission authorized |
| Total request / token / cost limits | Hard caps for the whole mission, including all children and retries; adapter rejects unbounded autonomous config today | No numbers authorized |
| Deadline | Mission wall-clock deadline inside the supervisor's bounded policy; child seconds bounded per reservation | No deadline authorized |
| Caps incl. children/retries | `max_children` (1–8), `max_child_depth` (default 1), `max_child_seconds`, `max_budget_seconds` (cumulative, never refunded), bounded supervisor retries | Defaults only; no mission-specific authorization |
| Cost basis | Priced basis for the chosen provider/model, or UNKNOWN | UNKNOWN — billing stays UNKNOWN; client-side estimates are labelled estimates |

## Resume-route proof without chat (model-free, isolated test state)

A textual checkpoint is not accepted as proof; the route is pinned by tests
that re-attach from persisted evidence with zero model/chat activity:

- `test_resume_cursor_is_loaded_only_for_the_requested_session` — resume
  reads only the matching session's prior evidence file; foreign cursors are
  ignored.
- `test_command_ids_are_stable_for_reconnect_replay` — deterministic command
  ids make re-attach idempotent instead of replaying mutations.
- `test_child_journal_probe_requires_bound_valid_records` — a relaunched
  probe fails closed on empty, malformed, or unbound journals; only a valid
  journaled lifecycle can be re-bound to a new launch.
- Daemon contract rows in the acceptance matrix: attach/snapshot/cursor PASS
  (upstream contract); uncertain replay still requires reconciliation.

## External waits (no executable work remains on this side)

1. Owner billing recovery on the GitHub account, then CI on the frozen
   candidate head (a rerun of the old run does not test a new head).
2. The single owner-terminal Kimi probe launch (authorization 007) — reserved,
   not part of Prime.
3. Q08 publish approval if this branch is to be pushed; without it the branch
   stays local.
4. Human independent verification for the frozen candidate.
