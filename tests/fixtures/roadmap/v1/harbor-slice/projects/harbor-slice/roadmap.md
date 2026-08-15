---
type: Roadmap
---

# harbor-slice roadmap

Cloud IV fixture. Designed so a later Local dogfood can point at a real
governed project. This fixture is not Dark Factory and does not invent
owner-vault contents.

## Roadmap record

```json
{
  "milestones": [
    {"id": "m-core", "title": "Core compile", "lifecycle": "POST_MERGE_VERIFIED"},
    {"id": "m-next", "title": "Next unlock", "lifecycle": "IN_PROGRESS"}
  ],
  "items": [
    {
      "id": "pkg-identity",
      "title": "Governed identity",
      "status": "VERIFIED_COMPLETION",
      "lifecycle": "POST_MERGE_VERIFIED",
      "milestone": "m-core",
      "depends_on": [],
      "evidence": ["generated/ops/receipts/identity.json"]
    },
    {
      "id": "pkg-connect",
      "title": "Connect compile",
      "status": "IMPLEMENTED",
      "lifecycle": "IMPLEMENTATION_COMPLETE",
      "milestone": "m-core",
      "depends_on": ["pkg-identity"],
      "evidence": ["generated/ops/receipts/connect.json"]
    },
    {
      "id": "pkg-roadmap",
      "title": "Living roadmap",
      "status": "IN_PROGRESS",
      "lifecycle": "IN_PROGRESS",
      "milestone": "m-next",
      "depends_on": ["pkg-connect"],
      "evidence": []
    },
    {
      "id": "pkg-gated",
      "title": "Gated surface",
      "status": "BLOCKED",
      "lifecycle": "IN_PROGRESS",
      "milestone": "m-next",
      "depends_on": ["pkg-roadmap"],
      "blockers": [
        {
          "reason": "owner merge gate",
          "waiting_on": "D042",
          "unlock_condition": "D042 merged to main"
        }
      ]
    }
  ]
}
```
