# D-092 — Local conversational-capture round-trip runbook

Validate the **exact D-091 production freeze**, not a later evidence tip.

```
D091_HEAD = 9ec65c7662f1ed8e18805a9496df8ded19d2c65e
D091_TREE = 97e56303ec7642bb86c9799cd2dbd79bfa1eaf08
CONVERSATION_CAPTURE_SCHEMA = atlas.conversation-capture.v1
```

Checkout:

```
git fetch origin
git checkout 9ec65c7662f1ed8e18805a9496df8ded19d2c65e
git rev-parse HEAD
git rev-parse HEAD^{tree}
```

Required match:

```
HEAD == 9ec65c7662f1ed8e18805a9496df8ded19d2c65e
TREE == 97e56303ec7642bb86c9799cd2dbd79bfa1eaf08
```

---

## Preconditions

D-092 authentic capture requires a governed Atlas identity/vault binding.
Owner-authorized D-092A onboarding for `D:\dev-ai\dark-factory` is the
precondition. D-092A accepted-main onboarding ≠ D-091 production payload.

```
LOCAL_D092_READY = CONDITIONAL
LOCAL_D092_GOVERNED_PROJECT_PRECONDITION = PENDING_D092A
D092A_AUTHORIZED_PROJECT_ROOT = D:\dev-ai\dark-factory
CANONICAL_GOVERNED_VAULT = D:\atlas-governed\dark-factory
```

After D-092A PASS:

- Use that **existing** governed project / vault binding.
- Do **not** create a second project from capture.
- Do **not** run estate discovery as a capture prerequisite.
- Do **not** include real secrets.
- Conversation payload is a controlled representative structured envelope.

If D-092A is not PASS, D-092 authentic round-trip is
`NOT_APPLICABLE` / `BLOCKED`. Do not blame D-091 for accepted-main
connect/onboarding behavior.

---

## Round-trip

1. Confirm the target project already exists under `vault/projects/<id>/`.
2. Write a provider-neutral `atlas.conversation-capture.v1` JSON file with:
   - observation
   - idea
   - action_item
   - open_question
   - proposed_decision
   - confirmed_owner_decision **only if** explicit `owner_origin` is supplied
3. Submit:

```
atlas capture conversation --vault <vault> --input capture.json --json
```

4. Confirm:
   - routed to the existing project
   - receipt `capture_id` starts with `ccap-`
   - inbox file exists under `generated/ops/inbox/`
   - Markdown projection exists and says it is not Truth Core
5. Repeat the exact command. Required:

```
SAME_INPUT_SAME_CAPTURE_ID = YES
REPLAY_DUPLICATE_WRITES = 0
```

6. `atlas context --vault <vault> --project <id>` must label the capture
   `Conversation capture — non-authoritative`.
7. Optional API parity (privileged LIVE_API token only):

```
POST /v1/captures/conversation
```

Must return the same `capture_id`.

---

## Fail-closed checks

- Unmatched project id → `UNMATCHED_PROJECT`
- Two project ids → `CONFLICTING_PROJECT`
- Name-only routing → `UNMATCHED_PROJECT`
- `confirmed_owner_decision` without `owner_origin` → `FALSE_OWNER_DECISION`
- Secret-shaped item text → `SECRET_CONTENT` (no echo)
- Prompt-injection text is stored as data and does not ingest/connect/discover

---

## Do not

- Point this runbook at a later evidence commit
- Treat REVIEWED as Truth Core promotion
- Merge without a later owner merge authorization
