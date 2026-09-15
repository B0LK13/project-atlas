# Atlas 2.3 — Strategic backlog

**Position:** post-2.2 intelligence slice; still not north-star end-state.  
**Not** in 2.1 release-critical queue.

| ID | Theme | Proposed packages | Notes |
|---|---|---|---|
| B-2.3-001 | Multi-user collaboration network plane | AS-2.3-COLLAB-NET-001 | Local receipts exist (2.1); network plane later |
| B-2.3-002 | Federation / multi-vault | AS-2.3-FED-001, AS-2.3-FED-LENS-001 | Contracts exist; production later |
| B-2.3-003 | Estate scheduler / autonomy L4 consideration | AS-2.3-AUTONOMY-L4-RFC-001 | L4/L5 remain off unless RFC+AUTHZ |
| B-2.3-004 | Obsidian UX product polish | AS-2.3-OBSIDIAN-UX-001 | Beyond 2.1 live read shell |
| B-2.3-005 | Backup / migration recovery productization | AS-2.3-BACKUP-OPS-001 | Build on existing backup modules |
| B-2.3-006 | Mission/Workspace full product lenses | AS-2.3-WEB-MISSION-WORKSPACE-001 | After 2.1 harden stubs |

## DAG sketch

```text
v2.2.0
  |
  +--> COLLAB-NET
  +--> FED
  +--> OBSIDIAN-UX
  +--> BACKUP-OPS
  |
  v
AS-REL-2.3-001 → v2.3.0
```

## Discipline

Items here must not be pulled into 2.1 P0 to “look complete.”
