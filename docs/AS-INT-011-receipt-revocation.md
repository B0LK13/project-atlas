# AS-INT-011 — Receipt revocation and invalidation semantics

**Status:** implemented  
**Backlog:** INT-011  
**Package:** AS-INT-011

## Scope

Deterministic operational projection for **revoking** or **invalidating**
agent-event receipts without deleting files and without inventing project
authority:

```text
receipts/agent-events/<project-id>/<event-id>.yaml   (file may remain)
generated/ops/receipt-revocations.json               (operational index)
```

Distinct from AS-INT-010 tombstones (deleted package/receipt units) and from
AS-INT-009 retention (count/byte eviction).

## Reasons / status

| Reason | Default status | Meaning |
|---|---|---|
| `operator` | `revoked` | Explicit operator withdrawal of receipt trust |
| `skill_policy` | `revoked` | Skill / readiness policy rotation withdrew trust |
| `integrity` | `invalidated` | Integrity / hash follow-up rendered receipt unusable |

## Apply

```bash
atlas revocation revoke --vault <vault> --project <id> --event <id> \
  [--reason operator|skill_policy|integrity] [--status revoked|invalidated] \
  [--detail <text>] [--json]

atlas revocation list --vault <vault> [--json]
atlas revocation status --vault <vault> --project <id> --event <id> [--json]
```

Index path: `generated/ops/receipt-revocations.json` (`sort_keys=True`, no
`generated.at`).

Library helpers: `revoke_receipt`, `is_receipt_revoked`,
`receipt_trust_disposition`, `assert_receipt_active`,
`inventory_with_revocations`.

## Explicit non-goals

- No rewrite of `event_tombstones` / INT-010 core
- No Layer B concept-note deletion or authority invention
- No automatic skill-registry dual-own (consume disposition only)
- No `apps/web`, PILOT invent, REL-001, or Atlas 2.0 production semantics
