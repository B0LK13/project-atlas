# Reality Gap prep — contract drafts (PREP)

Status: **PREP ONLY**. Schema drafts under this directory are **not** shipped
package data and must not be imported from `src/` until unlock + freeze.

| Draft ID | File | Role |
|---|---|---|
| `atlas.2.2.reality-gap-prep-inventory.v0` | `reality-gap-prep-inventory.schema.json` | Inventory envelope |
| `atlas.2.2.reality-gap-prep-scenario.v0` | `reality-gap-prep-scenario.schema.json` | Scenario row |

## Error code sketch (non-normative)

| Code | Meaning |
|---|---|
| `reality-gap-prep-unknown-as-healthy-forbidden` | unknown coerced to healthy |
| `reality-gap-prep-ui-canonical-writes-forbidden` | UI tried canonical write |
| `reality-gap-prep-pilot-invent-forbidden` | invent_pilot_roots or pilot_roots>0 |
| `reality-gap-prep-gap-id-invalid` | gap_id pattern fail |
| `reality-gap-prep-evidence-class-invalid` | non fixture-only in PREP |
