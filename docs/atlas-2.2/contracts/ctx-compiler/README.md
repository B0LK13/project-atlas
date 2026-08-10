# Context Compiler — contract drafts (PREP)

Status: **PREP ONLY**. Schema drafts under `docs/atlas-2.2/` are **not**
shipped package data and must not be imported from `src/` until unlock + freeze.

| Draft ID | File | Role |
|---|---|---|
| `atlas.2.2.context-compiler-request.v0` | `context-compiler-request.schema.json` | Task + profile + budget input |
| `atlas.2.2.context-item.v0` | `context-item.schema.json` | Per-item provenance + signals |
| `atlas.2.2.context-compiler-package.v0` | `context-compiler-package.schema.json` | Output package + pipeline receipt |

## Compatibility posture

- Future production schemas will pin a 2.1 compatibility snapshot (not invented here).
- Until unlock: treat these as review vocabulary only.
- `estate_facts_invented` must remain `false` on all packages.
- `authority.level` on the package envelope remains `derived`.

## Error code sketch (non-normative)

| Code | Meaning |
|---|---|
| `context-compiler-profile-unknown` | Unknown profile_id |
| `context-compiler-estate-facts-invent-forbidden` | invent flag set |
| `context-compiler-budget-overflow` | hard cap exceeded |
| `context-compiler-secret-finding` | privacy stage blocked item/set |
| `context-compiler-authority-spoof` | authority level not from Core vocabulary |
