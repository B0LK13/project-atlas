# AS-CODER-ALPHA-LENS-MCP-001

Zero-arg vault-scoped MCP tools for existing Coder Alpha derive lenses:

| Tool | Lens |
|---|---|
| `atlas.overview.read` | `build_overview_lens` |
| `atlas.unknown.read` | `build_unknown_lens` |
| `atlas.state.read` | `build_state_lens` |

Honesty:

- MCP != AUTHORITY
- UNKNOWN is valid
- No request args / path / write keys
- Vault-scoped loop via `AppService.projects()` — not implicit portfolio-all
- Does not write Layer B
- `atlas.state.read` is the Coder Alpha CLI state lens, not AS-2.0 `/v1/project-state`

Does not duplicate `#478`/`#479` HTTP adapters.
