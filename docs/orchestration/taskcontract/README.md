# AS-TASK-CONTRACT-001 — backlog item to task contract

One structured source for three things that otherwise drift apart: the
instruction a worker receives, the program configuration that launches it, and
the acceptance checks that judge the result.

## Truth boundaries

| | |
| --- | --- |
| `VALID_CONTRACT != EXECUTION_AUTHORIZATION` | A contract references authorization; it never holds it. There is no `authorized` field. |
| `VALID_CONTRACT != TASK_COMPLETE` | `acceptance_outcome` is always `NOT_EVALUATED` here. Nothing in this package observes a result. |
| `PRESENCE != BEHAVIOUR` | A `FILE_EXISTS` check is supporting evidence. A requirement judged only by presence is an ERROR. |
| `TEXT_MATCH != PROOF` | Every heuristic finding is a WARNING. None is an ERROR. |
| `ESTIMATED_COST != BILLED_SPEND` | The budget records what is enforceable and, separately, what is not. |
| `RESOLVES_HERE != AVAILABLE_THERE` | A bare executable resolving on this host says nothing about the worker's. |

## The seven verbs

```bash
atlas task sources  --project <repo>
atlas task draft    --project <repo> --item <ITEM-ID> --supplied supplied.json \
                    --contract-id <ID> --source-revision <sha> --out contract.json
atlas task validate --contract contract.json --binding binding.json \
                    --project <repo> [--program program.json] [--json-out report.json] [--json]
atlas task render   --contract contract.json --binding binding.json --profile profile.json \
                    --approved-by <who> --approval-reference <where> \
                    --out-program program.json --out-instruction instruction.md
atlas task review   --contract contract.json --binding binding.json --project <repo> \
                    --program-file program.json --out review-package.json
atlas task diff     --before contract.v1.json --after contract.v2.json \
                    [--binding-before b1.json] [--binding-after b2.json]
atlas task verify   --contract contract.json --report report.json [--binding binding.json]
```

Exit codes: `0` fine, `1` operational error, `2` usage, `3` validation found an
ERROR. Every command prints one JSON object; `validate` prints the operator
view instead unless `--json` is passed. Logs go to stderr, so `2>/dev/null`
leaves clean JSON on stdout.

## Task content vs deployment binding

`TaskContract` is repository-relative and portable — absolute paths are refused
at construction. `DeploymentBinding` holds one installation's absolute
`workspace_root`, `state_root`, `registry_root` and `interpreter`, plus the
profile and role. They digest separately, so a contract reviewed on one host
does not inherit that review on another: `task verify` reports a changed
binding as stale evidence.

The binding is also where the interpreter is decided. A contract may write
`python3`; `task render` substitutes the binding's absolute interpreter into
the generated argv, once, from a structured value. Bare `python` has been
observed not to resolve on hosts that have `python3`.

## Requirements, prompt and acceptance

Every result requirement has a stable identifier and one of three verification
modes, kept apart because collapsing them manufactures rigour:

- `AUTOMATED` — a named check decides it. It must name at least one, and they
  must not all be presence-only.
- `HUMAN_REVIEW` — no check can close it. Reported as a WARNING on every
  validation so it cannot be forgotten by a green report.
- `NO_CHECK_AVAILABLE` — automatable in principle, not yet checkable. Recorded
  as UNKNOWN rather than covered by a weaker check.

`render` writes every requirement into the instruction verbatim, by identifier.
A worker cannot satisfy a condition it was never told about.

## Five dimensions

`structurally_valid`, `content_complete`, `preconditions_checked`,
`execution_authorization`, `acceptance_outcome`. A contract can be structurally
valid and content-complete while the launch stays blocked. Only
`execution_authorization` consults the agent registry, and only through
`enrollment`; `DEMONSTRATED` still is not permission, because the supervisor
re-checks status and assignment immediately before every dispatch and that
check is the authoritative one.

## What validation never does

It never executes an acceptance `argv`. Contracts are drafted from backlog
text, and backlog text is written by whoever can edit the backlog; running a
command it names would make "can edit docs/backlog.md" equal to "can execute
code on this host". `shutil.which` resolves a name without running it, and the
base-pin check reads the git object database directly rather than shelling out.

See `demo/` for the whole flow on a real backlog item, and `ROLES.md` for what
each of the three readers needs.
