# AT3-035-F1 — register_provider must not claim live history sync

Date: 2026-09-13
Base: `b87b4a226f4aa8b2f669edf112aa3476454f754f` / `46d1989b026a2f15920ec5e1c78a106799bd1249`
MERGE_AUTHORIZATION = NOT_GRANTED.

## Finding

On live main, `register_provider` accepted
`live_full_history_sync=True` and overwrote the in-process adapter
registry. `provider_capabilities` then reported a live history API that
does not exist (EXTERNAL_BLOCKED).

## Fix

`register_provider` fails closed with `LIVE_HISTORY_CLAIMED` and leaves
the registry unchanged. Default adapters remain `live_full_history_sync=False`.

Distinct from fixture-export live-claim refusals (ChatGPT/Claude/Gemini/Cursor/Codex)
and from AT3-056 handoff turn claims.
Does not grant merge authority.
