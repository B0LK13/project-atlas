# AS-CODER-ALPHA-ROADMAP-MCP-001

Zero-arg vault-scoped MCP read tool for Living Project Roadmap V1.

```
atlas.roadmap.read
```

- Allow-listed `vault-read` only. No request args.
- Enumerates `projects/*` and returns one derived roadmap per project.
- ROADMAP != canonical. UNKNOWN stays valid. No invented completion.
- Does not replace `/v1/roadmap` or `#/roadmap`.
