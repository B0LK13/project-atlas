# AS-STUDIO-A0-001 — migration / compatibility policy

```text
NO_WHOLESALE_CORE_REWRITE
REUSE_BEFORE_REIMPLEMENT
STUDIO_UI != AUTHORITY
ATLAS_DAEMON = AUTHORITATIVE_RUNTIME
MODEL_PROVIDER != ATLAS_ARCHITECTURE
```

## Policy

1. **No wholesale Core rewrite.** Studio attaches as a projection/control
   shell. Truth Core, vault identity, and coordination F1–F16 remain the
   authoritative implementations.
2. **Reuse before reimplement.** Prefer importing `atlas_dag.*` builders and
   existing LIVE_API/MCP read patterns over parallel eligibility logic.
3. **Versioned contracts.** Studio clients consume
   `ATLAS_STUDIO_SNAPSHOT_V1` / `ATLAS_STUDIO_EVENT_V1`. Breaking changes
   require a new schema const (`_V2`), not silent field repurposing.
4. **A0/A1 contracts are stable attach points.** Knowledge Plane (A5) and
   Improvement Plane (A7) may attach later **without replacing** A0/A1
   snapshot/event/authz boundaries. They extend panels/provenance; they do
   not redefine Studio as authority.
5. **Compatibility.** Older RO clients must tolerate additional optional
   panels (`additionalProperties` where declared) and must fail closed on
   honesty const violations.
6. **Provider neutrality.** Swapping model providers must not fork Studio
   architecture or daemon contracts.

## Non-goals of migration

- Replacing `atlas-dag` with a Studio-owned DAG engine.
- Replacing vault Truth Core with UI-local “knowledge.”
- Treating demo fixtures as authentic pilot authority.
