# Atlas 3 — Knowledge extraction

AT3-040 reuses the landed conversation-capture taxonomy.
Do not create a second item vocabulary.

## Taxonomy (canonical, already shipped)

```text
session_note
idea
observation
research_finding
action_item
open_question
proposed_decision
confirmed_owner_decision
claim_candidate
constraint
lesson_learned
failed_approach
next_step
```

Source: `src/project_atlas/conversation_capture.py` `ITEM_TYPES`.

## Extraction classes

| Class | Allowed now |
|---|---|
| Deterministic / heuristic | Yes — derived interpretation |
| Structured submission | Yes — Core path |
| LLM-assisted | Only as derived; must keep extractor identity + version |
| Transcript extraction in Core | **NOT IMPLEMENTED** — do not claim otherwise |

Every extracted item retains:

- provider, conversation, message references
- source content hash
- project identity
- temporal metadata (observation / source if present)
- extractor identity + version

## Owner decision safety

Never infer `confirmed_owner_decision` from model paraphrase.

Only when provenance proves an explicit owner-origin statement:

```text
owner_origin.evidence_kind = explicit_owner_statement
owner_origin.origin = owner
owner_origin.statement = <non-empty>
```

Otherwise classify `proposed_decision` or `claim_candidate`.

Preserve existing `FALSE_OWNER_DECISION` fail-closed semantics.
