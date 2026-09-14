# Interface handoffs — AS-WORK-READINESS-001

These dependencies are **not** claimed as live integrations on this branch.
Fixture adapters document the expected ports until owners land them on main.

| Missing interface | Expected port | Owner lane | Fixture stand-in |
| --- | --- | --- | --- |
| Task contracts | `ContractPort.load_for_task` | `ATLAS-BACKLOG-TO-TASK-CONTRACT-001` / `AS-TASK-CONTRACT-001` | `fixture.taskcontract.v1` |
| Enrollment / claims | `EnrollmentPort`, `ClaimPort` | Program supervisor (e.g. PR #797) | `fixture.enrollment.v1`, `fixture.claims.v1` |
| Quality-loop results | `ResultPort.result_for` | `ATLAS-EXECUTION-QUALITY-LOOP-001` | `fixture.qualityloop.v1` |
| Dependency DAG status | `DependencyPort.status_for` | Autonomy / program DAG | `fixture.dependencies.v1` |
| Atomic claim before dispatch | Existing lease/claim API | Supervisor / registry | **Not simulated** — report dependency; no faux-atomic alternative |
| Studio UI | Consume `WorkQueueReport` / `HandoffProposal` JSON | Studio owner | Documented projection interface in README |

When a live port becomes available, wire it behind the same Protocol shapes in
`adapters.py` and keep fixture bundles for hermetic tests.
