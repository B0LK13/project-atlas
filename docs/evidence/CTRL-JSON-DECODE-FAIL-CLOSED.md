# Control-plane JSON decode fail-closed containment

## Object

- Package: CTRL-JSON-DECODE-FAIL-CLOSED
- Base: `b87b4a226f4aa8b2f669edf112aa3476454f754f`
- Base tree: `46d1989b026a2f15920ec5e1c78a106799bd1249`
- MERGE_AUTHORIZATION = NOT_GRANTED

## Defect

Malformed JSON leaked `json.JSONDecodeError` from fail-closed control-plane
readers on live main:

| Site | Pre-fix |
|------|---------|
| `vault_identity.read` | `JSONDecodeError` |
| `authority.load_grant` / `revoke_grant` | `JSONDecodeError` |
| `session.load` | `JSONDecodeError` |
| `repository_gate.validate` | `JSONDecodeError` |

Reproduced on `b87b4a22`. Sibling of #827 (YAML constructor class; this is JSON).

## Fix

Map `JSONDecodeError` onto existing structured refusals. Does not authorize
grants or sessions. Does not touch Core `ingestion.py`.

## IV remediation (2026-09-13)

Independent verification of `3427d76c` found a VALID P1: JSON `null`
parsed successfully as `None` and skipped both the unreadable and
malformed arms, so `repository_gate.validate` returned `ok=True`.
Truthy non-dicts (`[1]`, `true`) then crashed on `receipt.get`.

Successful non-object parses now collect `receipt is malformed` and
never call mapping methods on a non-dict. Decode failures still collect
`receipt is unreadable` only.

## Tests

`atlas-vault-documentation/tests/test_ctrl_json_decode_fail_closed.py`
