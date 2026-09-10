# AS-STUDIO-A0-001 — authorization boundary

```text
STUDIO_UI != AUTHORITY
ATLAS_DAEMON = AUTHORITATIVE_RUNTIME
UI_STATE = PROJECTION_OF_ATLAS_TRUTH
```

## Actors

| Actor | May call (A0) | Must not |
|---|---|---|
| Local operator (shell) | `atlas-studio snapshot`, `atlas-studio doctor` | Claim mutation authority from Studio output |
| Studio RO slice process | Import `atlas_dag` builders; read GhClient | Write vault; emit coordination events; dispatch; merge |
| Future Studio UI | Consume versioned snapshot/event schemas | Escalate privileges beyond daemon grants |
| Daemon / coordination control plane | Own runtime, leases, Git/GitHub mutation paths | Treat UI liveness as task authority |
| Model provider | Optional later adapters behind daemon | Define Atlas architecture |

## Grants

### RO slice (A0) — **zero writes**

```text
STUDIO_RO_SLICE_GRANTS = NONE
WRITE_CLAIM = DENIED
WRITE_DISPATCH = DENIED
WRITE_EMIT = DENIED
WRITE_MERGE = DENIED
WRITE_VAULT = DENIED
WRITE_IV = DENIED
```

Allowed: build and print `ATLAS_STUDIO_SNAPSHOT_V1`; validate schemas;
report doctor diagnostics; project injected or live read-only panels.

### Observation events

`ATLAS_STUDIO_EVENT_V1` is **read-only observation**, not authority and not
a substitute for `ATLAS_EVENT_V1` coordination bus events.

## Decision rule

If a Studio surface would change world state, it is **out of A0** and must
go through daemon authz (future A2+), never through UI-local privilege.
