# D-049 authentic-estate acceptance plan (planning only)

DIRECTIVE: `D-PROJECT-ATLAS-CLOUD-D049-PREMERGE-066`

This is a protocol for an owner-authorized dogfood run **after**
technical merge readiness. It is not D-042. It is not an estate
inventory. Cloud did not invent an estate and did not scan any remote
or personal tree.

`AUTHENTIC_USER_ESTATE_ACCEPTANCE = NOT_YET_PROVEN`

`D_042_EXECUTION_GATE = CLOSED`

## Goal

Owner authorizes **one** bounded real root. Atlas should:

- discover multiple projects / knowledge where they are present
- require near-zero manual paths
- not scan beyond the authorized root
- not ingest automatically
- show ambiguity honestly

## Preconditions

1. Technical candidate `0509287` / `728f3af` is merge-eligible or already
   on main with identical production trees.
2. Windows IV (Local D-065) has returned.
3. Owner names exactly one authorized root (not `/`, not `$HOME`).
4. No network discovery. No cloud sync. No second root.

## Protocol (owner / Local)

1. Confirm Atlas binary / checkout matches the sealed production pin.
2. `atlas init` a throwaway vault (or an existing dogfood vault the
   owner designates). Discovery must not create canonical projects by
   itself.
3. Run:

   ```bash
   atlas discover --root <OWNER_AUTHORIZED_ROOT> --vault <vault>
   atlas discover review --vault <vault>
   ```

4. Do **not** run `atlas ingest` unless the owner separately authorizes
   ingest of a named candidate. Default dogfood stops at discover/review.
5. `atlas discover connect` only for a candidate the owner explicitly
   accepts, and only after review of match evidence.
6. Record the metrics below. Stop.

## Metrics (fill after the run; do not invent)

| Metric | Meaning |
| --- | --- |
| `PROJECT_DISCOVERY_RECALL` | Owner-known projects under the root that appeared as project candidates |
| `FALSE_PROJECT_MATCH_COUNT` | Candidates the owner rejects as not-a-project |
| `AMBIGUOUS_MATCH_COUNT` | `AMBIGUOUS` / `CONFLICTING` rows requiring a human choice |
| `USER_CORRECTIONS_REQUIRED` | Identity corrections needed before any connect |
| `MANUAL_PATHS_REQUIRED` | Extra paths the owner had to supply beyond `--root` |
| `TIME_TO_DISCOVER_PROJECTS` | Wall time of the single authorized scan |
| `UNSAFE_PATH_ESCAPES` | `security.unsafe_path_escapes_detected` / `allowed` |
| `CROSS_PROJECT_LEAKS` | Knowledge or CONNECTED rows that assigned the wrong project |

## Honesty rules

- Missing projects stay missing (`UNKNOWN` / unmatched). Do not invent.
- Ambiguity stays visible. Do not auto-unify copied UUIDs.
- Obsidian / personal knowledge is review, not ingest.
- A successful technical merge does not satisfy this plan.
- This plan does not authorize D-042 Conversational Capture.
