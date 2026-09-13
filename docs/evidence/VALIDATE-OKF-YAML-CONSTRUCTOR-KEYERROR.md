# OKF concept-note YAML constructor KeyError containment

## Object

- Package: VALIDATE-OKF-YAML-CONSTRUCTOR-KEYERROR
- Base: `b87b4a226f4aa8b2f669edf112aa3476454f754f`
- Base tree: `46d1989b026a2f15920ec5e1c78a106799bd1249`
- MERGE_AUTHORIZATION = NOT_GRANTED

## Defect

PyYAML `!!bool nope` raises a bare `KeyError`, not `yaml.YAMLError`.
`validation._validate_okf_concept_note` (used by `atlas validate` for
`projects/*/concepts.md`) leaked it and aborted the vault scan.

Reproduced on `b87b4a22`. Sibling of #819 / #820 / #822 / #823.

## Fix

Map constructor `KeyError` onto the existing structured finding:

`invalid OKF concept note <path>: ...`

Does not widen acceptance. Does not touch `ingestion.py`.

## Tests

`tests/unit/test_validate_okf_yaml_constructor_keyerror.py`
