# YAML constructor KeyError containment

## Object

- Package: YAML-CONSTRUCTOR-KEYERROR-CONTAINMENT
- Base: `b87b4a226f4aa8b2f669edf112aa3476454f754f`
- Base tree: `46d1989b026a2f15920ec5e1c78a106799bd1249`
- MERGE_AUTHORIZATION = NOT_GRANTED

## Defect

PyYAML `!!bool nope` raises a bare `KeyError`, not `yaml.YAMLError`.
Three remaining loaders on live main leaked it:

| Site | Public/helper | Pre-fix |
|------|----------------|---------|
| `yaml_structured.load_safe_yaml` | public safe loader | `KeyError` |
| `estate_discovery._parse_marker_file` | estate marker parse | `KeyError` |
| `graph_acceptance._parse_artifact` (metadata YAML) | graph acceptance | `KeyError` |
| `graph_acceptance._project_id` (marker YAML) | graph acceptance | `KeyError` |

Reproduced on `b87b4a22`. Sibling package #819 contains the same class
in `obsidian_capture_note._existing_capture_id` only.

## Fix

Map constructor `KeyError` onto each site's existing structured refusal:

- `MalformedYamlError` from `load_safe_yaml`
- `marker_status=invalid` from estate marker parse
- `GraphAcceptanceError("malformed-metadata")` from graph acceptance

Does not widen acceptance. Does not touch `ingestion.py`.

## Tests

`tests/unit/test_yaml_constructor_keyerror_containment.py`
`tests/unit/test_yaml_structured.py::test_bool_constructor_keyerror_is_structured`
