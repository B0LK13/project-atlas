# Ops-health YAML constructor KeyError containment

## Object

- Package: OPS-HEALTH-YAML-CONSTRUCTOR-KEYERROR
- Base: `b87b4a226f4aa8b2f669edf112aa3476454f754f`
- Base tree: `46d1989b026a2f15920ec5e1c78a106799bd1249`
- MERGE_AUTHORIZATION = NOT_GRANTED

## Defect

PyYAML `!!bool nope` raises a bare `KeyError`, not `yaml.YAMLError`.
`ops_health._read_yaml_mapping` leaked it, so a constructor-tagged
`.atlas/agent-readiness.yaml` aborted `build_health_snapshot`.

Reproduced on `b87b4a22`. Sibling of #819 / #820 / #822 / #823 / #824 / #825.

## Fix

Map constructor `KeyError` onto the existing unreadable-file path (`None`).
Does not invent readiness. Does not touch `ingestion.py`.

## Tests

`tests/unit/test_ops_health_yaml_constructor_keyerror.py`
