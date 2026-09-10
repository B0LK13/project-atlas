# Goal checkpoint — mission lifecycle reliability

```text
HEAD_AT_CHECKPOINT      = see git rev-parse HEAD after push
PRIOR_REPORTED          = 1bca04e3 / b9fd932d (superseded)
CI_EXACT_HEAD           = NOT_ESTABLISHED (do not poll-loop)
FORMAL_IV               = NOT_STARTED (prior IV does not transfer)
MERGE                   = NOT_GRANTED
```

## This increment

1. Binding: null `intent_id` on decision → MISMATCHED_BINDING (blocks PENDING_EXECUTE).
2. Snapshot consistency block: COHERENT / INCOHERENT / UNPROVEN; `SNAPSHOT_INCONSISTENT` state.
3. Cross-process acceptance via fresh `python -m atlas_studio` processes + labeled fixtures.
4. CLI module entry (`__main__`) so subprocess/module invocation actually runs commands.
5. READ_ERROR unreadable-file coverage.

## Next

- One-shot CI check after tip settles; pin exact-head SUCCESS once.
- Owner Formal IV only after CI pin.
- No further engineered gaps unless concrete risk appears.
