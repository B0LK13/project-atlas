# Agent Event Taxonomy

| Event kind | Use when | Typical status |
|---|---|---|
| `session-start` | A new work cycle begins | in-progress |
| `plan` | Scope or acceptance criteria are established or changed | in-progress |
| `implementation` | Behavior or configuration is added | in-progress / completed |
| `refactor` | Structure changes without intended behavior change | in-progress / completed |
| `decision` | A consequential choice is made | informational / completed |
| `validation` | Tests, checks, benchmarks, or evidence are produced | completed / failed |
| `issue` | A concrete defect or blocker is identified | blocked / informational |
| `finding` | Review, security, or quality analysis produces a finding | informational |
| `risk` | An uncertain exposure is identified or changed | informational |
| `research` | External or repository evidence is gathered | informational |
| `deployment` | A release is deployed or promoted | completed / failed |
| `rollback` | A deployed change is reversed | completed / failed |
| `migration` | Data, schema, environment, or platform is migrated | in-progress / completed |
| `recovery` | Service or data recovery is executed | completed / failed |
| `documentation` | Documentation is created or materially corrected | completed |
| `handoff` | Work is transferred | in-progress |
| `completion` | A work package satisfies its exit gate | completed |
| `blocked` | Work cannot safely continue | blocked |

Create one event per meaningful state transition. Consolidate tightly related actions sharing one objective, validation result, and work package. Split events when outcomes, decisions, projects, or evidence differ materially.
