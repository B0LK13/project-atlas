# Demonstration: one real backlog item, end to end

`./run-demo.sh` runs the whole flow against **INT-013** in this repository's own
`docs/backlog.md`, which carries a real, human-authored acceptance contract in
`docs/origination-acceptance-contracts.yaml`.

Read-only. The original item and its ownership are unmodified, no worker starts,
no model call is made, and no acceptance command is executed. `evidence/` holds
the raw output of the run recorded here; `snapshot/` pins the exact item text
and digest it ran against.

```bash
ATLAS_PREFLIGHT=/path/to/scripts/acceptance/program_preflight.py ./run-demo.sh
```

## Source → contract → report → instruction → configuration → review

| Step | Command | Evidence |
| --- | --- | --- |
| 1 | `atlas task sources` | `evidence/01-sources.json` — 24 eligible items |
| 2 | `atlas task draft` (no input) | `evidence/02-draft-incomplete.json` — 10 named gaps |
| 3 | `atlas task draft --supplied` | `evidence/03-draft-complete.json` → `contract.v1.json` |
| 4 | `atlas task validate` | `evidence/04-validate-operator-view.txt` — exit 0 |
| 5 | `atlas task render` | `evidence/05-render.json` → `program.v1.json`, `instruction.v1.md` |
| 6 | `atlas program validate` | `evidence/06-program-validate.json` — `valid: true` |
| 7 | `program_preflight.py` | `evidence/07-preflight.txt` |
| 8 | `atlas task review` | `evidence/08-review-package.json` |
| 9 | blocked example | `evidence/09-blocked-operator-view.txt` — exit 3, 6 errors |
| 10 | `atlas task diff` / `verify` | `evidence/10-diff.json`, `evidence/11-verify-stale.json` |

## What the run shows

**Nothing is invented.** With no supplied input the draft names ten gaps, each
with the question that closes it — owner, base_pin, mutation_paths, runtime,
requirements, acceptance, limits, budget, repository, observable_outcome — and
fills none of them.

**The blocker survives.** INT-013 is `EXTERNAL_BLOCKED`. The draft carries that
into `executable_when` as `blocker resolved: ...`. The contract never claims the
blocker is cleared, and the demonstration does not clear it.

**A conflict is reported, not resolved.** An earlier run of step 3 supplied a
prose scope while the item's own acceptance contract states scope as two paths;
the draft returned `SCOPE_DISAGREES_WITH_SOURCE_CONTRACT` with both sides. The
committed `supplied.json` now quotes the human-authored scope verbatim, so the
conflict list is empty — the disagreement was resolved by a person, which is
the only way this package resolves one.

**The interpreter is substituted once, from a structured value.** The contract
writes `python3`; validation warns that resolving here says nothing about the
worker's host; `render` writes the binding's absolute interpreter into the
generated argv. The preflight then reports `acceptance.executable` OK — which is
an independent tool agreeing, having been given only the generated file.

**Two tools agree that authorization is absent.** This package reports
`execution_authorization: NOT_DEMONSTRATED`; the preflight reports
`registry.exists` ERROR. Neither was told the answer by the other.

**The blocked example fails for six separate, concrete reasons** — a requirement
judged only by file presence, two acceptance checks linked to no requirement, an
output outside the mutation scope, a `state_root` inside the workspace, and an
interpreter that does not exist — and exits 3.

**An earlier approval does not survive.** `diff` reports
`prior_approval_still_describes_this_work: false` with `why_not: ["acceptance
changed", "scope changed", "deployment binding changed"]`, and `verify` reports
the v1 validation report as stale against the v2 contract, naming both digests.

## What it does not show

That INT-013 was done. Every report in `evidence/` carries
`acceptance_outcome: NOT_EVALUATED`, and `atlas program validate` reports
`execution_authorized: false`, `merge_authorized: false`.

`supplied.json`, `binding.json` and `profile.json` are **demonstration input**.
They are decisions written to show the flow, not approvals of INT-013.
