# AS-ID-001 — Durable Source Lineage Identity

Status: implementation complete — governor review required.

AS-ID-001 adds a durable `source_lineage_id` to the Core source registry while
retaining the path-derived `source_id` during its compatibility window. Project
identity is an explicitly allocated UUIDv4 persisted in the source project
marker. Source-lineage IDs are derived only after that UUID is committed:

```text
sline- + sha256(
  atlas/source-lineage/v1 | project_uuid | canonical_first_seen_path |
  first_content_sha256 | lineage_generation
)[:20]
```

The implementation uses the existing write-plan and single `_promote`
boundary. A Core-local, project-scoped lock serializes genesis and migration;
the losing initializer rereads the committed marker and performs no second
allocation. Source registry v1 migration is staged with the UUID, registry,
and migration receipts in the same plan.

The package does not modify AS-CORE-002 lifecycle vocabularies, AS-CORE-003,
the Control Plane, claims, reviews, conflicts, retrieval, or graph identity.
Ambiguous continuity and duplicate active project UUIDs fail closed before
promotion.
