# AS-CODER-ALPHA-SOURCE-HEALTH-MCP-001

Zero-arg vault-scoped MCP read tool for Coder Alpha source-health.

```
atlas.source-health.read
```

- Allow-listed `vault-read` only. No request args (`project`, `args`, `path` forbidden).
- Enumerates `projects/*` and returns one derived report per project.
- Empty vault → empty reports (honest emptiness, not invented CLEAR).
- MCP != authority. UNKNOWN remains valid. Secrets are never echoed.
- Same fail-closed parsing contract as AS-2.1-MCP-ADV-001.

Does not grant estate scan, vault write, or owner capability.
