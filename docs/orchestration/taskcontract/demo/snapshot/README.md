# Snapshot: what the demonstration was run against

A **record**, not a sandbox. The demonstration reads the live repository
read-only; these files pin the exact backlog text, the exact human-authored
acceptance contract, and the exact parsed item the run observed, so the
evidence stays checkable after `docs/backlog.md` moves on.

`INT-013.as-read.json` carries the item's `item_digest`. The contract built
from it pins that digest, and `atlas task validate --project <repo>` reports
`freshness.source_changed` as an ERROR the moment the backlog line is edited.

The original item and its ownership are unmodified. Nothing here approves
INT-013, clears its `EXTERNAL_BLOCKED` state, or authorizes a launch.
