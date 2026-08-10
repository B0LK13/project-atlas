# Time Machine contract stubs

**PREP ONLY.** Not installed via `importlib.resources`. Not CI-gated.

See:

- `../CONTRACT.md`
- `../ARCHITECTURE.md`

When unlocked, promote through schema freeze + ADR — do not copy blindly into
`src/project_atlas/schemas/`.

| Stub | Artifact |
|---|---|
| `as-of-snapshot.schema.json` | As-of snapshot |
| `knowledge-diff.schema.json` | T1→T2 envelope |
| `claim-diff.schema.json` | Claim delta |
| `graph-diff.schema.json` | Graph delta |
| `decision-diff.schema.json` | Decision delta |
| `time-machine-forbidden-action.schema.json` | Deepen fail-closed action (AS-2.2-TIME-MACHINE-DEEPEN-PREP-001) |
