# AS-CODER-ALPHA-UNKNOWN-MCP-001 / AS-CODER-ALPHA-CHANGED-MCP-001

Zero-arg vault-scoped MCP reads of the landed unknown and What Changed lenses.

```
atlas.unknown.read
atlas.changed.read
```

- No request args. Vault scope only. Not implicit portfolio-all.
- UNKNOWN != HEALTHY. CHANGED != KDIFF. MCP != AUTHORITY.
- No Layer B writes. No inventory rotation.
- Same deny-by-default MCP contract as `atlas.brief.read`.

Does not replace `#424` source-health/attention/next MCP, `#406` What Next, or D-149.
