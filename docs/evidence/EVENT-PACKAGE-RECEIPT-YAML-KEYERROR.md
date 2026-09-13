# Event-package receipt YAML constructor KeyError containment

## Object

- Package: EVENT-PACKAGE-RECEIPT-YAML-KEYERROR
- Base: `b87b4a226f4aa8b2f669edf112aa3476454f754f`
- Base tree: `46d1989b026a2f15920ec5e1c78a106799bd1249`
- MERGE_AUTHORIZATION = NOT_GRANTED

## Defect

PyYAML `!!bool nope` raises a bare `KeyError`, not `yaml.YAMLError`.
`atlas_contracts.event_package._load_receipt` leaked it instead of
`PackageValidationError("receipt.yaml invalid: ...")`.

Reproduced on `b87b4a22`. Sibling of #819 / #820 / #822 / #823 / #824.

## Fix

Map constructor `KeyError` onto the existing package-boundary refusal.
Does not widen acceptance. Does not touch `ingestion.py`.

## Tests

`tests/unit/test_event_package_receipt_yaml_keyerror.py`
