# Control-plane YAML constructor KeyError containment

## Object

- Package: CTRL-YAML-CONSTRUCTOR-KEYERROR
- Base: `b87b4a226f4aa8b2f669edf112aa3476454f754f`
- Base tree: `46d1989b026a2f15920ec5e1c78a106799bd1249`
- MERGE_AUTHORIZATION = NOT_GRANTED

## Defect

PyYAML `!!bool nope` raises a bare `KeyError`, not `yaml.YAMLError`.
Control-plane loaders on live main leaked it:

| Site | Pre-fix |
|------|---------|
| `agent_control.preflight.project_config` | `KeyError` |
| `agent_control.preflight` certification receipt | `KeyError` |
| `agent_control.readiness.check` | `KeyError` (SEC-015 DENY bypassed) |
| `agent_control.readiness.promote` | `KeyError` |
| `agent_control.skill_loader.load` | `KeyError` |

Reproduced on `b87b4a22`. Sibling constructor class of #819–#826, control-plane surface only.

## Fix

Map constructor `KeyError` onto existing fail-closed refusals. Readiness
check DENY-closes (does not authorize). Does not touch Core `ingestion.py`.

## Tests

`atlas-vault-documentation/tests/test_ctrl_yaml_constructor_keyerror.py`
