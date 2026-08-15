# AS-CODER-ALPHA-DECISIONS-STALE-001

```
PACKAGE = AS-CODER-ALPHA-DECISIONS-STALE-001
BASE = 32c992894d7cabe58dd4b965585093fe6d308458
OWNER_HELD = YES
MERGE_AUTHORIZATION = NOT_GRANTED
```

Decision memory is compiled from last-connect vault notes/claims.
Editing `docs/DECISIONS.md` without reconnect can leave
`ACTIVE_GOVERNING` looking current.

This package rehashes decision-looking active sources
(`DECISIONS.md`, ADR paths) and stamps
`honesty.governing_evidence_stale`. It does not invent a new governing
decision.

Does not rewrite `connect.py` or `cli.py`. Independent of #380/#381/#383.

```
DECISION LENS != AUTHORITY
STALE GOVERNING EVIDENCE != CURRENT
```
