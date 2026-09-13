# AT3-012-F1 — Estate-nodes declared path integrity

Status: IMPLEMENTED; AWAITING IV. `MERGE_AUTHORIZATION = NOT_GRANTED`.

## Defect

`compile_estate_nodes` treated any path that failed `Path.is_file()` as
missing (`status=UNKNOWN`, `reason=NO_DECLARED_ESTATE_NODES`).

Reproduced on live `main` `b87b4a226f4aa8b2f669edf112aa3476454f754f`
before any change:

| condition | result |
|---|---|
| missing `declared.json` | UNKNOWN / `NO_DECLARED_ESTATE_NODES` |
| directory named `declared.json` | UNKNOWN / `NO_DECLARED_ESTATE_NODES` |
| symlink to a regular JSON file listing `leaked-db` | `status=derived`, service composed as harbor-api |

`Path.is_file()` follows symlinks. A present link was therefore a healthy
projection, including services that never lived under the requested
project. A present directory was indistinguishable from absence.

That is the same honesty class as "do not silently filter corruption into
a healthy projection", applied to the AT3-012 consume path.

## Fix

`_load_declared`:

- missing path → `None` → UNKNOWN
- existing symlink / non-file → `ESTATE_NODES_CORRUPT`
- existing unreadable / non-object JSON → `ESTATE_NODES_CORRUPT` (unchanged)

Regular files still derive. `ingestion.py` is untouched. No new CLI.

## Not claimed

- Full exact-object GitHub CI (billing lock = EXTERNAL_BLOCKED)
- That every Atlas 3 declared-graph loader now uses this path check
- Row-level `project_id` bind on service/environment items (out of scope)
- Authentic D:\ estate discovery (LOCAL_WINDOWS)
