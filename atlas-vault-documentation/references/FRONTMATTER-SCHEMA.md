# Agent Work Event Frontmatter

## Raw capture

```yaml
---
type: Agent Work Event Source
id: source:agent-event:<event-id>
event_id: <event-id>
event_kind: <controlled kind>
occurred_at: <ISO-8601 UTC>
captured_at: <ISO-8601 UTC>
agent: <agent>
project_id: <project ID>
project_slug: <project slug>
session_id: <session ID or unknown>
work_package: <work package or unknown>
repository: <repository or unknown>
branch: <branch or unknown>
commit: <commit or unknown>
sync_state: captured
normalization_state: pending
knowledge_state: source
review_state: generated
tags:
  - agent-event-source
  - <event-kind>
---
```

## Validation constraints

- `event_id` is stable and unique.
- timestamps use ISO-8601;
- project ID is present or explicitly unknown;
- event kind uses the controlled vocabulary;
- a source event never self-asserts `verified`;
- normalized output references the raw source;
- secret values are absent;
- repository and vault paths are normalized.
