---
type: Agent Work Event Source
id: source:agent-event:{{ event_id }}
event_id: {{ event_id }}
event_kind: {{ event_kind }}
occurred_at: {{ occurred_at }}
captured_at: {{ captured_at }}
agent: {{ agent }}
project_id: {{ project_id }}
project_slug: {{ project_slug }}
session_id: {{ session_id }}
work_package: {{ work_package }}
repository: {{ repository }}
branch: {{ branch }}
commit: {{ commit }}
sync_state: captured
normalization_state: pending
knowledge_state: source
review_state: generated
tags:
  - agent-event-source
  - {{ event_kind }}
---

# {{ summary }}

## Objective or trigger

{{ objective }}

## Outcome

{{ outcome }}

## Changed files or systems

{{ changed_files }}

## Commands and observed results

{{ commands_and_results }}

## Validation

{{ validation }}

## Decisions and rationale

{{ decisions }}

## Risks, blockers, and uncertainty

{{ risks }}

## Evidence

{{ evidence }}

## Next actions

{{ next_actions }}

## Intended Atlas routing

{{ atlas_routing }}
