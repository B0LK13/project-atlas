# D-042 kickoff packet (inputs only)

DIRECTIVE context: D-082 Lane I, refreshed by D-086 / D-087 / D-089.

```
D042_KICKOFF_PACKET_READY = YES
D042_KICKOFF_PACKET_D087_ALIGNED = YES
D_042_EXECUTION_GATE = OPEN
D042_IMPLEMENTATION = NOT_STARTED
D049_STATE = CLOSED
ACCEPTED_MAIN = c282f2c1eb2dde24f997e480c37d083fda906e54
```

`OPEN != IMPLEMENTED`. Do not start D-042 from this file.
Do not reopen `#344`. Wait for a fresh owner-authorized execution lane.

This file is **not** a D-042 implementation, PREP coding package, or
authorization to reopen `#344`. Do not create a D-042 branch from this packet.

Lane H conditions now exist (D-088 CASE A PASS + owner-authorized #351
merge `c282f2c` + post-merge exact-main PASS). The execution gate is
OPEN. Implementation still requires a fresh owner-authorized D-042
directive. Do not treat this packet as that authorization.

---

## Accepted main (Lane H fired)

Accepted main is the **merge commit** of #351, not the D-087 freeze
itself (merge commit ≠ production freeze).

```
ACCEPTED_MAIN = c282f2c1eb2dde24f997e480c37d083fda906e54
ACCEPTED_MAIN_TREE = 2490d370ee5dc40cdcc4d66e1d821be300ec1c59
D087_PRODUCTION_FREEZE = b2b5d9b9fc7e4d3aff69fea3e1a90d9c950b0b78
D087_PRODUCTION_TREE = 14318297c5fbf40b4fff054ad27126ee4c89db7f
```

Historical candidates (do not Local-validate, do not merge alone):

```
D084_PRODUCTION_FREEZE = 2fcf8186d4a2c6d4209cee82b6d6f076e2119589
D080_PRODUCTION_FREEZE = 99aa937b3718cf0432bb688dbfa074daade7c049
```

---

## Truth / authority invariants (must survive D-042)

```
DISCOVER != CONNECT != INGEST != TRUST != AUTHORITY
UI != CANONICAL TRUTH
MODEL OUTPUT != AUTHORITY
LLM output != authority
CAPTURE != AUTHORITY
INBOX != TRUTH CORE
PREP != IMPLEMENTED
DEMO_FIXTURE != AUTHENTIC_PILOT
```

No claim without a traceable source. No silent promotion from capture or
inbox into Layer B / Truth Core.

---

## Project identity semantics

- one `project_uuid` → one durable project identity
- discovery match ≠ proof of ownership
- `FAMILY_GROUPING != IDENTITY_MERGE`
- CONNECTED requires durable bind / source-root ownership
- D-042 must not mint, merge, or rewrite project identity

---

## Discovery contract D-042 must not weaken

### D-078 root-mode

- Default: filesystem root and home refused
- Explicit `--root-mode owner-authorized-volume` is Windows non-system
  volume discovery only
- System volume / UNC / `/` remain refused

### D-080 truth

- Volume root is a scope container, not a project
- Knowledge never attaches to blank / dangling / container ids
- Traversal order is not selection authority

### D-084 selection

- `candidate_selection_policy = deterministic_hierarchical_fair_v2`
- Region round-robin before family / evidence / path tie-break
- One noisy region must not monopolize bounded output
- Ancestor project boundary is not displaced by a non-independent nested child
- Independent nested repositories remain separately eligible
- Sibling projects in one region must both have a realistic path into the cap
- Cheap sighting first; expensive enrichment only on a bounded shortlist
- Candidate limits bound output and memory, not first-seen admission

Conversational capture must not trigger estate discovery, ingest, or
connect as a side effect.

---

## Capture authority rules (AS-CODER-ALPHA-CAPTURE-001 already shipped)

Existing `atlas capture record` (`src/project_atlas/session_capture.py`):

- writes ops receipts under `generated/ops/session-captures/`
- kinds: milestone / decision / blocker / note / handoff
- captures are **ops receipts, not Layer B authority**
- UNKNOWN stays UNKNOWN

D-042 (Conversational Capture / CAPTURE-002) must keep that boundary.
A conversation transcript is evidence of a conversation, not a claim.

---

## Idempotency requirements

- Repeat capture of the same conversation must not duplicate authority
- Repeat capture may update an ops receipt only under an explicit contract
- No double ingest, no second project identity, no silent vault writes
  outside quarantine / inbox

---

## Provider-neutral capture contract

- Cursor / Claude / Codex / ChatGPT / other agents are sources, not owners
- Provider adapters optional; disabling them must leave Core functional
- No provider-specific authority bypass
- Existing AS-2.1 ChatGPT bridge already states `LLM output != authority`
  and quarantines capture — D-042 must not invert that

---

## Atlas Knowledge Inbox semantics

`docs/AS-2.0-INBOX-001.md`:

```
Quarantine intake; authority promote forbidden.
```

Conversational capture lands in inbox / quarantine. Human review / existing
Truth Loop is the only promotion path. Inbox ≠ Truth Core.

---

## Explicit non-starts

- do not implement D-042
- do not open/reopen PR #344
- do not create a D-042 branch
- do not write production capture code from this packet
