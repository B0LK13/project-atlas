# D-057 project-marker YAML constructor KeyError containment

## Object

- Package: D-057-MARKER-YAML-CONSTRUCTOR-KEYERROR
- Base: `b87b4a226f4aa8b2f669edf112aa3476454f754f`
- Base tree: `46d1989b026a2f15920ec5e1c78a106799bd1249`
- MERGE_AUTHORIZATION = NOT_GRANTED

## Defect

PyYAML `!!bool nope` raises a bare `KeyError`, not `yaml.YAMLError`.
Four project-marker readers on live main leaked it:

| Site | Public/helper | Pre-fix |
|------|----------------|---------|
| `discovery._project_context` / `discover()` | `atlas discover` | `KeyError` |
| `connect._read_project_marker` / `connect_project()` | `atlas connect` | `KeyError` |
| `origination.sources.load_origination_sources` | origination scan | `KeyError` |
| `origination.acceptance_contracts.load_acceptance_contracts` | marker + contracts file | `KeyError` |

Reproduced on `b87b4a22`. Sibling of #819 / #820 / #822 (same constructor
class). Does not touch `ingestion.py`.

## Fix

Map constructor `KeyError` onto each site's existing structured refusal:

- `ValueError("INVALID_PROJECT_MARKER: ...")` from discover
- `ConnectError("INVALID_PROJECT_MARKER: ...")` from connect
- `OriginationSourceConfigError("unreadable project marker")` from origination sources
- `AcceptanceContractConfigError("unreadable ...")` from acceptance contracts

Does not widen acceptance.

## Tests

`tests/unit/test_d057_marker_yaml_constructor_keyerror.py`
