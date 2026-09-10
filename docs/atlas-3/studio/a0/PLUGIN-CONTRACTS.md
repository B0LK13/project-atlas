# AS-STUDIO-A0-001 — plugin contracts (deferred stub)

```text
PREP != IMPLEMENTED
PLUGIN_SURFACE = DEFERRED
FAIL_CLOSED = REQUIRED
```

A0 PHASES asked for plugin contracts. Repository truth: no Studio plugin
runtime exists yet. This stub records the binding law until a later package
introduces versioned plugin schemas:

1. Plugins are **projections/extensions**, never authority.
2. Unknown plugin IDs / unsigned contracts **fail closed**.
3. Plugins must not claim/dispatch/merge/IV or bypass `ATLAS_STUDIO_*` honesty.
4. First executable plugin schema lands with an explicit package ID — not A0.

See ADR-034 and `AUTHZ-BOUNDARY.md`.
