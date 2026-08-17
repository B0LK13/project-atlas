---
name: atlas-vault-documentation
description: Enforce immediate, evidence-backed documentation of all meaningful agent work in the Project Atlas vault. Use whenever an agent plans, implements, edits, investigates, tests, reviews, deploys, decides, encounters a blocker, changes scope, or hands work off. Capture raw evidence first, normalize through mda-cli, update affected Atlas concepts, validate the result, and return an ATLAS-DOC-RECEIPT before declaring completion.
---

# Atlas Vault Documentation

Act as an **Atlas documentation participant** in addition to your primary role. Every meaningful project action must produce durable, source-backed knowledge in the Atlas vault during the same work cycle.

**Programmatic use:** install this directory as the `atlas-vault-documentation` mda-cli skill or pass it with `--skill-dir`. mda-cli loads this `SKILL.md` together with `MDA-STANDARD.md`.

## Authority and precedence

1. Follow the user’s explicit task requirements.
2. Follow repository safety, contribution, and security policies.
3. Follow the active Project Atlas schemas and project-specific documentation policy.
4. Follow `MDA-STANDARD.md` in this skill directory.
5. Use the reference documents in `references/` where the preceding sources are silent.
6. Never weaken evidence, secret-handling, human-edit protection, or source immutability.

When instructions conflict, record the conflict and follow the safer, more authoritative rule.

## Non-negotiable completion rule

Work is **not complete** until documentation is synchronized or explicitly marked as blocked.

Before reporting completion, produce an `ATLAS-DOC-RECEIPT` containing:

- event ID;
- raw event path;
- normalized event path or normalization status;
- affected Atlas notes;
- validation status;
- outstanding documentation blockers.

A code change, test run, diagnosis, review, deployment, or decision without a receipt is an incomplete work cycle.

## Immediate documentation loop

1. **Resolve context**
   - Locate the Atlas vault.
   - Resolve project ID, project slug, repository, branch, session, and work package.
   - Read the project `index.md`, `project.md`, `status.md`, active work package, and applicable standards.
2. **Open the work cycle**
   - Capture a `session-start` or `plan` event before substantial edits.
   - Record objective, scope, assumptions, intended validation, and expected documentation impact.
3. **Perform work**
   - Execute the primary task.
   - Do not postpone all documentation until the final response.
4. **Capture meaningful events immediately**
   - Write a raw event before starting the next major step.
   - Include evidence locations, exact commands when relevant, results, changed files, decisions, and uncertainty.
5. **Normalize**
   - Run mda-cli with this skill against the raw event.
   - Keep the raw capture immutable.
   - Treat normalized output as generated and review-required until validated.
6. **Route knowledge**
   - Update every affected Atlas concept, not merely the chronological log.
7. **Validate**
   - Check required metadata, links, provenance, protected regions, and unresolved spool events.
8. **Close the work cycle**
   - Capture a `handoff`, `completion`, or `blocked` event.
   - Return the documentation receipt.

## Meaningful event triggers

Capture an event when:

- a plan or task scope is created or materially changed;
- files, configuration, schemas, infrastructure, or documentation are modified;
- a command produces decision-relevant output;
- tests, linting, typing, security checks, benchmarks, or deployment checks run;
- a defect, risk, contradiction, missing dependency, or blocker is found;
- an architectural, product, operational, or security decision is made;
- a work package starts, changes state, completes, or is abandoned;
- a deployment, rollback, migration, or recovery action occurs;
- evidence changes the known project status;
- another agent or human must continue the work.

Do not create noise for trivial navigation or repeated commands that produce no new state. Consolidate tightly related low-level actions into one evidence-backed event.

## Capture-first rule

Preferred destination:

```text
<atlas-vault>/sources/agent-events/YYYY/MM/DD/<event-id>.md
```

If the vault is unavailable or unsafe to write:

```text
<repository>/.atlas-spool/<event-id>.md
```

Spooling is temporary. Do not claim clean completion while required events remain in `.atlas-spool`.

## mda-cli normalization

Installed skill:

```bash
mda --skill atlas-vault-documentation <raw-event-path>
```

Repository-local skill:

```bash
mda --skill-dir <path-to-this-skill> <raw-event-path>
```

Rules:

- Never use `--in-place` on immutable raw evidence.
- Use sibling output or explicit `--out-dir` (mda-cli 0.2.9). `--output-folder` is not a 0.2.9 flag.
- Canonical current-run sibling suffix is `.restructured.md`.
- Preserve mda-cli atomic-write behavior.
- Treat provider failure as `normalization-pending`.
- Record command, exit status, provider when known, and output path.

## Required event content

Record when applicable:

- stable event ID and event kind;
- occurrence time and agent identity;
- project, repository, branch, session, and work package;
- objective, trigger, and concise outcome;
- changed files or systems;
- commands and observed results;
- validation;
- decisions and rationale;
- risks, blockers, and uncertainty;
- evidence paths;
- next actions;
- affected Atlas concepts.

Use `unknown` or `[MISSING: ...]` when unresolved. Never invent identifiers, commits, test results, dates, or links.

## Evidence rules

- Distinguish observed facts from inference.
- Record exact pass/fail counts when available.
- A command is not evidence of success without its observed result.
- A changed file list does not prove behavior.
- A test validates only its actual scope.
- A generated summary cannot cite itself as sole evidence.
- Use repository-relative or vault-relative source paths where possible.
- Never persist secrets, tokens, private keys, passwords, or sensitive environment values.

## Atlas routing rules

Always update the chronological project log. Additionally:

| Event kind | Required Atlas targets |
|---|---|
| `plan` | active work package; roadmap when scope changes |
| `implementation` | work package; component or architecture when affected |
| `decision` | decision record; affected components; project log |
| `validation` | validation record; work package; project status |
| `issue` | issue/finding; risk when material |
| `risk` | risk record; project status when active |
| `deployment` | deployment; environment; release; validation |
| `rollback` | deployment; issue; status; risk |
| `research` | source/reference; affected decision or work package |
| `handoff` | work package; status; next actions |
| `completion` | work package; status; project log; validation |
| `blocked` | issue/risk; work package; status |

Do not mark work completed, operational, verified, or production without supporting evidence.

## Human content protection

- Never overwrite `BEGIN HUMAN` / `END HUMAN` regions.
- Replace only explicitly generated regions.
- Fail closed when markers are malformed.
- Do not edit imported source evidence.
- Create a review proposal when a canonical note cannot be safely updated.

## Failure behavior

### Vault unavailable

Capture to `.atlas-spool`, mark synchronization pending, and synchronize before clean completion.

### mda-cli unavailable

Preserve raw evidence, mark normalization pending, and report the missing executable or environment issue.

### Provider failure

Preserve raw evidence, record a sanitized error category, and keep normalization pending.

### Conflicting information

Preserve all claims, create or update a conflict record, and flag human review.

## Required final response fragment

Include this exact heading:

```text
ATLAS-DOC-RECEIPT
```

Then report:

```yaml
event_id: <id>
raw_event: <path>
normalized_event: <path | pending | not-required>
atlas_updates:
  - <path>
validation: <passed | warnings | failed>
sync_state: <synchronized | pending | blocked>
blockers: []
```

The receipt must reflect actual writes. Never claim an update that did not occur.
