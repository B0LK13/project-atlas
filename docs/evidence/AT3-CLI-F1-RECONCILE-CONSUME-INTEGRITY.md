# AT3-CLI-F1 — Memory CLI consume-path reconcile integrity

Status: IMPLEMENTED; AWAITING IV. `MERGE_AUTHORIZATION = NOT_GRANTED`.

## Defect

`project_atlas.atlas3.contracts.read_json` returns `None` when a path is
missing **and** when a path exists but is unreadable, non-JSON, or not an
object. The Atlas 3 memory CLI used that helper for
`generated/ops/atlas3/memory/<project>/reconcile.json`.

Reproduced on live `main` `b87b4a226f4aa8b2f669edf112aa3476454f754f`
before any change:

| condition | `atlas memory status` | `atlas memory honesty` |
|---|---|---|
| missing file | exit 0, `reconcile_present: false` | exit 0, empty healthy layers |
| `{not-json` | exit 0, `reconcile_present: false` | exit 0, empty healthy layers |
| JSON array root | exit 0, `reconcile_present: false` | exit 0, empty healthy layers |
| `{"reconciliation":"nope"}` | exit 0, `reconcile_present: true` | raw `AttributeError` on `.get` |

Corruption was therefore indistinguishable from absence on the consume
path. That is the same honesty class as "do not silently filter
corruption into a healthy projection", applied to the CLI.

## Fix

CLI-local loaders (`load_reconcile_artifact`, `load_reconcile_items`):

- missing file → `None` / `[]`
- existing symlink / non-file / invalid JSON / non-object → `RECONCILE_CORRUPT`
- present `reconciliation` that is not an object → `RECONCILE_CORRUPT`
- present `items` that is not a list → `RECONCILE_CORRUPT`

`read_json` itself is unchanged (avoids colliding with #840/#841 and
`load_answer`). `ingestion.py` is untouched.

## Not claimed

- Full exact-object GitHub CI (billing lock = EXTERNAL_BLOCKED)
- That every Atlas 3 compiler now uses this loader
- That mixed valid+non-object *items* are handled here (honesty already
  raises `MALFORMED_ITEM` on that shape)
