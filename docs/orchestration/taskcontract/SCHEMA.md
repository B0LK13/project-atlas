# Contract schema and version compatibility

`schema_version: 1`, `package_id: AS-TASK-CONTRACT-001`. Both are `Literal`
fields: a file carrying any other value is refused, not upgraded in place.

## Compatibility rule

A reader accepts exactly the `schema_version` it was written for. There is no
"best effort" parse of a newer file, because a contract whose unknown half is
silently dropped is a contract whose scope, exclusions or acceptance may have
been the dropped half. Every model sets `extra="forbid"` for the same reason:
a typo'd field name is an error, not an ignored key.

`contract_version` is a different number and does the opposite job: it counts
human revisions of the same contract. It participates in `contract_digest`, so
bumping it is itself a change that invalidates an earlier report.

## Objects

| Object | Holds | Digested by |
| --- | --- | --- |
| `TaskContract` | everything repository-relative and portable | `contract_digest` |
| `DeploymentBinding` | one installation's absolute paths, profile, role | `binding_digest` |

Both digests are SHA-256 over canonical JSON (`sort_keys`, no whitespace) —
the same construction `program/loader.py::program_digest` uses.

Neither object carries an observation time, a hostname or a run counter, so the
same explicit input always digests the same. Report metadata such as
`observed_at` lives on the validation report and never on the contract, which
is what keeps that true.

## Field groups

- **identity** — `contract_id`, `contract_version`, `schema_version`
- **provenance** — `source.{source_path,item_id,item_digest,source_revision,title}`
- **intent** — `objective`, `observable_outcome`, `scope`, `exclusions`
- **accountability** — `owner`, `authorization_references[]`
- **eligibility** — `depends_on`, `executable_when`
- **repository** — `repository`, `base_pin` (full 40-char sha)
- **paths** — `mutation_paths`, `expected_output_paths`, `evidence.evidence_paths`
- **runtime** — `runtime.{adapter,capabilities,adapter_min_version,constraints}`
- **context** — `context[].{source_id,path,why,digest}`
- **results** — `requirements[].{requirement_id,statement,verification,check_ids,review_note}`
- **checks** — `acceptance[]`, reusing `program.models.AcceptanceCheck` unchanged
- **bounds** — `limits`, `budget.{max_estimated_cost_usd,enforced_by,not_enforced}`
- **handover** — `evidence.handover_conditions`

`execution_authorized` and `merge_authorized` exist and are `Literal[False]`.
They are present so a reader looking for the authority field finds the answer,
rather than reading their absence as "unrestricted".

## Reused, not redefined

`AcceptanceCheck`, `AcceptanceKind`, `AdapterKind` and `AgentCapability` are
imported from the program and autonomy packages. This package adds no second
scheduler, registry, authorization system or backlog database: intake is
`origination.sources.eligible_work_items`, validation of the rendered program
is `program.loader.load_program`, and authorization is
`program.enrollment.load_registry`.

## Finding codes

`ERROR` objectively wrong now and checkable without running anything;
`WARNING` suspicious or true-but-recoverable; `UNKNOWN` not checkable from here.
The same three words, with the same meanings, as the program preflight uses.

| Code | Severity |
| --- | --- |
| `content.placeholder` | ERROR |
| `content.check_unknown_ref` | ERROR |
| `content.requirement_unchecked` | ERROR |
| `content.requirement_presence_only` | ERROR |
| `content.check_orphan` | ERROR |
| `content.requirement_human_review` | WARNING |
| `content.path_repeated_in_prose` | WARNING |
| `content.budget_unbounded` | WARNING |
| `content.limits_incoherent` | WARNING |
| `content.requirement_no_check_available` | UNKNOWN |
| `content.budget_not_enforced` | UNKNOWN |
| `paths.output_outside_mutation` | ERROR |
| `paths.evidence_outside_mutation` | WARNING |
| `paths.mutation_duplicate` / `paths.mutation_nested` | WARNING |
| `runtime.adapter_unsupported` | ERROR |
| `runtime.version_unpinned` / `runtime.constraint_unverified` | UNKNOWN |
| `acceptance.argv_empty` | ERROR |
| `acceptance.executable_missing` / `acceptance.executable_unresolvable` | ERROR |
| `acceptance.executable_bare` | WARNING |
| `acceptance.executable` | OK |
| `binding.workspace_missing` / `binding.workspace_not_git` | ERROR |
| `binding.state_inside_workspace` | ERROR |
| `binding.registry_missing` / `binding.interpreter_missing` | ERROR |
| `binding.context_missing` | ERROR |
| `binding.base_pin_absent` | WARNING |
| `binding.absent` | UNKNOWN |
| `dependencies.self_reference` / `dependencies.missing` | ERROR |
| `dependencies.unresolved` / `dependencies.sources_unreadable` | UNKNOWN |
| `freshness.source_item_gone` / `freshness.source_changed` | ERROR |
| `freshness.source_unchecked` / `freshness.sources_unreadable` | UNKNOWN |
| `authorization.registry_assignment` | OK |
| `authorization.agent_not_active` / `authorization.assignment_elsewhere` / `authorization.no_assignment` | WARNING |
| `authorization.not_checkable` / `authorization.reference_manual` / `authorization.registry_unreadable` | UNKNOWN |

A declared output file that does not exist before the first run is deliberately
no finding at all.
