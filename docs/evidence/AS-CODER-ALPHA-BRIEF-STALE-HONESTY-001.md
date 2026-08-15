# AS-CODER-ALPHA-BRIEF-STALE-HONESTY-001

```
PACKAGE = AS-CODER-ALPHA-BRIEF-STALE-HONESTY-001
STACKED_ON = 381
BASE_BRANCH = cursor/next-stale-evidence-001-315e
OWNER_HELD = YES
MERGE_AUTHORIZATION = NOT_GRANTED
```

`atlas brief` already calls `build_next_lens` live. After #381, What Next
stamps `answer_evidence_stale`. This successor copies that honesty onto the
brief payload so CLI / LIVE_API / MCP brief consumers cannot treat a stale
brief as current.

Does not rewrite `connect.py`, `cli.py`, or `web_api/brief.py`.
Does not flatten the #381 stack.

```
BRIEF != AUTHORITY
STALE EVIDENCE != CURRENT
UI != CANONICAL TRUTH
```
