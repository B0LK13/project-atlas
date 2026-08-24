# AS-CODER-ALPHA-CONFLICTS-MCP-001

Zero-arg vault-scoped MCP read tool for unresolved project conflicts.

```
atlas.conflicts.read
```

- Allow-listed `vault-read` only. No request args.
- Enumerates `projects/*` and projects persisted `review/conflicts/<id>.json`.
- Never resolves a conflict or picks a winner.
- Secret-shaped claim values stay redacted. MCP != authority.

Does not replace `/v1/conflicts` or `#/time-machine`.
