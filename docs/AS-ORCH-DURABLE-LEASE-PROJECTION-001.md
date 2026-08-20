# AS-ORCH-DURABLE-LEASE-PROJECTION-001

Durable **read projection** of primary-governor leases.

This package does **not** create a second authority model.

```
PRIMARY_GOVERNOR_REMAINS_AUTHORITY = YES
DURABLE_PROJECTION_IS_AUTHORITY = NO
LEASE_GRANT_SOURCE = PRIMARY_GOVERNOR
LEASE_ACK_SOURCE = PRIMARY_GOVERNOR
OWNER_AUTHORITY_NOT_EXPANDED = YES
MERGE_AUTHORIZATION = NOT_GRANTED
```

## Why

`AutonomousGovernor._leases` is process-local. Subordinates that cannot inspect
another process's memory must classify:

```
CROSS_PROCESS_LEASE_VISIBILITY = UNAVAILABLE
```

That is a resilience gap, not a global autonomy stop. This package projects
grant/release so restart, audit, ack, and stale-lease rejection can be observed
without treating the file as a grant source.

## Store

Optional `lease_projection_store` on `AutonomousGovernor`. Default `None` keeps
existing in-memory-only behavior.

When set, the governor writes `leases.json` under that directory after a
successful in-process grant or release. Writes use the existing identity-lock
+ atomic-replace pattern from the AS-ORCH-001E loop store.

## Fail-closed reads

Projection consumers may ack visibility only when lease id, worker, package,
and live `base_pin` all match an `ACTIVE` row. Stale pins, foreign workers,
foreign packages, duplicate actives, and replay fail closed.

## Out of scope

- Replacing the in-memory governor as grant authority
- Consuming the Cursor bridge / PR400 pending slot
- Auto-merge, owner-gate bypass, or lease-scope expansion
