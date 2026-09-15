# Product Requirements Prompt — Atlas Vault Agent Documentation Skill

## Product definition

A universal agent skill and deterministic support layer that makes Project Atlas documentation part of every execution transaction.

## Problem

Implementation, diagnostic, validation, and decision evidence often remains only in terminals or final chat summaries. Delayed documentation causes lost evidence, stale status, unverifiable completion, undocumented decisions, weak handoffs, and repeated investigation.

## Outcome

Every meaningful agent state transition becomes:

1. immutable raw evidence;
2. a normalized Agent Work Event;
3. updates to affected Atlas concepts;
4. a validated documentation receipt.

## Functional requirements

- **FR-S001 Universal skill:** one self-contained mda-cli-compatible skill directory.
- **FR-S002 Immediate capture:** capture before the next major work step.
- **FR-S003 Offline evidence:** raw capture requires no model or internet.
- **FR-S004 mda normalization:** normalize with mda-cli and this standard.
- **FR-S005 Immutable sources:** never transform raw evidence in place.
- **FR-S006 Conditional routing:** update project log and event-relevant concepts.
- **FR-S007 Failure visibility:** vault, mda, provider, validation, or routing failure remains visible.
- **FR-S008 Completion receipt:** each completion response includes an accurate receipt.
- **FR-S009 Human safety:** protected human content is preserved.
- **FR-S010 Security:** redact secrets and constrain paths.
- **FR-S011 Idempotency:** repeated processing creates no duplicate canonical records.
- **FR-S012 Multi-agent operation:** events remain unique and traceable across sessions.

## Non-functional requirements

- deterministic and atomic capture;
- plain Markdown and Obsidian compatibility;
- provider-neutral normalization;
- offline testability;
- portable paths;
- source provenance;
- bounded documentation noise.

## MVP

The MVP includes the skill contract, transformation standard, raw-event script, validation script, configuration, adapters, templates, and acceptance suite. Full automatic routing may move into the parent Atlas CLI.

## Success metrics

- 100% of completed fixture tasks produce a receipt.
- 100% of raw events have stable IDs and timestamps.
- 0 raw events mutated by normalization.
- 0 fixture secrets emitted.
- 0 duplicate log entries on reroute.
- 100% of validation claims link to evidence.
- 0 clean completion states with pending strict-mode spool events.
