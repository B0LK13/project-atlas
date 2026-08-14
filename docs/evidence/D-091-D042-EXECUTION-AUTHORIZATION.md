# D-091 — D-042 conversational capture execution authorization

DIRECTIVE: `D-PROJECT-ATLAS-OWNER-D042-D091-FRESH-EXECUTION-AUTHORIZATION`
PACKAGE: `AS-CODER-ALPHA-CONVERSATIONAL-CAPTURE-001` (CAPTURE-002 / D-042)

This file records the fresh execution lane. It does **not** rewrite
`docs/evidence/D-042-KICKOFF-PACKET.md`. Historical CLOSED-gate text in
that packet remains a historical object.

```
D049_CLOSED_MAIN = c282f2c1eb2dde24f997e480c37d083fda906e54
D049_STATE = CLOSED
D_042_EXECUTION_GATE = OPEN
D042_IMPLEMENTATION = IN_PROGRESS
HISTORICAL_PR_344_REUSED = NO
FRESH_BRANCH = cursor/d042-conversational-capture-6f85
```

---

## Authorized base

```
AUTHORIZED_BASE_MAIN = c282f2c1eb2dde24f997e480c37d083fda906e54
PRESTART_MAIN_MATCH = YES
```

`origin/main` was fetched and matched the authorized SHA before the
branch was created.

---

## Production freeze

```
D091_HEAD = 9ec65c7662f1ed8e18805a9496df8ded19d2c65e
D091_TREE = 97e56303ec7642bb86c9799cd2dbd79bfa1eaf08
CONVERSATION_CAPTURE_SCHEMA = atlas.conversation-capture.v1
EXISTING_SESSION_CAPTURE_REUSED = YES
TRANSCRIPT_EXTRACTION = DEFERRED
RAW_TRANSCRIPT_PERSISTED_BY_DEFAULT = NO
MCP = NOT_APPLICABLE
MERGE_AUTHORIZATION = NOT_GRANTED
```

MCP remains a read-only allow-list (`write_tools: []`). No capture write
tool was invented.

After this freeze, only evidence / governance / explicitly classified
test-only changes may follow.

```
PRODUCTION_SEMANTIC_CHANGES_AFTER_D091_FREEZE = 0
```

---

## Product contract on the freeze

- CLI: `atlas capture conversation` (`--input`, `--stdin`, or `--item`)
- API: `POST /v1/captures/conversation` (privileged `web.action`)
- Durable artifacts under `generated/ops/conversation-captures/`
- Knowledge Inbox receipt via existing `build_knowledge_inbox_receipt`
- Human-readable Markdown projection (not canonical)
- Agent context section: `Conversation capture — non-authoritative`
- Web Knowledge Inbox panel on `/knowledge` (UI ≠ Truth Core)
- Review lifecycle `captured|reviewed|rejected` does not promote

Authority hard gates on implementer + freeze IV suite:

```
CAPTURE_AUTO_PROMOTIONS = 0
TRUTH_CORE_MUTATIONS_FROM_CAPTURE = 0
PROJECT_IDENTITIES_MINTED = 0
DISCOVERY_SIDE_EFFECTS = 0
CONNECT_SIDE_EFFECTS = 0
INGEST_SIDE_EFFECTS = 0
SECRET_ECHO = 0
PROMPT_INJECTION_EXECUTIONS = 0
DUPLICATE_CAPTURE_RECORDS_ON_REPLAY = 0
```

---

## Local D-092

See `docs/evidence/D-092-LOCAL-REVALIDATION-RUNBOOK.md`.

Local must validate **exact** `D091_HEAD` / `D091_TREE`, not a later
evidence tip.
