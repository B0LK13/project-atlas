# Atlas Agent Documentation Standard

This is the governing transformation specification for the `atlas-vault-documentation` mda-cli skill.

## 1. Purpose

Transform one raw agent work event into a concise, structured, evidence-backed, Obsidian-compatible `Agent Work Event` suitable for Project Atlas.

Preserve factual meaning, uncertainty, evidence references, exact validation results, and the distinction between observed facts and inference.

## 2. Output contract

Unless the caller explicitly requests commentary only:

- Return exactly one Markdown document inside one outer fence of four backticks with language tag `markdown`.
- Include no preamble or postamble outside the fence.
- YAML frontmatter is the first content inside the fence.
- Use valid UTF-8 Markdown and YAML.
- Do not use numbered headings or a table of contents.
- Do not create more than one event from one raw event.
- Do not silently merge separate events.
- Do not reproduce secret values.

mda-cli may strip the outer fence before writing.

## 3. Required frontmatter

```yaml
---
type: Agent Work Event
title: "<concise outcome-oriented title>"
id: "agent-event:<stable-event-id>"
project_id: "<project ID or unknown>"
project_slug: "<project slug or unknown>"
event_kind: "<controlled event kind>"
status: "<completed | in-progress | blocked | failed | informational>"
occurred_at: "<ISO-8601 timestamp or unknown>"
agent: "<agent identity or unknown>"
session_id: "<session ID or unknown>"
work_package: "<work package or unknown>"
repository: "<repository or unknown>"
branch: "<branch or unknown>"
commit: "<commit SHA or unknown>"
review_state: generated
knowledge_state: evidence-backed
sync_state: synchronized
normalization:
  tool: mda-cli
  skill: atlas-vault-documentation
sources:
  - id: "source:<raw-event-id>"
    resource: "<raw event path>"
relationships:
  affects: []
  validates: []
  blocks: []
tags:
  - agent-work
  - "<event-kind>"
---
```

Preserve additional useful non-secret metadata.

## 4. Controlled event kinds

```text
session-start
plan
implementation
refactor
decision
validation
issue
finding
risk
research
deployment
rollback
migration
recovery
documentation
handoff
completion
blocked
```

## 5. Required body structure

```markdown
# <Title>

## Outcome

## Scope and changes

## Evidence

## Validation

## Decisions and rationale

## Risks, blockers, and uncertainty

## Next actions

## Atlas routing
```

Rules:

- Use `None recorded.` only when absence is meaningful.
- Use bullets for changed files, commands, evidence, and next actions.
- Preserve exact commands in fenced code blocks.
- Preserve exact test counts and exit codes.
- Separate successful validation from unexecuted validation.
- Mark inference explicitly as `Inference:`.
- Mark unresolved data as `[MISSING: ...]`.
- Do not convert pending or failed work into completed work.

## 6. Title rules

The title states the outcome, remains concise, avoids vague labels, and never claims more success than evidence supports.

## 7. Evidence normalization

Preferred representation:

```markdown
- **Command:** `python -m pytest tests/unit/test_hashing.py`
  - **Observed result:** `12 passed`
  - **Scope:** Source hashing unit tests
```

Do not infer an exit code unless provided.

## 8. Validation state

- `completed`: action finished and required validation passed;
- `in-progress`: work occurred but required validation remains;
- `blocked`: work cannot safely continue;
- `failed`: attempted action failed;
- `informational`: research, diagnosis, or observation.

## 9. Atlas routing

List specific concepts and distinguish:

- `Updated:`
- `Proposed:`
- `Pending:`

Never claim routing occurred unless the raw event says so.

## 10. Security

Redact secrets as `[REDACTED SECRET]`, including API keys, tokens, passwords, private keys, credential-bearing connection strings, cookies, and sensitive environment values.

## 11. Contradictions

Retain each conflicting claim and source, state that the conflict is unresolved, propose a conflict record, and do not select a value merely because it appears later.

## 12. Quality gate

- [ ] YAML is valid and begins the document.
- [ ] Required metadata is present or explicitly unknown.
- [ ] Event kind is controlled.
- [ ] Status matches evidence.
- [ ] Raw source reference is preserved.
- [ ] Exact validation results remain.
- [ ] No secrets are exposed.
- [ ] Facts and inference are distinguished.
- [ ] Atlas routing is explicit.
- [ ] No unsupported completion claim was introduced.
- [ ] Output contains one four-backtick Markdown wrapper and nothing else.
