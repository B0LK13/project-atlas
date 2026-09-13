# AT3-039-F1 — structured turn ingest must not claim live history

Date: 2026-09-13
Base: `b87b4a226f4aa8b2f669edf112aa3476454f754f` / `46d1989b026a2f15920ec5e1c78a106799bd1249`
MERGE_AUTHORIZATION = NOT_GRANTED.

## Finding

On live main, `normalize_turns` / `ingest_provider_turns` accepted
`live_full_history_sync=True` (and `conversation_sync=LIVE`) on a turn
and extracted it as ordinary memory. Export importers and AT3-056
handoff already refuse live claims; the structured ingest path did not.

## Fix

`normalize_turns` fails closed with `LIVE_HISTORY_CLAIMED`. Honest
EXPORT turns still normalize.

Distinct from #879 (`register_provider` adapter registry) and AT3-056
(handoff). Does not grant merge authority.
