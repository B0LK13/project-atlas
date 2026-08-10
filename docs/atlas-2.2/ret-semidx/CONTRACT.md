# RET-SEMIDX — contract sketch (PREP)

Package: **AS-2.2-RET-SEMIDX-PREP-001**

| Slot field | Prep rule |
|---|---|
| `semantic.enabled` | **false** by default |
| `semantic.index_contract_id` | required before enable |
| `semantic.authority` | always `derived`; never Layer B |
| Fail closed | missing contract → reject enable |

See forbidden-action schema for rehearsal vocabulary.
