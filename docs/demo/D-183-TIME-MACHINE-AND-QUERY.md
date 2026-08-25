# D-183 — Time Machine + query operator story (D-177 estate)

`DEMO_FIXTURE != AUTHENTIC_PILOT`. This is operator story, not production
Time Machine or query-semantic change.

## Time Machine

`fixtures/demo/estate/project-a` now declares document valid-time on the
hero datastore subject (`doc:harbor-database` / `deployment`):

| Instant | Source | Value |
|---|---|---|
| T1 `2024-01-15` | `ARCHITECTURE.md` | PostgreSQL 15 |
| T2 `2024-08-20` | `src/RUNTIME.md` | PostgreSQL 16 |

After `init → discover → ingest → build-indexes → build-portfolio`:

```
atlas kdiff --vault <vault> --project project-a --as-of 2024-03-01 --json
atlas kdiff --vault <vault> --project project-a --as-of 2024-10-01 --json
atlas kdiff --vault <vault> --project project-a --from 2024-03-01 --to 2024-10-01 --json
```

Expect a `value_changed` cell for `doc:harbor-database` / `deployment`.
Harbor golden (`tests/fixtures/demo/estate/harbor-api`) remains the
implementation acceptance fixture (`runtime` field, PostgreSQL 15→16).

Zero catalog windows on the previous D-177 estate was fixture deficiency
(no `timestamp:`), not a Time Machine implementation failure.

## Query

Do not invent an authoritative winner. Unresolved PostgreSQL 15 vs 16
must stay unresolved until a human accept.

Honest no-winner:

```
atlas query --vault <vault> --project project-a --kind authoritative --list
```

Expect `[]`. `status=not_found` / `value=null` on the contested
deployment field is correct.

Grounded evidence (not authority) is Ask Atlas 2:

```
atlas ask2 --vault <vault> --project project-a --question "What database does project-a use?" --json
```

Contest is visible; `ANSWER` stays null when unresolved. A true
authoritative query winner requires an accept into
`state/authoritative-state/`, which this fixture does not mint.
