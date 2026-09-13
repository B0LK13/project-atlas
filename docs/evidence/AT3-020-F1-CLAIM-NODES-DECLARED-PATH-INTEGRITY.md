# AT3-020-F1 — Claim-nodes declared path integrity

Status: IMPLEMENTED; AWAITING IV. `MERGE_AUTHORIZATION = NOT_GRANTED`.

## Defect

`compile_claim_nodes` treated any path that failed `Path.is_file()` as
missing (`status=UNKNOWN`, `reason=NO_DECLARED_CLAIM_NODES`).

Reproduced on live `main` `b87b4a226f4aa8b2f669edf112aa3476454f754f`
before any change:

| condition | result |
|---|---|
| missing `declared.json` | UNKNOWN / `NO_DECLARED_CLAIM_NODES` |
| directory named `declared.json` | UNKNOWN / `NO_DECLARED_CLAIM_NODES` |
| symlink to a regular JSON file listing decision `DEC-LEAK` | `status=derived`, node composed as harbor-api |

`Path.is_file()` follows symlinks. A present link was therefore a healthy
projection, including a foreign decision node. That is an owner-decision
leak, not just an inventory leak.

## Fix

`_load_declared`:

- missing path → `None` → UNKNOWN
- existing symlink / non-file → `CLAIM_NODES_CORRUPT`
- existing unreadable / non-object JSON → `CLAIM_NODES_CORRUPT` (unchanged)

Regular files still derive. `ingestion.py` is untouched. No new CLI.
Does not modify `#862` / `estate_nodes.py`.

## Not claimed

- Full exact-object GitHub CI (billing lock = EXTERNAL_BLOCKED)
- That every remaining Atlas 3 declared loader now uses this path check
- Authentic D:\ estate discovery (LOCAL_WINDOWS)
