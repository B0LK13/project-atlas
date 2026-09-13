# AS-OBSIDIAN-CAPTURE-001-F7-R1 — YAML constructor KeyError containment

## Object

- Package: AS-OBSIDIAN-CAPTURE-001-F7-R1
- Base: `b87b4a226f4aa8b2f669edf112aa3476454f754f`
- Base tree: `46d1989b026a2f15920ec5e1c78a106799bd1249`
- MERGE_AUTHORIZATION = NOT_GRANTED
- Independent certification: pending

## Defect

F7 sealed BOM ownership and recorded this residual without fixing it:

`yaml.safe_load` raises a bare `KeyError` (not `yaml.YAMLError`) for a
malformed explicit bool tag. `_existing_capture_id` caught only
`yaml.YAMLError`, so the public `retry()` API escaped.

Reproducer:

```text
---
atlas: !!bool nope
---
body
```

On live main `b87b4a22`:

```text
_existing_capture_id: KeyError KeyError('nope')
retry: KeyError KeyError('nope')
note unchanged: True
```

Outcome was fail-closed (bytes unchanged). Mechanism was wrong: the
exception bypassed `ObsidianNoteError` and `_render_stage`.

## Fix

Catch `(yaml.YAMLError, KeyError)` in `_existing_capture_id` and return
`None`. The caller still refuses with `OBSIDIAN_NOTE_CONFLICT`.

This does **not** widen acceptance. A constructor-tag corrupt note is
still unmanaged.

## What this does not do

- Does not edit `ingestion.py` (F5-B / DOGFOOD-001 freeze)
- Does not change BOM recognition (F7 remains sealed)
- Does not claim merge authorization
- Does not claim GitHub CI (billing lock = EXTERNAL_BLOCKED)

## Tests

`tests/unit/test_as_obsidian_capture_001_f7_r1_yaml_keyerror.py`
