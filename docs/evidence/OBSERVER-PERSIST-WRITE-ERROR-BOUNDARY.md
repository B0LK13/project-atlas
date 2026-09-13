# Observer persist write error boundary

## Object

- Package: OBSERVER-PERSIST-WRITE-ERROR-BOUNDARY
- Base: `b87b4a226f4aa8b2f669edf112aa3476454f754f`
- MERGE_AUTHORIZATION = NOT_GRANTED

## Defect

`external_observers._atomic_write` created parents and replaced the target
with no `OSError` guard. A blocked ancestor leaked a raw OSError.
Reads already fail closed (`load_*` swallow OSError). Writes did not.

## Fix

Catch `OSError` and raise `SdkRuntimeError` with code `OBSERVER_WRITE_FAILED`.
Success path unchanged. Does not grant merge.

## Tests

`tests/unit/test_observer_persist_write_error_boundary.py`
