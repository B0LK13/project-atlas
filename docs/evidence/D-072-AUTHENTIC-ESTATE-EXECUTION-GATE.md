# D-072 authentic-estate execution gate (not started)

DIRECTIVE: `D-PROJECT-ATLAS-OWNER-D049-MERGE-072`

Technical merge of #348 is `POST_MERGE_VERIFIED`. Authentic-estate
acceptance is a separate product proof.

```
AUTHENTIC_USER_ESTATE_ACCEPTANCE = NOT_EVALUATED
D_049_ACCEPTANCE = NOT_YET_EVALUATED
D_042_EXECUTION_GATE = CLOSED
OWNER_AUTHORIZED_ROOT = <not yet supplied>
```

## What this gate is waiting for

The owner must explicitly name **one** bounded existing root.

This directive does **not** authorize:

- entire disk
- home directory
- all Documents
- all OneDrive
- all Obsidian
- any invented or guessed path
- any scan Cloud performs without that root

## After the owner supplies a root

Follow `docs/evidence/D-071-AUTHENTIC-ESTATE-RUNBOOK.md` (and the
historical D-066 plan, which still names the invalidated `0509287`
freeze as contemporaneous text). Use sealed `main` production trees
(`src/` identical to `ccacaa5`).

Do not start D-042 from this gate.
