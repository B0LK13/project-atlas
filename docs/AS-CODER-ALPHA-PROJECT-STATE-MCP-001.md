# AS-CODER-ALPHA-PROJECT-STATE-MCP-001

Zero-arg vault-scoped MCP read tool for the existing project-state lens.

```
atlas.project-state.read
```

- Allow-listed `vault-read` only. No request args (`project`, `as_of`, `args` forbidden).
- Enumerates `projects/*` and returns current derived state per project.
- Empty vault → empty states. UNKNOWN stays valid. MCP != authority.
- Does not replace `/v1/project-state` or the Intelligence web page.
