# Agent Integration

## Universal requirement

Repository agent instructions must require the full skill, identify Atlas configuration, require capture before the next major step, and require a final receipt.

## Configuration discovery order

1. explicit command-line parameters;
2. `ATLAS_AGENT_CONFIG`;
3. repository `atlas-agent.yaml`;
4. repository `.atlas/agent.yaml`;
5. environment variables;
6. user-level defaults.

## Recommended environment variables

```text
ATLAS_VAULT
ATLAS_PROJECT_ID
ATLAS_PROJECT_SLUG
ATLAS_AGENT_ID
ATLAS_SESSION_ID
ATLAS_WORK_PACKAGE
ATLAS_AGENT_CONFIG
```

## Agent surfaces

Adapters are supplied for `AGENTS.md`, `CLAUDE.md`, Cursor rules, `GEMINI.md`, and generic system prompts. They are launch points; `SKILL.md` is authoritative.

## Multi-agent coordination

Each agent uses a unique identity and session ID. Agents may share a work package but never an event ID. A supervisor reconciles pending spool items, conflicting claims, handoffs, and duplicate completion events.
