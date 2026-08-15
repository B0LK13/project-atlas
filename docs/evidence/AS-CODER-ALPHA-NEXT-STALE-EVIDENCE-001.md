# AS-CODER-ALPHA-NEXT-STALE-EVIDENCE-001

```
PACKAGE = AS-CODER-ALPHA-NEXT-STALE-EVIDENCE-001
BASE = 32c992894d7cabe58dd4b965585093fe6d308458
OWNER_HELD = YES
MERGE_AUTHORIZATION = NOT_GRANTED
```

What Next reads cached `generated/answers` plus live attention/source-health.
After a disk edit without reconnect, those answers can look current.

This package compares live source fingerprints to `connect-manifest`.
Proven drift stamps `honesty.answer_evidence_stale=true` and a
`stale_evidence` queue item. Missing `source_root` or inventory is
`UNKNOWN`, never fabricated `FRESH`.

Does not rewrite `connect.py` or `cli.py`. Does not import
`context_stale_guard` (independent of #380).

```
NEXT LENS != AUTHORITY
STALE EVIDENCE != CURRENT
UNKNOWN != FRESH
ANSWER CACHE != TRUTH CORE
```
