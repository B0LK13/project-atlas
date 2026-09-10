# ATLAS-LIVE-COMPONENT-INTEGRATION-002 — delivery

## Flags (separate)

| Flag | Value |
| --- | --- |
| `COMPONENTS_AVAILABLE` | **YES** |
| `LIVE_INTERFACES_CONNECTED` | **YES** (TaskContract ↔ context ↔ readiness via public models + explicit bridge) |
| `CONTROLLED_CHAIN_PASSED` | **YES** (INT-013 EXTERNAL_BLOCKED preserved + LCI-002-TEST-OWNED chain) |
| `INDEPENDENT_REVIEW` | **NO** |
| `REAL_LAUNCH_AUTHORIZED` | **NO** |

A positive score on the first three does **not** grant the last two.

## Component identities (from artifacts, not truncated chat)

| Component | Role tested | HEAD | TREE |
| --- | --- | --- | --- |
| Taskcontract | tip = impl | `b0c35270494890cd9acd067c4a02e70fd0503cf7` | `f195eeb8aecf6af5b5d47ef59bfadb4dc4b51dcf` |
| Context impl | feature | `94e7b397e9d2400643228f50468be624504e20bd` | `cb81c8f072607a1503aedf1be6cd5d2f8cf59077` |
| Context tip | impl + docs pin | `0a2541b5cc18bd16cbc61ec5c6eba1ffb2cb257d` | `9811bd84c20c3bafa8c65737dde24099d1574c5b` |
| Readiness impl | feature | `a6746c2bdabbdb2c58ef60ffced589694433eae6` | `f6eb52e14a9f452389f6136f9d7d1848055df0d6` |
| Readiness tip | impl + docs pins | `bf98963766f873349ddb46f2fc7dfc4daee3b8f0` | `81ae18a437190706f6b4738cc8dac19dede2d3a2` |
| Supervisor base | PR #797 | `80280bfe13c77708cada7af17215acdaff3725e4` | (unchanged) |

Taskcontract bundle verified: SHA-256
`d75c08af67e96836df2c37bae31ed238e19e290524ee479ce135b2f8e8304ee7`
(`atlas-taskcontract-b0c35270.bundle`).

**What was tested on this candidate:** full tips of all three components composed
onto the taskcontract/#797 base (context + readiness tip trees checked out;
CLI registrations merged). Tip includes docs pins; implementation digests above
identify the code commits.

## Supervisor base decision

Integration candidate base = taskcontract tip (`b0c35270`), which already
includes `orchestration.program` from PR #797. Merge of #797 to main remains
an **owner decision** and is not claimed here.

## Isolated environment

| | |
| --- | --- |
| Worktree | `/home/gebruiker/Projects/project-atlas-worktrees/live-component-integration-002` |
| Branch | `feat/live-component-integration-002` |
| Venv | `/home/gebruiker/Projects/project-atlas-runs/live-component-integration-002/venv` |
| Interpreter | that venv’s `bin/python` only (editable install of this worktree) |

Do not use foreign `PYTHONPATH` or another checkout’s `atlas` executable.

## Interface compatibility / translation layer

Module: `project_atlas.orchestration.live_integration`

| Direction | Mapping |
| --- | --- |
| TaskContract → context | `live_contract_to_context_snapshot` → `ContractSnapshot` (`source_kind=LIVE_MODULE`) |
| TaskContract → readiness | `live_contract_to_readiness_view` → `ContractView` |
| Context → handoff | packet `packet_id` + `content_digest` + freshness into `ReviewPackage` |
| Readiness → review | selection reasons, blockers, source revisions, optional `handoff_id` |

Production live load (`load_live_task_contract`) **fails closed** on schema
mismatch (`SCHEMA_INCOMPATIBLE`) — no silent fixture fallback.
`try_load_live_taskcontract` returns `None` for non-TaskContract files so
labeled fixtures still work in component tests.

## Reproduce demo (one command)

```bash
WT=/home/gebruiker/Projects/project-atlas-worktrees/live-component-integration-002
PY=/home/gebruiker/Projects/project-atlas-runs/live-component-integration-002/venv/bin/python
$PY -m project_atlas.cli live-integrate demo \
  --int013-contract $WT/docs/orchestration/taskcontract/demo/contract.v1.json \
  --owned-contract $WT/tests/fixtures/live_integration/LCI-002-TEST-OWNED.contract.json \
  --workspace $WT/tests/fixtures/task-context-continuity/repo \
  --out /home/gebruiker/Projects/project-atlas-runs/live-component-integration-002/demo-report.json
```

## Tests on this candidate

```bash
$PY -m pytest \
  tests/unit/test_live_component_integration_002.py \
  tests/unit/orchestration/test_work_readiness.py \
  tests/unit/test_task_context_continuity_001.py \
  tests/unit/test_taskcontract_preparation.py \
  tests/unit/test_taskcontract_authority_and_evidence.py \
  -q --override-ini='addopts='
```

Recorded: **72 passed** (see `…/runs/live-component-integration-002/component-tests.txt`).

## Proven boundaries / remaining blockers

* INT-013 valid contract/program path does **not** clear `EXTERNAL_BLOCKED` /
  does not become `OFFERABLE_TO_DISPATCHER` without live runtime+auth.
* Positive path uses **test-owned** `LCI-002-TEST-OWNED` only.
* Live ClaimPort / EnrollmentPort / ResultPort production wiring still open
  (demo enrollment is test-labeled).
* Atomic claim-before-dispatch remains supervisor-owned.
* No push, merge, self-IV, real backlog launch, or #726 package mutation.

## Owner handoffs

| Owner | Handoff |
| --- | --- |
| Program / #797 | Decide main merge of supervisor base; wire live enrollment/claim ports |
| Task-contract | Keep `TaskContract` schema stable; consume bridge as optional client |
| Task-context | Prefer live TaskContract via `try_load_live_taskcontract`; fixtures labeled |
| Work-readiness | Consume `LiveContractPort` / bridge instead of fixture-only demos |
| Quality-loop | Provide live `ResultPort` when available |
| Independent reviewer | Review this candidate; local tests ≠ IV |
| Launch authority | Owner-gated; this package never authorizes |

## Integration HEAD/TREE

* HEAD: 
* TREE: .
├── advance-005
│   ├── REMEDI-CLAUDE-001-005
│   │   ├── HEAD.txt
│   │   ├── ONELINE.txt
│   │   ├── probe_freshness.py
│   │   ├── probe-result.json
│   │   ├── probe-run.txt
│   │   └── VERDICT.md
│   ├── REMEDI-CLAUDE-009
│   │   ├── BASE_HEAD.txt
│   │   ├── HEAD.txt
│   │   ├── IDENTITY.txt
│   │   ├── ONELINE.txt
│   │   ├── pr.json
│   │   ├── probe_isolation.py
│   │   ├── probe-results.json
│   │   ├── probe-run.txt
│   │   ├── pytest-hybrid.txt
│   │   └── VERDICT.md
│   └── REMEDI-CLAUDE-293
│       ├── IDENTITY.txt
│       └── VERDICT.md
├── AGENT-BOOTSTRAP.md
├── AGENTS.md
├── apps
│   └── web
│       ├── e2e
│       │   └── mission-control.acceptance.spec.ts
│       ├── index.html
│       ├── package.json
│       ├── package-lock.json
│       ├── playwright.config.ts
│       ├── public
│       │   ├── sample-mission-control.fixture.json
│       │   ├── sample-mission-control.json
│       │   ├── sample-read-status.json
│       │   ├── sample-workspace.fixture.json
│       │   └── sample-workspace.json
│       ├── README.md
│       ├── scripts
│       │   ├── smoke.mjs
│       │   ├── test-agent-context-markdown.mjs
│       │   └── test-source-health-web.mjs
│       ├── src
│       │   ├── api
│       │   │   └── liveApi.ts
│       │   ├── App.tsx
│       │   ├── components
│       │   │   ├── LabNav.tsx
│       │   │   ├── LabShell.tsx
│       │   │   ├── LensModeSwitcher.tsx
│       │   │   ├── ProdNav.tsx
│       │   │   ├── ProdShell.tsx
│       │   │   └── ReadStatusPanel.tsx
│       │   ├── hooks
│       │   │   ├── useEstateDiscovery.ts
│       │   │   ├── useLiveAsk.ts
│       │   │   ├── useLiveBrief.ts
│       │   │   ├── useLiveGraph.ts
│       │   │   ├── useLiveIntelligence.ts
│       │   │   ├── useLiveKnowledge.ts
│       │   │   ├── useLiveMissionWorkspace.ts
│       │   │   ├── useLiveRoadmap.ts
│       │   │   ├── useLiveSourceHealth.ts
│       │   │   ├── useLiveTimeMachine.ts
│       │   │   ├── useOpsReceipts.ts
│       │   │   └── useReadStatus.ts
│       │   ├── lib
│       │   │   └── agentContextMarkdown.ts
│       │   ├── main.tsx
│       │   ├── pages
│       │   │   ├── design-lab
│       │   │   │   ├── CartographQuietPage.tsx
│       │   │   │   ├── LedgerDeskPage.tsx
│       │   │   │   ├── SignalRackPage.tsx
│       │   │   │   └── TerminalHonestPage.tsx
│       │   │   ├── HomePage.tsx
│       │   │   └── production
│       │   │       ├── AskPage.tsx
│       │   │       ├── CommandCenterPage.tsx
│       │   │       ├── ContextPage.tsx
│       │   │       ├── DiscoveryPage.tsx
│       │   │       ├── GraphPage.tsx
│       │   │       ├── IntelligencePage.tsx
│       │   │       ├── KnowledgePage.tsx
│       │   │       ├── MissionControlPage.tsx
│       │   │       ├── OpsHealthPage.tsx
│       │   │       ├── ProjectsPage.tsx
│       │   │       ├── RoadmapPage.tsx
│       │   │       ├── SourceHealthPage.tsx
│       │   │       ├── TimeMachinePage.tsx
│       │   │       └── WorkspacePage.tsx
│       │   ├── styles.css
│       │   ├── tokens.css
│       │   ├── types.ts
│       │   └── vite-env.d.ts
│       ├── tsconfig.json
│       ├── tsconfig.node.json
│       └── vite.config.ts
├── atlas-vault-documentation
│   ├── ACCEPTANCE_TESTS.md
│   ├── adapters
│   │   ├── AGENTS.md.fragment
│   │   ├── CLAUDE.md.fragment
│   │   ├── cursor-rule.mdc
│   │   ├── GEMINI.md.fragment
│   │   └── universal-system-prompt.md
│   ├── agent-control
│   │   └── README.md
│   ├── agent_control
│   │   ├── adapter_registry.py
│   │   ├── agent_identity.py
│   │   ├── authority.py
│   │   ├── bootstrap.py
│   │   ├── capability.py
│   │   ├── doctor.py
│   │   ├── event_client.py
│   │   ├── __init__.py
│   │   ├── postflight.py
│   │   ├── preflight.py
│   │   ├── protected_paths.py
│   │   ├── readiness.py
│   │   ├── receipt_gate.py
│   │   ├── repository_gate.py
│   │   ├── session.py
│   │   ├── skill_ack.py
│   │   ├── skill_compiler.py
│   │   ├── skill_loader.py
│   │   ├── spool_sync.py
│   │   └── vault_identity.py
│   ├── AS-CTRL-001-CERTIFICATION.md
│   ├── AS-CTRL-001-CERTIFICATION-RECEIPT.yaml
│   ├── AS-CTRL-001-COMPLETION-REPORT.md
│   ├── AS-SKILL-001-CERTIFICATION.md
│   ├── AS-SKILL-001-CERTIFICATION-RECEIPT.yaml
│   ├── AS-SKILL-001-COMPLETION-REPORT.md
│   ├── AS-WP-003-CERTIFICATION.md
│   ├── AS-WP-004-CERTIFICATION.md
│   ├── AS-WP-004-COMPLETION-REPORT.md
│   ├── AS-WP-005-CERTIFICATION.md
│   ├── ATLAS-DOC-RECEIPT.md
│   ├── config
│   │   ├── agent-readiness.yaml
│   │   ├── agent-registry.yaml
│   │   └── atlas-agent.example.yaml
│   ├── docs
│   │   ├── MDA-CLI-ALIGNMENT.md
│   │   ├── NORMALIZATION.md
│   │   └── THREAT_MODEL.md
│   ├── evidence
│   │   ├── agent-readiness-promoted.yaml
│   │   ├── AS-CTRL-001-concurrency-reconciliation.json
│   │   ├── AS-CTRL-001-managed-launch.json
│   │   ├── AS-SKILL-001-certification-evidence.json
│   │   └── AS-SKILL-001-negative-gates.json
│   ├── examples
│   │   └── raw-event-example.md
│   ├── IMPLEMENTATION_ROADMAP.md
│   ├── internal
│   │   ├── atlas_links.py
│   │   ├── atlas_router.py
│   │   ├── authority_model.py
│   │   ├── content_fingerprint.py
│   │   ├── documentation_conflicts.py
│   │   ├── documentation_coverage.py
│   │   ├── document_classifier.py
│   │   ├── document_inventory.py
│   │   ├── event_reader.py
│   │   ├── frontmatter.py
│   │   ├── generated_regions.py
│   │   ├── graph_confidence.py
│   │   ├── graph_conflicts.py
│   │   ├── graph_deduplication.py
│   │   ├── graph_edge.py
│   │   ├── graph_identity.py
│   │   ├── graphify_discovery.py
│   │   ├── graphify_parser.py
│   │   ├── graphify_schema.py
│   │   ├── graph_ingestion.py
│   │   ├── graph_ingestion_state.py
│   │   ├── graph_node.py
│   │   ├── graph_projection.py
│   │   ├── graph_quarantine.py
│   │   ├── graph_source_linking.py
│   │   ├── graph_validation.py
│   │   ├── ingestion_orchestrator.py
│   │   ├── ingestion_planner.py
│   │   ├── ingestion_projection.py
│   │   ├── ingestion_state.py
│   │   ├── ingestion_validation.py
│   │   ├── __init__.py
│   │   ├── mda_output_contract.py
│   │   ├── normalization.py
│   │   ├── process_runner.py
│   │   ├── project_discovery.py
│   │   ├── project_identity.py
│   │   ├── project_log.py
│   │   ├── project_markers.py
│   │   ├── project_pages.py
│   │   ├── provenance.py
│   │   ├── route_planner.py
│   │   ├── router_validation.py
│   │   ├── routing_state.py
│   │   ├── transaction.py
│   │   ├── trusted_exec.py
│   │   ├── verification.py
│   │   └── work_package_projection.py
│   ├── MDA-STANDARD.md
│   ├── PRP.md
│   ├── README.md
│   ├── references
│   │   ├── AGENT-BOOTSTRAP-CONTRACT.md
│   │   ├── AGENT-CAPABILITY-CONTRACT.md
│   │   ├── AGENT-INTEGRATION.md
│   │   ├── AGENT-READINESS-CONTRACT.md
│   │   ├── AGENT-SESSION-CONTRACT.md
│   │   ├── ATLAS-DOCUMENTATION-CONTRACT.md
│   │   ├── DOCUMENTATION-COVERAGE-CONTRACT.md
│   │   ├── DOCUMENTATION-ENFORCEMENT-CONTRACT.md
│   │   ├── DOCUMENT-CLASSIFICATION-CONTRACT.md
│   │   ├── DOCUMENT-INVENTORY-CONTRACT.md
│   │   ├── EVENT-TAXONOMY.md
│   │   ├── FRONTMATTER-SCHEMA.md
│   │   ├── GRAPH-IDENTITY-CONTRACT.md
│   │   ├── GRAPHIFY-ADAPTER-CONTRACT.md
│   │   ├── GRAPH-QUARANTINE-CONTRACT.md
│   │   ├── GRAPH-SOURCE-LINK-CONTRACT.md
│   │   ├── GRAPH-VALIDATION-CONTRACT.md
│   │   ├── INGESTION-RECEIPT-CONTRACT.md
│   │   ├── JSON-OUTPUT-CONTRACT.md
│   │   ├── MDA-CLI-INTEGRATION.md
│   │   ├── PROJECT-DISCOVERY-CONTRACT.md
│   │   ├── PROVENANCE.md
│   │   ├── RELATIONSHIP-AUTHORITY-CONTRACT.md
│   │   ├── SKILL-DISTRIBUTION-CONTRACT.md
│   │   ├── SOURCE-AUTHORITY-CONTRACT.md
│   │   ├── SUPERVISED-AGENT-CONTRACT.md
│   │   ├── VAULT-IDENTITY-CONTRACT.md
│   │   └── VAULT-PATH-MAPPING.md
│   ├── schemas
│   │   ├── agent-adapter-registry.schema.json
│   │   ├── agent-adapter.schema.json
│   │   ├── agent-readiness.schema.json
│   │   ├── agent-receipt.schema.json
│   │   ├── agent-session.schema.json
│   │   ├── documentation-coverage.schema.json
│   │   ├── document-inventory.schema.json
│   │   ├── graph-edge-record.schema.json
│   │   ├── graphify-artifact.schema.json
│   │   ├── graph-ingestion-receipt.schema.json
│   │   ├── graph-ingestion-state.schema.json
│   │   ├── graph-node-record.schema.json
│   │   ├── graph-quarantine-record.schema.json
│   │   ├── ingestion-plan.schema.json
│   │   ├── ingestion-receipt.schema.json
│   │   ├── ingestion-state.schema.json
│   │   ├── project-record.schema.json
│   │   ├── relationship-record.schema.json
│   │   ├── skill-acknowledgement.schema.json
│   │   └── skill-manifest.schema.json
│   ├── scripts
│   │   ├── atlas_agent.py
│   │   ├── atlas_config.py
│   │   ├── benchmark_graphify.py
│   │   ├── benchmark_ingestion.py
│   │   ├── capture_event.py
│   │   ├── check_documentation.py
│   │   ├── discover_projects.py
│   │   ├── document_work.py
│   │   ├── ingest_graphify.py
│   │   ├── ingest_project.py
│   │   ├── inspect_graphify.py
│   │   ├── install_agent_instructions.py
│   │   ├── install-skill.ps1
│   │   ├── install-skill.sh
│   │   ├── inventory_project.py
│   │   ├── normalize_event.py
│   │   ├── rebuild_project.py
│   │   ├── rebuild_relationships.py
│   │   ├── route_event.py
│   │   ├── run_ctrl_certification.py
│   │   ├── run_skill_certification.py
│   │   ├── validate_agent_session.py
│   │   ├── validate_graphify.py
│   │   ├── validate_ingestion.py
│   │   └── validate_routes.py
│   ├── skill
│   │   ├── skill-manifest.yaml
│   │   ├── SKILL.md
│   │   └── skill.sha256
│   ├── SKILL.md
│   ├── skills
│   │   ├── atlas-golden-estate-curator
│   │   │   ├── curator.py
│   │   │   ├── examples
│   │   │   │   ├── discover-only.json
│   │   │   │   └── owner-gate-denied.json
│   │   │   ├── README.md
│   │   │   ├── references
│   │   │   │   ├── PHASES.md
│   │   │   │   ├── QUALIFICATION.md
│   │   │   │   ├── SAFETY.md
│   │   │   │   └── WINDOWS-D-DRIVE.md
│   │   │   ├── SKILL.md
│   │   │   ├── skill.sha256
│   │   │   ├── skill.yaml
│   │   │   └── tests
│   │   │       ├── conftest.py
│   │   │       ├── estate.py
│   │   │       ├── test_adversarial.py
│   │   │       ├── test_discover_readonly.py
│   │   │       ├── test_inventory_honesty.py
│   │   │       ├── test_qualify_depth.py
│   │   │       ├── test_skill_schema.py
│   │   │       └── test_windows_remediation.py
│   │   └── atlas-governed-work
│   │       ├── agents
│   │       │   └── openai.yaml
│   │       ├── COMMANDS.md
│   │       ├── EVENT-TYPES.md
│   │       ├── examples
│   │       │   ├── completion-event.json
│   │       │   ├── implementation-event.json
│   │       │   ├── offline-session.md
│   │       │   └── validation-event.json
│   │       ├── FAILURE-RECOVERY.md
│   │       ├── RECEIPT-CONTRACT.md
│   │       ├── references
│   │       │   └── api_reference.md
│   │       ├── SKILL.md
│   │       ├── skill.sha256
│   │       ├── skill.yaml
│   │       └── tests
│   │           └── capability-scenarios.yaml
│   ├── START_HERE_AGENT_PROMPT.md
│   ├── templates
│   │   ├── documentation-receipt.md
│   │   ├── project-log-entry.md
│   │   ├── raw-event.md
│   │   └── work-package-update.md
│   ├── tests
│   │   ├── conftest.py
│   │   ├── fixtures
│   │   │   ├── bin
│   │   │   │   └── mda
│   │   │   ├── project-atlas
│   │   │   │   ├── archive.pdf
│   │   │   │   ├── credentials.json
│   │   │   │   ├── docs
│   │   │   │   │   ├── ARCHITECTURE.md
│   │   │   │   │   ├── roadmap.md
│   │   │   │   │   └── VALIDATION_REPORT.md
│   │   │   │   ├── graphify-out
│   │   │   │   │   └── graph.json
│   │   │   │   └── README.md
│   │   │   ├── projects
│   │   │   │   ├── documentation-rich
│   │   │   │   │   ├── ARCHITECTURE.md
│   │   │   │   │   ├── DEPLOYMENT.md
│   │   │   │   │   ├── docs
│   │   │   │   │   │   ├── decisions
│   │   │   │   │   │   │   └── ADR-001.md
│   │   │   │   │   │   ├── operations
│   │   │   │   │   │   │   └── RUNBOOK.md
│   │   │   │   │   │   └── work-packages
│   │   │   │   │   │       └── WP-001.md
│   │   │   │   │   ├── pyproject.toml
│   │   │   │   │   ├── README.md
│   │   │   │   │   ├── REQUIREMENTS.md
│   │   │   │   │   ├── ROADMAP.md
│   │   │   │   │   ├── SECURITY.md
│   │   │   │   │   ├── VALIDATION_REPORT.md
│   │   │   │   │   └── WORKLOG.md
│   │   │   │   ├── graphify-present
│   │   │   │   │   ├── ARCHITECTURE.md
│   │   │   │   │   ├── graphify-out
│   │   │   │   │   │   ├── edges.jsonl
│   │   │   │   │   │   ├── graph.json
│   │   │   │   │   │   ├── metadata.yaml
│   │   │   │   │   │   └── nodes.jsonl
│   │   │   │   │   └── README.md
│   │   │   │   ├── mixed-formats
│   │   │   │   │   ├── architecture.pdf
│   │   │   │   │   ├── archive.zip
│   │   │   │   │   ├── config.yaml
│   │   │   │   │   ├── credentials.json
│   │   │   │   │   ├── diagram.png
│   │   │   │   │   ├── metadata.json
│   │   │   │   │   ├── notes.txt
│   │   │   │   │   ├── README.md
│   │   │   │   │   └── secrets.pem
│   │   │   │   ├── monorepo
│   │   │   │   │   ├── apps
│   │   │   │   │   │   ├── api
│   │   │   │   │   │   │   ├── pyproject.toml
│   │   │   │   │   │   │   └── README.md
│   │   │   │   │   │   └── web
│   │   │   │   │   │       ├── package.json
│   │   │   │   │   │       └── README.md
│   │   │   │   │   ├── docs
│   │   │   │   │   │   └── ARCHITECTURE.md
│   │   │   │   │   ├── package.json
│   │   │   │   │   ├── packages
│   │   │   │   │   │   └── shared
│   │   │   │   │   │       ├── package.json
│   │   │   │   │   │       └── README.md
│   │   │   │   │   └── README.md
│   │   │   │   └── sparse-readme
│   │   │   │       ├── package.json
│   │   │   │       └── README.md
│   │   │   └── secret-event-input.txt
│   │   ├── test_agent_control.py
│   │   ├── test_atlas_config.py
│   │   ├── test_capture_event.py
│   │   ├── test_check_documentation.py
│   │   ├── test_graph_ingestion.py
│   │   ├── test_ingestion.py
│   │   ├── test_ingestion_stage2.py
│   │   ├── test_internal.py
│   │   ├── test_mda_output_contract_r1.py
│   │   ├── test_normalize_event.py
│   │   ├── test_router.py
│   │   ├── test_sec_015_016_019_authority.py
│   │   └── test_sec021_trusted_exec.py
│   └── VALIDATION_REPORT.md
├── CLAUDE.md
├── CODE_OF_CONDUCT.md
├── CONTRIBUTING.md
├── deps
│   ├── integrity.json
│   └── README.md
├── docs
│   ├── acceptance-test.md
│   ├── adr
│   │   ├── ADR-001-wp001-foundation-decisions.md
│   │   ├── ADR-002-atlas-two-track-reconciliation.md
│   │   ├── ADR-003-agent-event-ingestion-contract.md
│   │   ├── ADR-004-source-quarantine-prompt-injection-boundary.md
│   │   ├── ADR-005-mvp-portfolio-intelligence-pilot-onboarding.md
│   │   ├── ADR-006-github-repository-governance-baseline.md
│   │   ├── ADR-007-claim-identity-v2-canonicalization.md
│   │   ├── ADR-008-atlas-web-application.md
│   │   ├── ADR-009-web-design-tokens.md
│   │   ├── ADR-010-atlas-web-ux.md
│   │   ├── ADR-025-research-workspace-prep.md
│   │   ├── ADR-028-reality-gap-prep.md
│   │   ├── ADR-031-adv-pool-prep.md
│   │   ├── ADR-032-derived-intelligence-is-not-authority.md
│   │   └── ADR-033-phase2a-specification-backed-work-origination.md
│   ├── agent-event-ingestion-contract.md
│   ├── agent-event-ingestion-plan.md
│   ├── architecture
│   │   └── AS-OBSIDIAN-CAPTURE-001-architecture-source.md
│   ├── architecture-governance
│   │   ├── MERGE-GATE-MECHANICS.md
│   │   └── VERIFY-AS-RET-SEQUENCING-DECISION.md
│   ├── AS-2.0-AGENT-EVAL-001.md
│   ├── AS-2.0-AGENTOS-001.md
│   ├── AS-2.0-AGENTOS-002.md
│   ├── AS-2.0-API-001.md
│   ├── AS-2.0-AUTONOMY-001.md
│   ├── AS-2.0-CHATGPT-CAPTURE-001.md
│   ├── AS-2.0-COLLAB-001.md
│   ├── AS-2.0-COMPAT-001.md
│   ├── AS-2.0-CTX-001.md
│   ├── AS-2.0-CTX-002.md
│   ├── AS-2.0-ESTATE-INTEL-001.md
│   ├── AS-2.0-FED-001.md
│   ├── AS-2.0-FED-002.md
│   ├── AS-2.0-FINAL-CERT-PILOT-WAIVER.md
│   ├── AS-2.0-INBOX-001.md
│   ├── AS-2.0-KCI-001.md
│   ├── AS-2.0-KCI-HARNESS-001.md
│   ├── AS-2.0-MCP-001.md
│   ├── AS-2.0-OAI-IMPORT-001.md
│   ├── AS-2.0-OAI-IMPORT-002.md
│   ├── AS-2.0-OBS-UX-001.md
│   ├── AS-2.0-OBS-UX-002.md
│   ├── AS-2.0-PROV-001.md
│   ├── AS-2.0-REALITY-GAP-001.md
│   ├── AS-2.0-REALITY-GAP-UI-001.md
│   ├── AS-2.0-RET-HYBRID-001.md
│   ├── AS-2.0-SCALE-001.md
│   ├── AS-2.0-SCHED-001.md
│   ├── AS-2.0-SEC-001.md
│   ├── AS-2.0-SEC-ADV-001.md
│   ├── AS-2.0-SYNC-001.md
│   ├── AS-2.0-TEMPORAL-001.md
│   ├── AS-2.0-TWIN-001.md
│   ├── AS-2.0-TWIN-FIXTURE-001.md
│   ├── AS-2.0-TWIN-FIXTURE-002.md
│   ├── AS-2.0-UX-001.md
│   ├── AS-2.0-UX-002.md
│   ├── AS-2.0-WEB-ASK-001.md
│   ├── AS-2.0-WEB-SURFACE-001.md
│   ├── AS-2.1-AUTONOMY-L3-001.md
│   ├── AS-2.1-CHATGPT-BRIDGE-001.md
│   ├── AS-2.1-COLLAB-001.md
│   ├── AS-2.1-OAI-RESPONSES-POC-001.md
│   ├── AS-2.1-PROV-LIVE-001.md
│   ├── AS-2.1-WEB-ACTIONS-001.md
│   ├── AS-2.1-WEB-LIVE-001.md
│   ├── AS-2.2-EVAL-001.md
│   ├── AS-2.2-MEM-GOV-001.md
│   ├── AS-2.2-REALITY-LIVE-001.md
│   ├── AS-2.2-RESEARCH-001.md
│   ├── AS-ADV-CLEAN-CLONE-REHEARSAL.md
│   ├── AS-ADV-RELEASE-001-package.md
│   ├── AS-ADV-RELEASE-002-clean-clone.md
│   ├── AS-ADV-RELEASE-003-perf-determinism.md
│   ├── AS-ADV-RELEASE-004-migration-recovery.md
│   ├── AS-ADV-RELEASE-MATRIX.md
│   ├── AS-BACKUP-001-verified-snapshot.md
│   ├── AS-CODER-ALPHA-CONNECT-PERF-001.md
│   ├── AS-CODER-ALPHA-CONTEXT-FRESHNESS-ADV-001.md
│   ├── AS-CODER-ALPHA-DEMO-READINESS-001.md
│   ├── AS-CODER-ALPHA-FRESH-AGENT-CHALLENGE-V2.md
│   ├── AS-CODER-ALPHA-INBOX-LIST-001.md
│   ├── AS-CODER-ALPHA-INCREMENTAL-CONNECT-001.md
│   ├── AS-CODER-ALPHA-OBSIDIAN-R1-PROJECTION-001.md
│   ├── AS-CODER-ALPHA-SOURCE-HEALTH-API-001.md
│   ├── AS-CODER-ALPHA-SOURCE-HEALTH-WEB-001.md
│   ├── AS-CODER-ALPHA-WORKFLOW-METRICS-001.md
│   ├── AS-CORE-002-plan.md
│   ├── AS-CORE-002-post-merge.md
│   ├── AS-CORE-002-remediation.md
│   ├── AS-CORE-002-source-lifecycle-erratum.md
│   ├── AS-CORE-003-claim-identity-amendment.md
│   ├── AS-CORE-003-plan.md
│   ├── AS-CORE-006-authority.md
│   ├── AS-CORE-007-knowledge-query.md
│   ├── AS-CORE-008-subject-multifield-query.md
│   ├── AS-EXPLAIN-001-explain-receipts.md
│   ├── AS-EXPLAIN-001-graph-sidecars.md
│   ├── AS-GRAPH-001-graph-artifact-acceptance.md
│   ├── AS-GRAPH-002-entity-resolution.md
│   ├── AS-GRAPH-003-relationship-store.md
│   ├── AS-GRAPH-004-quarantine-health.md
│   ├── AS-GRAPH-005-graph-projections.md
│   ├── AS-ID-001-governor-remediation.md
│   ├── AS-ID-001-plan.md
│   ├── AS-INCR-COMPILE-001-compile-cache.md
│   ├── AS-INT-001-post-merge.md
│   ├── AS-INT-009-retention-policy.md
│   ├── AS-INT-011-receipt-revocation.md
│   ├── AS-INT-012-schema-compat.md
│   ├── AS-J-005-impact-graph.md
│   ├── AS-KF2-002.md
│   ├── AS-KF2-WAVE1.md
│   ├── AS-LANE-Y-001-docs-reconciliation.md
│   ├── AS-OBS-002-operator-guide.md
│   ├── AS-OBS-002-ops-events.md
│   ├── AS-OBS-003-operator-guide.md
│   ├── AS-OBS-003-ops-report.md
│   ├── AS-OBSIDIAN-CAPTURE-001-conversational-capture.md
│   ├── AS-OBSIDIAN-CAPTURE-001-verifier-packet.md
│   ├── AS-OPT-GATE-001.md
│   ├── AS-ORCH-AUTONOMOUS-MISSION-RECONCILER-001.md
│   ├── AS-ORCH-CONTINUATION-BROKER-001.md
│   ├── AS-ORCH-DURABLE-LEASE-PROJECTION-001.md
│   ├── AS-ORCH-NONBLOCKING-SCHEDULER-LIVENESS-001.md
│   ├── AS-ORCH-SELF-WAKE-RESIDENT-DRIVER-001.md
│   ├── AS-PILOT-FIXTURE-ONLY-WAIVER.md
│   ├── AS-QUERY-001-list-kinds.md
│   ├── AS-QUERY-DIAG-001-query-outcome-diagnostics.md
│   ├── AS-QUERY-MULTI-001-query-plans.md
│   ├── AS-SEC-CONT-001-fixture-gates.md
│   ├── AS-SEC-CONT-002-fixture-deepen.md
│   ├── AS-SEC-CONT-MATRIX.md
│   ├── AS-SYNC-001-SCAFFOLD.md
│   ├── AS-SYNC-002-SCAFFOLD.md
│   ├── AS-SYNC-003-SCAFFOLD.md
│   ├── AS-SYNC-004-SCAFFOLD.md
│   ├── AS-TASK-CONTEXT-AND-CONTINUITY-001.md
│   ├── AS-VAL-001-freshness-orphan.md
│   ├── AS-WEB-ACCEPT-001-checklist.md
│   ├── AS-WEB-ACCEPT-005-governor-evidence.md
│   ├── AS-WEB-ACCEPT-GOVERNOR-SIGNOFF.md
│   ├── AS-XPROJ-001-global-entities.md
│   ├── AS-XPROJ-002-cross-project-edges.md
│   ├── AS-XPROJ-003-duplicate-detection.md
│   ├── AS-XPROJ-004-conflict-indexes.md
│   ├── atlas-2.0
│   │   ├── AGENT-ELIGIBLE-INVENTORY.md
│   │   ├── AGENT-OS.md
│   │   ├── ARCHITECTURE.md
│   │   ├── CHARTER.md
│   │   ├── COMPATIBILITY.md
│   │   ├── CONTEXT.md
│   │   ├── CONTRACT-FREEZE-CHECKLIST.md
│   │   ├── DAG-FREEZE-DRAFT.md
│   │   ├── DAG.md
│   │   ├── DIGITAL-TWIN.md
│   │   ├── FIXTURE-PLAN.md
│   │   ├── fixtures
│   │   │   ├── openai-importer
│   │   │   │   ├── expected-fixture-receipt.json
│   │   │   │   ├── README.md
│   │   │   │   └── sample-chat-export.md
│   │   │   ├── README.md
│   │   │   ├── reality-gap
│   │   │   │   ├── inventory.fixture.json
│   │   │   │   └── README.md
│   │   │   └── twin-projection
│   │   │       ├── README.md
│   │   │       └── sample-projection.json
│   │   ├── IMPLEMENTATION-READY-GATE.md
│   │   ├── KCI.md
│   │   ├── MCP-API-DRAFTS.md
│   │   ├── MIGRATION-STRATEGY.md
│   │   ├── OBSIDIAN-2.0.md
│   │   ├── OPENAI-MCP-DESIGN.md
│   │   ├── OPEN-QUESTIONS.md
│   │   ├── PACKAGE-CONTRACT-STUBS.md
│   │   ├── PERFORMANCE-BUDGETS.md
│   │   ├── PRD.md
│   │   ├── PROTOTYPE-MARKERS.md
│   │   ├── prototypes
│   │   │   ├── AGENT-OS-SESSION-PROTOTYPE.md
│   │   │   ├── DIGITAL-TWIN-DASHBOARD-PROTOTYPE.md
│   │   │   ├── README.md
│   │   │   ├── REVIEW-WALKTHROUGH-PROTOTYPE.md
│   │   │   └── UX-COMMAND-CENTER-WIREFRAME-PROTOTYPE.md
│   │   ├── README.md
│   │   ├── REALITY-GAP.md
│   │   ├── SCHEMA-API-DRAFTS.md
│   │   ├── TEST-STRATEGY.md
│   │   ├── THREAT-MODEL.md
│   │   ├── VISION.md
│   │   └── Z-WAVE-INDEX.md
│   ├── atlas-2.1
│   │   ├── ADV-LIVE-SUITE.md
│   │   ├── CHARTER.md
│   │   ├── DAG.md
│   │   ├── FEATURE-MATURITY-MATRIX.md
│   │   ├── KNOWN-GAPS.md
│   │   ├── OBS-PERF.md
│   │   ├── PACKAGE-BOARD.md
│   │   ├── PRODUCTIONIZATION-AUDIT.md
│   │   ├── README.md
│   │   └── THREAT-MODEL-DELTA.md
│   ├── atlas-2.2
│   │   ├── adr
│   │   │   ├── ADR-2.2-001-context-compiler-pipeline.md
│   │   │   ├── ADR-2.2-DOD-001-dod-compiler-prep.md
│   │   │   └── ADR-2.2-MEM-GOV-001-governed-agent-memory.md
│   │   ├── adv-pool
│   │   │   ├── ADV-MATRIX.md
│   │   │   ├── FIXTURE-INVARIANTS.md
│   │   │   ├── fixtures
│   │   │   │   └── README.md
│   │   │   └── README.md
│   │   ├── AS-2.2-DOD-COMPILER-001.md
│   │   ├── AS-2.2-KCI-ENGINE-PREP-001.md
│   │   ├── AS-2.2-PREP-FIXTURE-ROLLUP-001.md
│   │   ├── AS-2.2-RET-HYBRID-001.md
│   │   ├── AS-2.2-TIME-MACHINE-001.md
│   │   ├── ask-atlas-2
│   │   │   ├── adr
│   │   │   │   └── ADR-2.2-ASK2-001-answer-lens-deepen-prep.md
│   │   │   ├── ARCHITECTURE.md
│   │   │   ├── AS-2.2-ASK2-DEEPEN-PREP-001.md
│   │   │   ├── CONTRACT.md
│   │   │   ├── contracts
│   │   │   │   ├── ask2-citation-chain.schema.json
│   │   │   │   ├── ask2-deepen-answer-view.schema.json
│   │   │   │   ├── ask2-forbidden-action.schema.json
│   │   │   │   └── ask2-lens-projection.schema.json
│   │   │   ├── FIXTURE-PLAN.md
│   │   │   ├── fixtures
│   │   │   │   ├── citation-chain.sample.json
│   │   │   │   ├── deepen-answer-complete.sample.json
│   │   │   │   ├── lens-projection-web.sample.json
│   │   │   │   ├── negative-canonical-write.expect.json
│   │   │   │   ├── negative-live-mutate.expect.json
│   │   │   │   └── negative-llm-authority.expect.json
│   │   │   └── INVARIANTS.md
│   │   ├── benchmarks
│   │   │   ├── cases
│   │   │   │   ├── BM-RET2-001-lexical-exact.json
│   │   │   │   ├── BM-RET2-002-lexical-prefix.json
│   │   │   │   ├── BM-RET2-003-semantic-fail-closed.json
│   │   │   │   └── BM-RET2-004-fusion-preserve-lexical.json
│   │   │   └── README.md
│   │   ├── CHARTER.md
│   │   ├── chatgpt-live
│   │   │   ├── adr
│   │   │   │   ├── ADR-2.2-CHATGPT-LIVE-001-quarantine-first-live-bridge-deepen-prep.md
│   │   │   │   └── ADR-2.2-CHATGPT-LIVE-001-quarantine-first-live-bridge-prep.md
│   │   │   ├── ARCHITECTURE.md
│   │   │   ├── AS-2.2-CHATGPT-LIVE-DEEPEN-PREP-001.md
│   │   │   ├── AS-2.2-CHATGPT-LIVE-PREP-001.md
│   │   │   ├── CONTRACT.md
│   │   │   ├── contracts
│   │   │   │   ├── chatgpt-live-deepen-forbidden-action.schema.json
│   │   │   │   ├── forbidden-action.schema.json
│   │   │   │   ├── live-bridge-request.schema.json
│   │   │   │   ├── live-session-receipt.schema.json
│   │   │   │   └── quarantine-envelope.schema.json
│   │   │   ├── FIXTURE-PLAN.md
│   │   │   ├── fixtures
│   │   │   │   ├── live-bridge-request.sample.json
│   │   │   │   ├── live-session-quarantined.sample.json
│   │   │   │   ├── negative-billing-without-opt-in.expect.json
│   │   │   │   ├── negative-bypass-quarantine-deepen.expect.json
│   │   │   │   ├── negative-bypass-quarantine.expect.json
│   │   │   │   ├── negative-default-on-live.expect.json
│   │   │   │   ├── negative-env-force-live.expect.json
│   │   │   │   ├── negative-layer-b-write.expect.json
│   │   │   │   ├── negative-llm-authority.expect.json
│   │   │   │   ├── negative-pilot-invent.expect.json
│   │   │   │   ├── negative-release-cert-stamp.expect.json
│   │   │   │   └── quarantine-envelope.sample.json
│   │   │   └── INVARIANTS.md
│   │   ├── compat-pin
│   │   │   ├── adr
│   │   │   │   ├── ADR-2.2-COMPAT-PIN-001-2.1-anchor-deepen-prep.md
│   │   │   │   └── ADR-2.2-COMPAT-PIN-001-2.1-anchor-prep.md
│   │   │   ├── ARCHITECTURE.md
│   │   │   ├── AS-2.2-COMPAT-PIN-DEEPEN-PREP-001.md
│   │   │   ├── AS-2.2-COMPAT-PIN-PREP-001.md
│   │   │   ├── CONTRACT.md
│   │   │   ├── contracts
│   │   │   │   ├── compat-pin-expectation.schema.json
│   │   │   │   ├── compat-pin-forbidden-action.schema.json
│   │   │   │   ├── compat-pin-scenario.schema.json
│   │   │   │   └── README.md
│   │   │   ├── FIXTURE-PLAN.md
│   │   │   ├── fixtures
│   │   │   │   ├── compat-expectation.fixture.json
│   │   │   │   ├── negative-deepen-anchor-publish.expect.json
│   │   │   │   ├── negative-deepen-future-pin-as-live.expect.json
│   │   │   │   ├── negative-deepen-pilot-invent.expect.json
│   │   │   │   ├── negative-deepen-release-cert-stamp.expect.json
│   │   │   │   ├── negative-deepen-runtime-mutation.expect.json
│   │   │   │   ├── negative-pilot-invent.expect.json
│   │   │   │   ├── negative-release-certified.expect.json
│   │   │   │   └── README.md
│   │   │   ├── INVARIANTS.md
│   │   │   └── README.md
│   │   ├── conflict-ux
│   │   │   ├── adr
│   │   │   │   ├── ADR-2.2-CONFLICT-UX-001-review-cockpit.md
│   │   │   │   └── ADR-2.2-CONFLICT-UX-002-deepen-prep.md
│   │   │   ├── ARCHITECTURE.md
│   │   │   ├── AS-2.2-CONFLICT-UX-DEEPEN-PREP-001.md
│   │   │   ├── AS-2.2-CONFLICT-UX-PREP-001.md
│   │   │   ├── CONTRACT.md
│   │   │   ├── contracts
│   │   │   │   ├── conflict-cockpit-view.schema.json
│   │   │   │   ├── conflict-projection-card.schema.json
│   │   │   │   ├── conflict-ux-forbidden-action.schema.json
│   │   │   │   ├── disposition-action.schema.json
│   │   │   │   └── review-queue-slice.schema.json
│   │   │   ├── DEEPEN-FIXTURE-PLAN.md
│   │   │   ├── FIXTURE-PLAN.md
│   │   │   ├── fixtures
│   │   │   │   ├── cockpit-open-conflict.sample.json
│   │   │   │   ├── negative-authority-elevation.expect.json
│   │   │   │   ├── negative-auto-resolve.expect.json
│   │   │   │   ├── negative-llm-authority.expect.json
│   │   │   │   ├── negative-pilot-invent.expect.json
│   │   │   │   ├── negative-release-cert-stamp.expect.json
│   │   │   │   ├── negative-ui-write.expect.json
│   │   │   │   ├── projection-card-duplicate-source.sample.json
│   │   │   │   └── review-queue-slice.sample.json
│   │   │   └── INVARIANTS.md
│   │   ├── contracts
│   │   │   ├── ctx-compiler
│   │   │   │   ├── context-compiler-package.schema.json
│   │   │   │   ├── context-compiler-request.schema.json
│   │   │   │   ├── context-item.schema.json
│   │   │   │   └── README.md
│   │   │   ├── dod-compiler
│   │   │   │   ├── dod-criterion.schema.json
│   │   │   │   ├── dod-definition.schema.json
│   │   │   │   ├── dod-evidence-ref.schema.json
│   │   │   │   ├── dod-goal.schema.json
│   │   │   │   ├── dod-proof-receipt.schema.json
│   │   │   │   ├── dod-test-binding.schema.json
│   │   │   │   └── README.md
│   │   │   ├── mem-gov
│   │   │   │   ├── agent-memory-expiry.schema.json
│   │   │   │   ├── agent-memory-index.schema.json
│   │   │   │   ├── agent-memory-provenance.schema.json
│   │   │   │   ├── agent-memory-record.schema.json
│   │   │   │   ├── agent-memory-revocation.schema.json
│   │   │   │   ├── agent-memory-supersession.schema.json
│   │   │   │   └── README.md
│   │   │   ├── reality-live
│   │   │   │   ├── README.md
│   │   │   │   ├── reality-live-gap-report.schema.draft.json
│   │   │   │   └── reality-live-planes.schema.draft.json
│   │   │   └── research
│   │   │       ├── ask-atlas-2-answer.schema.json
│   │   │       ├── research-conflict.schema.json
│   │   │       ├── research-evidence-pack.schema.json
│   │   │       ├── research-evidence-ref.schema.json
│   │   │       ├── research-hypothesis.schema.json
│   │   │       ├── research-question.schema.json
│   │   │       └── research-synthesis.schema.json
│   │   ├── ctx-compiler
│   │   │   ├── adr
│   │   │   │   └── ADR-2.2-CTX-002-context-compiler-deepen-prep.md
│   │   │   ├── ARCHITECTURE.md
│   │   │   ├── AS-2.2-CTX-DEEPEN-PREP-001.md
│   │   │   ├── CONTRACT.md
│   │   │   ├── contracts
│   │   │   │   └── ctx-forbidden-action.schema.json
│   │   │   ├── FIXTURE-PLAN.md
│   │   │   ├── fixtures
│   │   │   │   ├── negative-budget-invent.expect.json
│   │   │   │   ├── negative-layer-b-write.expect.json
│   │   │   │   └── negative-llm-authority.expect.json
│   │   │   ├── INVARIANTS.md
│   │   │   ├── PROFILES.md
│   │   │   └── README.md
│   │   ├── doc-charter
│   │   │   ├── adr
│   │   │   │   ├── ADR-2.2-DOC-CHARTER-001-charter-maturity-deepen-prep.md
│   │   │   │   └── ADR-2.2-DOC-CHARTER-001-charter-maturity-prep.md
│   │   │   ├── ARCHITECTURE.md
│   │   │   ├── AS-2.2-DOC-CHARTER-DEEPEN-PREP-001.md
│   │   │   ├── AS-2.2-DOC-CHARTER-MATRIX-SYNC-001.md
│   │   │   ├── AS-2.2-DOC-CHARTER-PREP-001.md
│   │   │   ├── CONTRACT.md
│   │   │   ├── contracts
│   │   │   │   ├── charter-maturity-matrix.schema.json
│   │   │   │   ├── charter-maturity-row.schema.json
│   │   │   │   └── doc-charter-forbidden-action.schema.json
│   │   │   ├── FEATURE-MATURITY-MATRIX.md
│   │   │   ├── FIXTURE-PLAN.md
│   │   │   ├── fixtures
│   │   │   │   ├── maturity-matrix.fixture.json
│   │   │   │   ├── negative-deepen-llm-authority.expect.json
│   │   │   │   ├── negative-deepen-matrix-cert-promotion.expect.json
│   │   │   │   ├── negative-deepen-pilot-invent.expect.json
│   │   │   │   ├── negative-deepen-release-cert-stamp.expect.json
│   │   │   │   ├── negative-deepen-runtime-mutation.expect.json
│   │   │   │   ├── negative-deepen-unlock-stamp.expect.json
│   │   │   │   ├── negative-pilot-invent.expect.json
│   │   │   │   └── negative-release-certified.expect.json
│   │   │   └── INVARIANTS.md
│   │   ├── dod-compiler
│   │   │   ├── adr
│   │   │   │   └── ADR-2.2-DOD-002-dod-compiler-deepen-prep.md
│   │   │   ├── ARCHITECTURE.md
│   │   │   ├── AS-2.2-DOD-DEEPEN-PREP-001.md
│   │   │   ├── CONTRACT.md
│   │   │   ├── contracts
│   │   │   │   └── dod-forbidden-action.schema.json
│   │   │   ├── FIXTURE-PLAN.md
│   │   │   ├── fixtures
│   │   │   │   ├── negative-invented-pass.expect.json
│   │   │   │   ├── negative-layer-b-promotion.expect.json
│   │   │   │   ├── negative-llm-authority.expect.json
│   │   │   │   └── negative-pilot-invent.expect.json
│   │   │   ├── INVARIANTS.md
│   │   │   ├── README.md
│   │   │   └── THREAT-ROWS.md
│   │   ├── estate-ops
│   │   │   ├── adr
│   │   │   │   ├── ADR-2.2-ESTATE-OPS-001-estate-ops-lens-deepen-prep.md
│   │   │   │   └── ADR-2.2-ESTATE-OPS-001-estate-ops-lens-prep.md
│   │   │   ├── ARCHITECTURE.md
│   │   │   ├── AS-2.2-ESTATE-OPS-DEEPEN-PREP-001.md
│   │   │   ├── AS-2.2-ESTATE-OPS-PREP-001.md
│   │   │   ├── CONTRACT.md
│   │   │   ├── contracts
│   │   │   │   ├── estate-ops-action.schema.json
│   │   │   │   ├── estate-ops-cockpit-view.schema.json
│   │   │   │   ├── estate-ops-forbidden-action.schema.json
│   │   │   │   ├── mission-control-lens.schema.json
│   │   │   │   └── ops-health-receipt.schema.json
│   │   │   ├── FIXTURE-PLAN.md
│   │   │   ├── fixtures
│   │   │   │   ├── cockpit-estate-selected.sample.json
│   │   │   │   ├── mission-control-lens.sample.json
│   │   │   │   ├── negative-deepen-llm-authority.expect.json
│   │   │   │   ├── negative-deepen-ops-runtime-mutation.expect.json
│   │   │   │   ├── negative-deepen-pilot-invent.expect.json
│   │   │   │   ├── negative-deepen-ui-canonical-write.expect.json
│   │   │   │   ├── negative-deepen-unknown-as-healthy.expect.json
│   │   │   │   ├── negative-pilot-invent.expect.json
│   │   │   │   ├── negative-ui-canonical-write.expect.json
│   │   │   │   ├── negative-unknown-as-healthy.expect.json
│   │   │   │   └── ops-health-receipt.sample.json
│   │   │   └── INVARIANTS.md
│   │   ├── FIXTURE-PLAN.md
│   │   ├── fixtures
│   │   │   ├── ctx-compiler
│   │   │   │   ├── conflict-filter.request.json
│   │   │   │   ├── expected-budget-fail.json
│   │   │   │   ├── expected-conflict-package.json
│   │   │   │   ├── expected-estate-invent-fail.json
│   │   │   │   ├── expected-package-developer.json
│   │   │   │   ├── negative-budget-overflow.request.json
│   │   │   │   ├── negative-estate-invent.request.json
│   │   │   │   ├── README.md
│   │   │   │   └── task-developer.request.json
│   │   │   ├── dod-compiler
│   │   │   │   ├── expected-proof-fail-evidence-class.json
│   │   │   │   ├── expected-proof-fail-unknown-criterion.json
│   │   │   │   ├── expected-proof-incomplete.json
│   │   │   │   ├── expected-proof-pass.json
│   │   │   │   ├── README.md
│   │   │   │   ├── sample-dod-chain.json
│   │   │   │   └── sample-goal.json
│   │   │   ├── hybrid-retrieval
│   │   │   │   ├── fusion-order.sketch.json
│   │   │   │   ├── plan-exact.sample.json
│   │   │   │   ├── plan-prefix.sample.json
│   │   │   │   ├── README.md
│   │   │   │   └── semantic-disabled.expect.json
│   │   │   ├── kci-engine
│   │   │   │   └── README.md
│   │   │   ├── mem-gov
│   │   │   │   ├── active-memory.json
│   │   │   │   ├── expiry-as-of-before.json
│   │   │   │   ├── expiry-as-of-past.json
│   │   │   │   ├── memory-index.json
│   │   │   │   ├── provenance-only.json
│   │   │   │   ├── README.md
│   │   │   │   ├── revocation-event.json
│   │   │   │   ├── revoked-memory.json
│   │   │   │   ├── superseded-prior.json
│   │   │   │   ├── superseding-successor.json
│   │   │   │   └── supersession-edge.json
│   │   │   ├── README.md
│   │   │   └── research
│   │   │       ├── expected-ask-atlas-2-answer.json
│   │   │       ├── expected-conflicts-retained.json
│   │   │       ├── expected-pack-complete.json
│   │   │       ├── expected-pack-incomplete.json
│   │   │       ├── README.md
│   │   │       ├── sample-question.json
│   │   │       └── sample-workspace-chain.json
│   │   ├── HYBRID-RETRIEVAL-2.md
│   │   ├── intel-slice
│   │   │   ├── adr
│   │   │   │   └── ADR-2.2-INTEL-SLICE-001-deepen-prep.md
│   │   │   ├── ARCHITECTURE.md
│   │   │   ├── AS-2.2-INTEL-SLICE-DEEPEN-PREP-001.md
│   │   │   ├── AS-2.2-INTEL-SLICE-PREP-001.md
│   │   │   ├── contracts
│   │   │   │   └── intel-slice-forbidden-action.schema.json
│   │   │   ├── DEEPEN-FIXTURE-PLAN.md
│   │   │   ├── FIXTURE-PLAN.md
│   │   │   ├── fixtures
│   │   │   │   ├── inputs-citations.sample.json
│   │   │   │   ├── intel-slice-complete.sample.json
│   │   │   │   ├── intel-slice-incomplete.sample.json
│   │   │   │   ├── negative-authority-elevation.expect.json
│   │   │   │   ├── negative-canonical-write.expect.json
│   │   │   │   ├── negative-llm-authority.expect.json
│   │   │   │   ├── negative-llm-authority-stamp.expect.json
│   │   │   │   ├── negative-pilot-invent.expect.json
│   │   │   │   ├── negative-release-cert-stamp.expect.json
│   │   │   │   └── negative-silent-conflict-resolve.expect.json
│   │   │   └── INVARIANTS.md
│   │   ├── kci-engine
│   │   │   ├── adr
│   │   │   │   └── ADR-2.2-KCI-ENGINE-002-deepen-prep.md
│   │   │   ├── ARCHITECTURE.md
│   │   │   ├── AS-2.2-KCI-ENGINE-DEEPEN-PREP-001.md
│   │   │   ├── CONTRACT.md
│   │   │   ├── contracts
│   │   │   │   └── kci-forbidden-action.schema.json
│   │   │   ├── DEEPEN-FIXTURE-PLAN.md
│   │   │   ├── FIXTURE-PLAN.md
│   │   │   ├── fixtures
│   │   │   │   ├── negative-layer-b-write.expect.json
│   │   │   │   ├── negative-llm-as-authority.expect.json
│   │   │   │   ├── negative-pilot-invent.expect.json
│   │   │   │   ├── negative-release-cert-stamp.expect.json
│   │   │   │   └── negative-silent-pass-without-evidence.expect.json
│   │   │   ├── INVARIANTS.md
│   │   │   ├── README.md
│   │   │   └── UNIT-TEST-LANGUAGE.md
│   │   ├── kf2-fabric
│   │   │   ├── adr
│   │   │   │   ├── ADR-2.2-KF2-FABRIC-001-estate-fabric-prep.md
│   │   │   │   └── ADR-2.2-KF2-FABRIC-002-deepen-prep.md
│   │   │   ├── ARCHITECTURE.md
│   │   │   ├── AS-2.2-KF2-FABRIC-DEEPEN-PREP-001.md
│   │   │   ├── AS-2.2-KF2-FABRIC-PREP-001.md
│   │   │   ├── CONTRACT.md
│   │   │   ├── contracts
│   │   │   │   ├── kf2-estate-fabric-inventory.schema.json
│   │   │   │   ├── kf2-estate-fabric-scenario.schema.json
│   │   │   │   ├── kf2-estate-projection.schema.json
│   │   │   │   ├── kf2-fabric-forbidden-action.schema.json
│   │   │   │   └── README.md
│   │   │   ├── DEEPEN-FIXTURE-PLAN.md
│   │   │   ├── FIXTURE-PLAN.md
│   │   │   ├── fixtures
│   │   │   │   ├── entity.sample.json
│   │   │   │   ├── fabric-inventory.fixture.json
│   │   │   │   ├── inventory-export.sample.json
│   │   │   │   ├── namespace.sample.json
│   │   │   │   ├── negative-authority-elevate.expect.json
│   │   │   │   ├── negative-cross-promote.expect.json
│   │   │   │   ├── negative-deepen-authority-elevate.expect.json
│   │   │   │   ├── negative-deepen-cross-promote.expect.json
│   │   │   │   ├── negative-deepen-kf2-runtime-mutation.expect.json
│   │   │   │   ├── negative-deepen-layer-b-write.expect.json
│   │   │   │   ├── negative-deepen-llm-authority.expect.json
│   │   │   │   ├── negative-deepen-pilot-invent.expect.json
│   │   │   │   ├── negative-deepen-projection-write.expect.json
│   │   │   │   ├── negative-deepen-release-cert-stamp.expect.json
│   │   │   │   ├── negative-projection-write.expect.json
│   │   │   │   ├── README.md
│   │   │   │   └── relationship.sample.json
│   │   │   ├── INVARIANTS.md
│   │   │   └── README.md
│   │   ├── mem-gov
│   │   │   ├── adr
│   │   │   │   └── ADR-2.2-MEM-GOV-001-governed-agent-memory-deepen-prep.md
│   │   │   ├── ARCHITECTURE.md
│   │   │   ├── AS-2.2-MEM-GOV-DEEPEN-PREP-001.md
│   │   │   ├── CONTRACT.md
│   │   │   ├── contracts
│   │   │   │   └── mem-gov-forbidden-action.schema.json
│   │   │   ├── FIXTURE-PLAN.md
│   │   │   ├── fixtures
│   │   │   │   ├── negative-dual-active.expect.json
│   │   │   │   ├── negative-layer-b-promotion.expect.json
│   │   │   │   └── negative-llm-authority.expect.json
│   │   │   ├── INVARIANTS.md
│   │   │   └── README.md
│   │   ├── PACKAGE-CONTRACT-STUBS.md
│   │   ├── PACKAGE-MATURITY.json
│   │   ├── PREP-STATUS.md
│   │   ├── README.md
│   │   ├── reality-gap
│   │   │   ├── adr
│   │   │   │   └── ADR-2.2-REALITY-GAP-001-deepen-prep.md
│   │   │   ├── ARCHITECTURE.md
│   │   │   ├── AS-2.2-REALITY-GAP-DEEPEN-PREP-001.md
│   │   │   ├── AS-2.2-REALITY-GAP-PREP-001.md
│   │   │   ├── CONTRACT.md
│   │   │   ├── contracts
│   │   │   │   ├── README.md
│   │   │   │   ├── reality-gap-forbidden-action.schema.json
│   │   │   │   ├── reality-gap-prep-inventory.schema.json
│   │   │   │   └── reality-gap-prep-scenario.schema.json
│   │   │   ├── DEEPEN-FIXTURE-PLAN.md
│   │   │   ├── FIXTURE-PLAN.md
│   │   │   ├── fixtures
│   │   │   │   ├── inventory.fixture.json
│   │   │   │   ├── negative-deepen-llm-authority.expect.json
│   │   │   │   ├── negative-deepen-pilot-invent.expect.json
│   │   │   │   ├── negative-deepen-release-cert-stamp.expect.json
│   │   │   │   ├── negative-deepen-runtime-mutation.expect.json
│   │   │   │   ├── negative-deepen-ui-canonical-write.expect.json
│   │   │   │   ├── negative-deepen-unknown-as-healthy.expect.json
│   │   │   │   ├── negative-deepen-unlock-stamp.expect.json
│   │   │   │   ├── negative-pilot-invent.fixture.json
│   │   │   │   ├── negative-ui-canonical.fixture.json
│   │   │   │   ├── negative-unknown-as-healthy.fixture.json
│   │   │   │   └── README.md
│   │   │   ├── INVARIANTS.md
│   │   │   └── README.md
│   │   ├── reality-live
│   │   │   ├── adr
│   │   │   │   └── ADR-2.2-REALITY-LIVE-001-live-collectors-deepen-prep.md
│   │   │   ├── ARCHITECTURE.md
│   │   │   ├── AS-2.2-REALITY-LIVE-DEEPEN-PREP-001.md
│   │   │   ├── COLLECTORS-DESIGN.md
│   │   │   ├── CONTRACT.md
│   │   │   ├── contracts
│   │   │   │   └── reality-live-forbidden-action.schema.json
│   │   │   ├── FIXTURE-PLAN.md
│   │   │   ├── fixtures
│   │   │   │   ├── collectors.fixture.json
│   │   │   │   ├── negative-llm-authority.expect.json
│   │   │   │   ├── negative-pilot-invent.expect.json
│   │   │   │   ├── negative-release-cert-stamp.expect.json
│   │   │   │   ├── planes.fixture.json
│   │   │   │   └── README.md
│   │   │   ├── INVARIANTS.md
│   │   │   ├── PLANES.md
│   │   │   └── README.md
│   │   ├── research
│   │   │   ├── adr
│   │   │   │   └── ADR-2.2-RESEARCH-001-workspace-deepen-prep.md
│   │   │   ├── ARCHITECTURE.md
│   │   │   ├── AS-2.2-RESEARCH-DEEPEN-PREP-001.md
│   │   │   ├── ASK-ATLAS-2.md
│   │   │   ├── CONTRACT.md
│   │   │   ├── contracts
│   │   │   │   └── research-forbidden-action.schema.json
│   │   │   ├── DEEPEN-FIXTURE-PLAN.md
│   │   │   ├── FIXTURE-PLAN.md
│   │   │   ├── fixtures
│   │   │   │   ├── negative-class-mismatch.expect.json
│   │   │   │   ├── negative-hypothesis-promotion.expect.json
│   │   │   │   ├── negative-llm-authority.expect.json
│   │   │   │   └── negative-silent-winner.expect.json
│   │   │   ├── INVARIANTS.md
│   │   │   ├── README.md
│   │   │   └── THREAT-ROWS.md
│   │   ├── ret-hybrid
│   │   │   ├── adr
│   │   │   │   └── ADR-2.2-RET-HYBRID-002-deepen-prep.md
│   │   │   ├── AS-2.2-RET-HYBRID-DEEPEN-PREP-001.md
│   │   │   ├── CONTRACT.md
│   │   │   ├── contracts
│   │   │   │   └── ret-hybrid-forbidden-action.schema.json
│   │   │   ├── FIXTURE-PLAN.md
│   │   │   ├── fixtures
│   │   │   │   ├── negative-invent-rank-winner.expect.json
│   │   │   │   ├── negative-layer-b-write.expect.json
│   │   │   │   ├── negative-pilot-invent.expect.json
│   │   │   │   ├── negative-release-cert-stamp.expect.json
│   │   │   │   └── negative-semantic-as-authority.expect.json
│   │   │   ├── INVARIANTS.md
│   │   │   └── README.md
│   │   ├── ret-semidx
│   │   │   ├── adr
│   │   │   │   └── ADR-2.2-RET-SEMIDX-001-semantic-index-prep.md
│   │   │   ├── AS-2.2-RET-SEMIDX-PREP-001.md
│   │   │   ├── CONTRACT.md
│   │   │   ├── contracts
│   │   │   │   └── ret-semidx-forbidden-action.schema.json
│   │   │   ├── FIXTURE-PLAN.md
│   │   │   ├── fixtures
│   │   │   │   ├── negative-default-enable-semantic.expect.json
│   │   │   │   ├── negative-layer-b-write.expect.json
│   │   │   │   ├── negative-llm-authority.expect.json
│   │   │   │   ├── negative-pilot-invent.expect.json
│   │   │   │   ├── negative-release-cert-stamp.expect.json
│   │   │   │   ├── negative-semantic-as-authority.expect.json
│   │   │   │   └── negative-unlock-stamp.expect.json
│   │   │   └── INVARIANTS.md
│   │   ├── roadmap-crosswalk
│   │   │   ├── adr
│   │   │   │   └── ADR-2.2-ROADMAP-CROSSWALK-001-deepen-prep.md
│   │   │   ├── AS-2.2-ROADMAP-CROSSWALK-DEEPEN-PREP-001.md
│   │   │   ├── AS-2.2-ROADMAP-CROSSWALK-PREP-001.md
│   │   │   ├── AS-2.2-ROADMAP-CROSSWALK-SYNC-001.md
│   │   │   ├── contracts
│   │   │   │   ├── README.md
│   │   │   │   └── roadmap-crosswalk-forbidden-action.schema.json
│   │   │   ├── CROSSWALK.md
│   │   │   ├── DEEPEN-FIXTURE-PLAN.md
│   │   │   ├── fixtures
│   │   │   │   ├── crosswalk.fixture.json
│   │   │   │   ├── negative-deepen-fixture-as-certification.expect.json
│   │   │   │   ├── negative-deepen-llm-authority.expect.json
│   │   │   │   ├── negative-deepen-pilot-invent.expect.json
│   │   │   │   ├── negative-deepen-production-ready-claim.expect.json
│   │   │   │   ├── negative-deepen-release-cert-stamp.expect.json
│   │   │   │   ├── negative-deepen-runtime-mutation.expect.json
│   │   │   │   ├── negative-deepen-unlock-claim.expect.json
│   │   │   │   └── README.md
│   │   │   ├── INVARIANTS.md
│   │   │   └── README.md
│   │   ├── schemas
│   │   │   └── hybrid-retrieval-2-plan.schema.draft.json
│   │   ├── temporal-ux
│   │   │   ├── adr
│   │   │   │   ├── ADR-2.2-TEMPORAL-UX-001-validity-lens-cockpit.md
│   │   │   │   └── ADR-2.2-TEMPORAL-UX-001-validity-lens-deepen-prep.md
│   │   │   ├── ARCHITECTURE.md
│   │   │   ├── AS-2.2-TEMPORAL-UX-DEEPEN-PREP-001.md
│   │   │   ├── AS-2.2-TEMPORAL-UX-PREP-001.md
│   │   │   ├── CONTRACT.md
│   │   │   ├── contracts
│   │   │   │   ├── as-of-lens-receipt.schema.json
│   │   │   │   ├── forbidden-action.schema.json
│   │   │   │   ├── temporal-action.schema.json
│   │   │   │   ├── temporal-cockpit-view.schema.json
│   │   │   │   └── validity-window-card.schema.json
│   │   │   ├── FIXTURE-PLAN.md
│   │   │   ├── fixtures
│   │   │   │   ├── as-of-lens-receipt.sample.json
│   │   │   │   ├── cockpit-as-of-selected.sample.json
│   │   │   │   ├── negative-bitemporal-mutation.expect.json
│   │   │   │   ├── negative-deepen-bitemporal-mutation.expect.json
│   │   │   │   ├── negative-deepen-canonical-write.expect.json
│   │   │   │   ├── negative-deepen-llm-authority.expect.json
│   │   │   │   ├── negative-deepen-pilot-invent.expect.json
│   │   │   │   ├── negative-deepen-release-cert-stamp.expect.json
│   │   │   │   ├── negative-deepen-silent-winner.expect.json
│   │   │   │   ├── negative-deepen-wall-clock.expect.json
│   │   │   │   ├── negative-silent-winner.expect.json
│   │   │   │   ├── negative-wall-clock.expect.json
│   │   │   │   └── validity-window-card.sample.json
│   │   │   └── INVARIANTS.md
│   │   ├── time-machine
│   │   │   ├── adr
│   │   │   │   └── ADR-2.2-TIME-MACHINE-001-time-machine-deepen-prep.md
│   │   │   ├── ARCHITECTURE.md
│   │   │   ├── AS-2.2-TIME-MACHINE-DEEPEN-PREP-001.md
│   │   │   ├── CONTRACT.md
│   │   │   ├── contracts
│   │   │   │   ├── as-of-snapshot.schema.json
│   │   │   │   ├── claim-diff.schema.json
│   │   │   │   ├── decision-diff.schema.json
│   │   │   │   ├── graph-diff.schema.json
│   │   │   │   ├── knowledge-diff.schema.json
│   │   │   │   ├── README.md
│   │   │   │   └── time-machine-forbidden-action.schema.json
│   │   │   ├── FIXTURE-PLAN.md
│   │   │   ├── fixtures
│   │   │   │   ├── as-of-overlap.expect.json
│   │   │   │   ├── as-of-selected.sample.json
│   │   │   │   ├── claim-diff.sample.json
│   │   │   │   ├── decision-diff.sample.json
│   │   │   │   ├── diff-t1-t2.sample.json
│   │   │   │   ├── graph-diff.sample.json
│   │   │   │   ├── negative-layer-b-promotion.expect.json
│   │   │   │   ├── negative-llm-authority.expect.json
│   │   │   │   ├── negative-pilot-invent.expect.json
│   │   │   │   ├── negative-release-cert-stamp.expect.json
│   │   │   │   ├── negative-silent-overlap-winner.expect.json
│   │   │   │   ├── README.md
│   │   │   │   └── rejected-wall-clock.expect.json
│   │   │   ├── INVARIANTS.md
│   │   │   └── README.md
│   │   └── xproj
│   │       ├── adr
│   │       │   ├── ADR-2.2-XPROJ-001-cross-project-fabric-prep.md
│   │       │   └── ADR-2.2-XPROJ-002-deepen-prep.md
│   │       ├── ARCHITECTURE.md
│   │       ├── AS-2.2-XPROJ-CONTRACT-PREP-001.md
│   │       ├── AS-2.2-XPROJ-DEEPEN-PREP-001.md
│   │       ├── CONTRACT.md
│   │       ├── contracts
│   │       │   ├── README.md
│   │       │   ├── xproj-estate-lens.schema.json
│   │       │   ├── xproj-fabric-inventory.schema.json
│   │       │   ├── xproj-fabric-scenario.schema.json
│   │       │   └── xproj-forbidden-action.schema.json
│   │       ├── DEEPEN-FIXTURE-PLAN.md
│   │       ├── FIXTURE-PLAN.md
│   │       ├── fixtures
│   │       │   ├── conflict-index.sample.json
│   │       │   ├── cross-project-edge.sample.json
│   │       │   ├── duplicate-candidate.sample.json
│   │       │   ├── entity-join.sample.json
│   │       │   ├── fabric-inventory.fixture.json
│   │       │   ├── negative-authority-elevate.expect.json
│   │       │   ├── negative-autocollapse.expect.json
│   │       │   ├── negative-deepen-authority-elevate.expect.json
│   │       │   ├── negative-deepen-autocollapse.expect.json
│   │       │   ├── negative-deepen-fuzzy-join.expect.json
│   │       │   ├── negative-deepen-layer-b-write.expect.json
│   │       │   ├── negative-deepen-llm-authority.expect.json
│   │       │   ├── negative-deepen-pilot-invent.expect.json
│   │       │   ├── negative-deepen-release-cert-stamp.expect.json
│   │       │   ├── negative-fuzzy-join.expect.json
│   │       │   └── README.md
│   │       ├── INVARIANTS.md
│   │       └── README.md
│   ├── atlas-3
│   │   ├── ACCEPTANCE.md
│   │   ├── ARCHITECTURE.md
│   │   ├── AT3-006.md
│   │   ├── AT3-010.md
│   │   ├── AT3-011.md
│   │   ├── AT3-012.md
│   │   ├── AT3-013.md
│   │   ├── AT3-020.md
│   │   ├── AT3-021.md
│   │   ├── AT3-022.md
│   │   ├── AT3-023.md
│   │   ├── AT3-036.md
│   │   ├── AT3-037.md
│   │   ├── AT3-038.md
│   │   ├── AT3-039.md
│   │   ├── AT3-040.md
│   │   ├── AT3-041.md
│   │   ├── AT3-042.md
│   │   ├── AT3-043.md
│   │   ├── AT3-044.md
│   │   ├── AT3-045.md
│   │   ├── AT3-046.md
│   │   ├── AT3-047.md
│   │   ├── AT3-048.md
│   │   ├── AT3-049.md
│   │   ├── AT3-051.md
│   │   ├── AT3-052.md
│   │   ├── AT3-053.md
│   │   ├── AT3-054.md
│   │   ├── AT3-055.md
│   │   ├── AT3-056.md
│   │   ├── AT3-057.md
│   │   ├── AT3-058.md
│   │   ├── AT3-060.md
│   │   ├── AT3-061.md
│   │   ├── AT3-062.md
│   │   ├── AT3-070.md
│   │   ├── AT3-071.md
│   │   ├── AT3-072.md
│   │   ├── AT3-080.md
│   │   ├── AT3-081.md
│   │   ├── AT3-082.md
│   │   ├── AT3-090.md
│   │   ├── AT3-091.md
│   │   ├── AT3-092.md
│   │   ├── AT3-093.md
│   │   ├── AT3-094.md
│   │   ├── AT3-095.md
│   │   ├── AT3-096.md
│   │   ├── AT3-100.md
│   │   ├── AT3-101.md
│   │   ├── AT3-102.md
│   │   ├── AT3-110.md
│   │   ├── AT3-111.md
│   │   ├── AT3-112.md
│   │   ├── chronicle
│   │   │   └── HORIZON.md
│   │   ├── COMPETITIVE-POSITIONING.md
│   │   ├── contracts
│   │   │   ├── capability.schema.json
│   │   │   ├── engineering-event.schema.json
│   │   │   ├── twin-node.schema.json
│   │   │   └── twin-relationship.schema.json
│   │   ├── DEPENDENCY-DAG.md
│   │   ├── EPICS.md
│   │   ├── FOUNDATION.md
│   │   ├── HISTORICAL-INPUTS.md
│   │   ├── llm-memory
│   │   │   ├── ACCEPTANCE.md
│   │   │   ├── ARCHITECTURE.md
│   │   │   ├── KNOWLEDGE-EXTRACTION.md
│   │   │   ├── NORMALIZATION.md
│   │   │   ├── PRIVACY.md
│   │   │   ├── PROVIDER-CONTRACT.md
│   │   │   ├── PROVIDER-MATRIX.md
│   │   │   ├── RECONCILIATION.md
│   │   │   └── SECURITY.md
│   │   ├── MASTER-ROADMAP.md
│   │   ├── MIGRATION-2X-TO-3X.md
│   │   ├── NORTH-STAR.md
│   │   ├── PACKAGE-MATURITY.json
│   │   ├── PRODUCT-EXPERIENCE.md
│   │   ├── README.md
│   │   └── SECURITY.md
│   ├── atlas-core-vertical-slice-plan.md
│   ├── atlas-core-vertical-slice-post-merge.md
│   ├── atlas-demo-estate-001-handoff-acceptance.md
│   ├── backlog.md
│   ├── claims-authority-conflicts.md
│   ├── CODER-ALPHA-035-REBASE.md
│   ├── completion-plan.md
│   ├── contracts
│   │   ├── AS-2.0-INTEL-WAVE1-FUTURE-API.md
│   │   ├── AS-2.0-INTEL-WAVE1-FUTURE-WEB.md
│   │   ├── AS-2.0-INTEL-WAVE6-FUTURE-API.md
│   │   └── AS-2.0-INTEL-WAVE7-FUTURE-WEB.md
│   ├── demo
│   │   ├── ADV-DEMO.md
│   │   ├── API-MCP-E2E.md
│   │   ├── ARCHITECTURE.md
│   │   ├── AS-DEMO-2.1-001.md
│   │   ├── BACKEND-SUITE.md
│   │   ├── browser-e2e
│   │   │   ├── ARCHITECTURE.md
│   │   │   ├── AS-DEMO-2.1-BROWSER-E2E-001.md
│   │   │   ├── checklists
│   │   │   │   └── browser-e2e.md
│   │   │   ├── CONTRACT.md
│   │   │   ├── FIXTURE-PLAN.md
│   │   │   ├── fixtures
│   │   │   │   ├── browser-e2e-missing.receipt.sample.json
│   │   │   │   ├── negative-invent-path-a-observed.expect.json
│   │   │   │   ├── negative-invent-verified.expect.json
│   │   │   │   └── negative-release-certified.expect.json
│   │   │   ├── INVARIANTS.md
│   │   │   └── README.md
│   │   ├── CERTIFICATE-TEMPLATE.md
│   │   ├── checklists
│   │   │   ├── api-mcp.md
│   │   │   ├── backend.md
│   │   │   └── frontend.md
│   │   ├── D-183-TIME-MACHINE-AND-QUERY.md
│   │   ├── DEMO-ESTATE-MANIFEST.json
│   │   ├── DEMO-EVIDENCE.md
│   │   ├── DEMO-FINDINGS.md
│   │   ├── DEMO-SCRIPT.md
│   │   ├── DEMO-TEST-REPORT.md
│   │   ├── FRONTEND-SUITE.md
│   │   ├── FULL-PRODUCT-DEMO.md
│   │   ├── full-product-demo-scope.json
│   │   ├── FULL-PRODUCT-DEMO-SCOPE.md
│   │   ├── L3-OAI-OPTIONAL.md
│   │   ├── LIMITATIONS.md
│   │   ├── LIVE-EXPERIENCE.md
│   │   ├── MODE-BANNER.md
│   │   ├── QUICKSTART.md
│   │   ├── README.md
│   │   ├── scripts
│   │   │   ├── demo-down.ps1
│   │   │   └── demo-up.ps1
│   │   └── WINDOWS-QUICKSTART.md
│   ├── durable-source-lineage.md
│   ├── evidence
│   │   ├── AS-2.0-API-001-LOCAL-ACCEPTANCE.md
│   │   ├── AS-2.0-API-001-MATRICES.md
│   │   ├── AS-2.0-API-001.md
│   │   ├── AS-2.0-API-001-WAVE15-FREEZE.md
│   │   ├── AS-2.0-CHANGE-001.md
│   │   ├── AS-2.0-CTX-001.md
│   │   ├── AS-2.0-DECISION-001.md
│   │   ├── AS-2.0-DELTA-001.md
│   │   ├── AS-2.0-DEP-001.md
│   │   ├── AS-2.0-EXPLAIN-001.md
│   │   ├── AS-2.0-GAP-002.md
│   │   ├── AS-2.0-HANDOFF-001.md
│   │   ├── AS-2.0-INTEGRATION-READINESS-REPORT.md
│   │   ├── AS-2.0-INTEL-001.md
│   │   ├── AS-2.0-INTEL-002.md
│   │   ├── AS-2.0-INTEL-003B.md
│   │   ├── AS-2.0-INTEL-003C.md
│   │   ├── AS-2.0-INTEL-003.md
│   │   ├── AS-2.0-INTEL-004.md
│   │   ├── AS-2.0-INTEL-005.md
│   │   ├── AS-2.0-INTEL-OBS-001.md
│   │   ├── AS-2.0-INTEL-PERF-001.md
│   │   ├── AS-2.0-INTEL-PERF-002.md
│   │   ├── AS-2.0-INTEL-PERF-003.md
│   │   ├── AS-2.0-INTEL-WAVE1-RECEIPT.md
│   │   ├── AS-2.0-INTEL-WAVE1-SURFACE-OVERLAP.md
│   │   ├── AS-2.0-INTEL-WAVE3-RECEIPT.md
│   │   ├── AS-2.0-INTEL-WAVE4-RECEIPT.md
│   │   ├── AS-2.0-INTEL-WAVE5-RECEIPT.md
│   │   ├── AS-2.0-INTEL-WAVE67-RECEIPT.md
│   │   ├── AS-2.0-INTEL-WAVE8-RECEIPT.md
│   │   ├── AS-2.0-INTEL-WAVE9-RECEIPT.md
│   │   ├── AS-2.0-NEXT-001.md
│   │   ├── AS-2.0-PORTFOLIO-001.md
│   │   ├── AS-2.0-PORTFOLIO-002.md
│   │   ├── AS-2.0-PORTFOLIO-003.md
│   │   ├── AS-2.0-RISK-001.md
│   │   ├── AS-2.0-STATE-001.md
│   │   ├── AS-2.0-TEMPINT-001.md
│   │   ├── AS-2.0-WAVE9PLUS-RECEIPT.md
│   │   ├── AS-2.0-WEB-001-LOCAL-ACCEPTANCE.md
│   │   ├── AS-2.0-WEB-001.md
│   │   ├── AS-2.0-WEB-001-OVERLAP.md
│   │   ├── AS-2.0-WEB-001-WAVE16-FREEZE.md
│   │   ├── AS-2.1-ASK-ATLAS-LIVE-WEB.md
│   │   ├── AS-2.1-ASK-ATLAS-LIVE-WEB-OWNER-PACKET.md
│   │   ├── AS-2.2-KDIFF-001-LIVE-PROJECT-WEB.md
│   │   ├── AS-2.2-KDIFF-001-LIVE-PROJECT-WEB-OWNER-PACKET.md
│   │   ├── AS-CI-WINDOWS-PERF-GATE-001.md
│   │   ├── AS-CODER-ALPHA-ARCHITECTURE-SURFACE-001.md
│   │   ├── AS-CODER-ALPHA-CONTEXT-WEB.md
│   │   ├── AS-CODER-ALPHA-DOGFOOD-COMPILER-COVERAGE-001.md
│   │   ├── AS-CODER-ALPHA-HONESTY-TAIL-001.md
│   │   ├── AS-CODER-ALPHA-INCREMENTAL-CONNECT-001.md
│   │   ├── AS-CODER-ALPHA-INVENTORY-DRIFT-001.md
│   │   ├── AS-CODER-ALPHA-ISOLATION-ADV-HARNESS-001.md
│   │   ├── AS-CODER-ALPHA-LENS-DRIFT-CONVERGENCE-001.md
│   │   ├── AS-CODER-ALPHA-SOURCE-DRIFT-SCOPE-001.md
│   │   ├── AS-CODER-ALPHA-WEB-LIVE-HOOK-HONESTY.md
│   │   ├── AS-CODER-ALPHA-WEB-LIVE-HOOK-HONESTY-OWNER-PACKET.md
│   │   ├── AS-CORE-002-post-merge-receipt.yaml
│   │   ├── AS-CORE-002-source-lifecycle-recertification.yaml
│   │   ├── AS-CORE-003-claim-identity-amendment-plan.yaml
│   │   ├── AS-CORE-003-receipt.yaml
│   │   ├── AS-CORE-003-v2-candidate-003-review.yaml
│   │   ├── AS-CORE-003-v2-candidate-003.yaml
│   │   ├── AS-CORE-003-v2-candidate-004.yaml
│   │   ├── AS-CORE-003-v2-candidate-005-review.yaml
│   │   ├── AS-CORE-003-v2-candidate-005.yaml
│   │   ├── AS-CORE-003-v2-candidate-006-review-addendum.yaml
│   │   ├── AS-CORE-003-v2-candidate-006.yaml
│   │   ├── AS-CORE-003-v2-remediation-receipt.yaml
│   │   ├── AS-CORE-004-post-merge-closure.md
│   │   ├── AS-CORE-004-raw-corpus-reconciliation.md
│   │   ├── AS-CORE-004-reviews.md
│   │   ├── AS-ENG-005-receipt.yaml
│   │   ├── AS-EXT-001A-level0-selfhost-receipt-v2-amendment.yaml
│   │   ├── AS-EXT-001A-level0-selfhost-receipt-v2.yaml
│   │   ├── AS-EXT-001A-level0-selfhost-receipt.yaml
│   │   ├── AS-GH-001-receipt.yaml
│   │   ├── AS-ID-001-final-certification-remediation-receipt.yaml
│   │   ├── AS-ID-001-governor-remediation-receipt.yaml
│   │   ├── AS-ID-001-receipt.yaml
│   │   ├── AS-ID-001-retired-slot-resolution-wiring-receipt.yaml
│   │   ├── AS-INT-001-post-merge-receipt.yaml
│   │   ├── AS-INT-001-receipt.yaml
│   │   ├── AS-MAINT-001-receipt.yaml
│   │   ├── AS-MVP-001-architecture-entry.yaml
│   │   ├── AS-MVP-001-receipt.yaml
│   │   ├── AS-OBSIDIAN-CAPTURE-001-F10-REFUSAL-PARITY.md
│   │   ├── AS-OBSIDIAN-CAPTURE-001-F11-MKDIR-BOUNDARY.md
│   │   ├── AS-OBSIDIAN-CAPTURE-001-F2-SEAL.md
│   │   ├── AS-OBSIDIAN-CAPTURE-001-F3-RESERVED-MARKER-CLOSURE.md
│   │   ├── AS-OBSIDIAN-CAPTURE-001-F5-NEWLINE-FIDELITY.md
│   │   ├── AS-OBSIDIAN-CAPTURE-001-F6-ERROR-BOUNDARY.md
│   │   ├── AS-OBSIDIAN-CAPTURE-001-F7-BOM-OWNERSHIP.md
│   │   ├── AS-OBSIDIAN-CAPTURE-001-F8-SPLIT-TOKEN-PIN.md
│   │   ├── AS-OBSIDIAN-CAPTURE-001-F9-DIAGNOSTIC-UNIFORMITY.md
│   │   ├── AS-ORCH-CONTINUATION-BROKER-001-d092-runtime-wiring-audit.json
│   │   ├── AS-ORCH-CONTINUATION-BROKER-001-six-p1-closure-088.json
│   │   ├── AS-PROJECT-ROADMAP-001.md
│   │   ├── AS-PROJECT-ROADMAP-001-OWNER-PACKET.md
│   │   ├── AS-RET-001-post-merge-receipt.yaml
│   │   ├── AS-RET-001-receipt.yaml
│   │   ├── AS-SEC-001-certification-carry-forward.yaml
│   │   ├── AS-SEC-001-post-merge-validation.yaml
│   │   ├── AS-SEC-001-receipt.yaml
│   │   ├── AS-SPEC-004-receipt.yaml
│   │   ├── AS-TASK-CONTEXT-AND-CONTINUITY-001
│   │   │   ├── demo
│   │   │   │   ├── budget.json
│   │   │   │   ├── budget-overflow.json
│   │   │   │   ├── compose-human.txt
│   │   │   │   ├── compose.json
│   │   │   │   ├── continuation.json
│   │   │   │   ├── freshness-after-change.json
│   │   │   │   ├── HEAD.txt
│   │   │   │   ├── inspect.json
│   │   │   │   ├── packet-budget-overflow.json
│   │   │   │   ├── packet.json
│   │   │   │   ├── repo-mut
│   │   │   │   │   ├── docs
│   │   │   │   │   │   ├── architecture.md
│   │   │   │   │   │   ├── conflict-a.md
│   │   │   │   │   │   ├── conflict-b.md
│   │   │   │   │   │   ├── injection-bait.md
│   │   │   │   │   │   └── unrelated-history.md
│   │   │   │   │   └── src
│   │   │   │   │       └── api.py
│   │   │   │   ├── size-comparison.json
│   │   │   │   └── TREE.txt
│   │   │   └── HANDOFF.md
│   │   ├── atlas-core-ingestion-traversal.json
│   │   ├── atlas-core-vertical-slice.json
│   │   ├── atlas-core-vertical-slice-post-merge-receipt.yaml
│   │   ├── atlas-core-vertical-slice-receipt.yaml
│   │   ├── D-028-INTEGRATED-ATLAS3-STACK.json
│   │   ├── D-028-INTEGRATED-ATLAS3-STACK.md
│   │   ├── D-029-SUPERSESSION-CLEANUP.json
│   │   ├── D-029-SUPERSESSION-CLEANUP.md
│   │   ├── D-038-COMPLETION-REPORT.md
│   │   ├── D-038-FRESH-AGENT-CHALLENGE.md
│   │   ├── D-038-REAL-ATLAS-DOGFOOD.md
│   │   ├── D-038-WEB-TRUTH-IV.md
│   │   ├── D-039-ARCH-CHANGED-IV.md
│   │   ├── D-039-SECOND-CONNECT.md
│   │   ├── D-040-CROSS-SURFACE.md
│   │   ├── D-040-FRESH-AGENT-V2.md
│   │   ├── D-040-POSITIVE-DELTA.md
│   │   ├── D-042-KICKOFF-PACKET.md
│   │   ├── D-043-FRESH-AGENT-V3.md
│   │   ├── D-049-WAVE1-DOGFOOD-IV.md
│   │   ├── D-049-WAVE1-IMPLEMENTATION.md
│   │   ├── D-062-CODER-ALPHA-ACCEPTANCE.md
│   │   ├── D-062-CODER-ALPHA-ACCEPTANCE-RECEIPT.yaml
│   │   ├── D-063-LOCAL-FREEZE.md
│   │   ├── D-063-WAVE1-TRUTH-HARDENING.md
│   │   ├── d064-overnight
│   │   │   ├── corrupt_input.py
│   │   │   ├── corrupt_input.result.json
│   │   │   ├── determinism_replay.py
│   │   │   ├── determinism_replay.result.json
│   │   │   ├── dogfood_realistic_estates.py
│   │   │   ├── dogfood_realistic_estates_results.json
│   │   │   ├── dogfood_scale.py
│   │   │   ├── dogfood_scale_results.json
│   │   │   ├── identity-connected-results.json
│   │   │   ├── parity_cli_api_web.py
│   │   │   ├── parity_cli_api_web.result.json
│   │   │   ├── path-stale-secret-results.json
│   │   │   ├── redteam_identity_connected.py
│   │   │   ├── redteam_knowledge_obsidian.py
│   │   │   ├── redteam_knowledge_obsidian_results.json
│   │   │   ├── redteam_path_security.py
│   │   │   ├── redteam_path_security-results.json
│   │   │   ├── redteam_secrets_privacy.py
│   │   │   ├── redteam_secrets_privacy-results.json
│   │   │   ├── redteam_stale_cache.py
│   │   │   ├── redteam_stale_cache-results.json
│   │   │   └── run_path_stale_secret.py
│   │   ├── D-067-INDEPENDENT-IV.md
│   │   ├── D-067-LOCAL-REVALIDATION-RUNBOOK.md
│   │   ├── d067-premerge
│   │   │   └── VALIDATION-COMMANDS.md
│   │   ├── D-067-SUPERSEDING-FREEZE.md
│   │   ├── D-078-INDEPENDENT-IV.md
│   │   ├── D-078-LOCAL-REVALIDATION-RUNBOOK.md
│   │   ├── D-078-SUPERSEDING-FREEZE.md
│   │   ├── D-080-INDEPENDENT-IV.md
│   │   ├── D-080-SUPERSEDING-FREEZE.md
│   │   ├── D-081-LOCAL-REVALIDATION-RUNBOOK.md
│   │   ├── D-082-CONDITIONAL-MERGE-READINESS.md
│   │   ├── D-084-INDEPENDENT-IV.md
│   │   ├── D-084-SUPERSEDING-FREEZE.md
│   │   ├── D-085-LOCAL-REVALIDATION-RUNBOOK.md
│   │   ├── D-086-CONDITIONAL-INTEGRATION-READINESS.md
│   │   ├── D-087-CLOUD-IV.json
│   │   ├── D-087-SUPERSEDING-FREEZE.md
│   │   ├── D-088-LOCAL-REVALIDATION-RUNBOOK.md
│   │   ├── D-089-FINAL-RECONCILIATION.md
│   │   ├── D-089-OWNER-MERGE-PACKET.md
│   │   ├── D-089-POST-MERGE-SEAL.md
│   │   ├── D-091-D042-EXECUTION-AUTHORIZATION.md
│   │   ├── D-092-LOCAL-REVALIDATION-RUNBOOK.md
│   │   ├── D-093-CONDITIONAL-INTEGRATION-READINESS.md
│   │   ├── D-094A-D092C-SEAL-ACK.md
│   │   ├── D-094-FINAL-RECONCILIATION.md
│   │   ├── D-094-OWNER-MERGE-PACKET.md
│   │   ├── D-095-D042-POST-MERGE-RATIFICATION-AND-SEAL.md
│   │   ├── D-095-D042-POST-MERGE-SEAL.md
│   │   ├── D-096-D042-POST-HOC-OWNER-GOVERNANCE-RATIFICATION.md
│   │   ├── D-099-PR359-REPAIR-MERGE-PACKET.md
│   │   ├── D-100-ROADMAP-LOCAL-AUTHENTIC-REIV.md
│   │   ├── D-102-PR358-EXACT-MAIN-OWNER-PACKET.md
│   │   ├── D-102-PR358-EXACT-MAIN-REFRESH.md
│   │   ├── D-164-PR428-FRESH-CARRIER.md
│   │   ├── D-176-D149-001-REMEDIATION.md
│   │   ├── D-177-CLEAN-MACHINE-FIRST-RUN.md
│   │   ├── D-177-MERGE-504-RECEIPT.md
│   │   ├── D-177-PR474-CORE-DIFF-IV.md
│   │   ├── D-177-QUEUE-AND-UNIQUE.md
│   │   ├── D-177-RETURN-PACKET.md
│   │   ├── D-197-RETURN-PACKET.md
│   │   ├── D-199-END-OF-DAY-HANDOFF.md
│   │   ├── D-200-ORCHAUT-010-GATE-CF-SELECT-LEASE-FIX.md
│   │   ├── D-201-ORCH001E-008-P3-ORPHANED-DISPATCH-RECOVERY.md
│   │   ├── D-202-OWNER-AUTHORIZED-ORCHESTRATION-ACTIVATION.md
│   │   ├── D-203-LOOP-IN-PROCESS-RECOVERY-ILLEGAL-TRANSITION.md
│   │   ├── D-204-GOVERNOR-LOOP-TICK-NO-NODE-REHYDRATION.md
│   │   ├── D-205-ORCH001E-011-GOVERNOR-LOOP-REHYDRATION.md
│   │   ├── D-206-ORCH001D-012-CURSOR-DISPATCH-ACCEPTANCE-ATTEMPT.md
│   │   ├── D-207-PERSISTENT-AUTONOMY-THREE-PROCESS-LIFECYCLE-REHEARSAL.md
│   │   ├── D-208-DEFECT-2-ACTIVE-LEASED-REGRESSION-FALSIFIED.md
│   │   ├── D-209-CLUSTER-C-GIT-HISTORY-SCAN-REDESIGN.md
│   │   ├── D-AUG26-EVIDENCE-GROUNDED-GOLDEN-ESTATE-034.json
│   │   ├── D-AUG26-EVIDENCE-GROUNDED-GOLDEN-ESTATE-034.md
│   │   ├── D-AUG26-FRONTIER-ACCOUNTING-RECONCILIATION-035.json
│   │   ├── D-AUG26-FRONTIER-ACCOUNTING-RECONCILIATION-035.md
│   │   ├── D-CLOUD-AUG26-GE-WINDOWS-REMEDIATION-020-LOCAL-REBIND.md
│   │   ├── D-CLOUD-AUG26-GE-WINDOWS-REMEDIATION-020.md
│   │   ├── D-CODER-ALPHA-035-CHANGED-001-IV.md
│   │   ├── D-CODER-ALPHA-035-CONNECT-001-IV.md
│   │   ├── D-CODER-ALPHA-035-OVERVIEW-001-IV.md
│   │   ├── D-CODER-ALPHA-036-CAPTURE-001-IV.md
│   │   ├── D-CODER-ALPHA-036-CONTEXT-HANDOFF-IV.md
│   │   ├── D-CODER-ALPHA-036-DECISIONS-UNKNOWN-BRIEF-IV.md
│   │   ├── D-CODER-ALPHA-036-HUMAN-LOOP-001-IV.md
│   │   ├── D-CODER-ALPHA-036-OBSIDIAN-001-IV.md
│   │   ├── D-CODER-ALPHA-037-DOC-ANCHOR-STATE-001-IV.md
│   │   ├── d-phase2a
│   │   │   ├── EVIDENCE.md
│   │   │   ├── POC-RUNBOOK.md
│   │   │   ├── receipts
│   │   │   │   ├── process-a-receipt.json
│   │   │   │   ├── process-b-receipt.json
│   │   │   │   └── process-c-receipt.json
│   │   │   └── run_three_process_demo.py
│   │   ├── D-PROJECT-ATLAS-CODER-ALPHA-035-phase2-journey-audit.md
│   │   └── F4-GRAPH-PROJECTION-HUMAN-REGION-DIVERGENCE.md
│   ├── implementation-roadmap.md
│   ├── master-roadmap.md
│   ├── orch001c-010-cursor-acceptance-packet.md
│   ├── orchestration
│   │   ├── AS-ORCH-SPECULATIVE-CERTIFICATION-001.md
│   │   ├── live-integration
│   │   │   └── DELIVERY.md
│   │   ├── program
│   │   │   ├── CAPABILITY-MATRIX.md
│   │   │   ├── CONTINUATION.md
│   │   │   ├── CONTROL.md
│   │   │   ├── ENROLLMENT.md
│   │   │   ├── evidence
│   │   │   │   ├── capability-matrix.json
│   │   │   │   ├── codex-runtime-demo-events.jsonl
│   │   │   │   ├── codex-runtime-demo-program.json
│   │   │   │   ├── codex-runtime-demo-report.json
│   │   │   │   ├── full-suite-b19c2298.md
│   │   │   │   ├── full-suite-b19c2298.tail.txt
│   │   │   │   ├── full-suite-integrated.md
│   │   │   │   ├── full-suite-integrated.tail.txt
│   │   │   │   ├── full-suite-no-runtimes.md
│   │   │   │   ├── full-suite-no-runtimes.tail.txt
│   │   │   │   ├── operator-journey-transcript.txt
│   │   │   │   ├── REAL-RUNTIME-DEMO-CODEX.md
│   │   │   │   ├── real-runtime-demo-events.jsonl
│   │   │   │   ├── REAL-RUNTIME-DEMO.md
│   │   │   │   ├── real-runtime-demo-program.json
│   │   │   │   ├── real-runtime-demo-report.json
│   │   │   │   ├── runtime-support-matrix.json
│   │   │   │   ├── systemwide-acceptance-events.jsonl
│   │   │   │   ├── SYSTEMWIDE-ACCEPTANCE.md
│   │   │   │   ├── systemwide-acceptance-program.json
│   │   │   │   ├── systemwide-acceptance-report.json
│   │   │   │   └── TERMINAL-CI.md
│   │   │   ├── LAUNCH.md
│   │   │   ├── MISSION-TASK-QUEUE.md
│   │   │   ├── OPERATOR-JOURNEY.md
│   │   │   ├── operator-journey.sh
│   │   │   ├── PERMISSIONS.md
│   │   │   ├── programs
│   │   │   │   └── first-program-TEMPLATE.json
│   │   │   ├── README.md
│   │   │   ├── REUSE-MAP.md
│   │   │   ├── SERVICE.md
│   │   │   ├── SUPPORT-MATRIX.md
│   │   │   └── WORK-SELECTION.md
│   │   ├── taskcontract
│   │   │   ├── demo
│   │   │   │   ├── binding.broken.json
│   │   │   │   ├── binding.json
│   │   │   │   ├── contract.v1.json
│   │   │   │   ├── contract.v2-blocked.json
│   │   │   │   ├── diff.v1-v2.json
│   │   │   │   ├── evidence
│   │   │   │   │   ├── 01-sources.json
│   │   │   │   │   ├── 02-draft-incomplete.json
│   │   │   │   │   ├── 03-draft-complete.json
│   │   │   │   │   ├── 04-validate-operator-view.txt
│   │   │   │   │   ├── 05-render.json
│   │   │   │   │   ├── 06-program-validate.json
│   │   │   │   │   ├── 07-preflight.txt
│   │   │   │   │   ├── 08-review-package.json
│   │   │   │   │   ├── 09-blocked-operator-view.txt
│   │   │   │   │   ├── 10-diff.json
│   │   │   │   │   └── 11-verify-stale.json
│   │   │   │   ├── instruction.v1.md
│   │   │   │   ├── profile.json
│   │   │   │   ├── program.v1.json
│   │   │   │   ├── README.md
│   │   │   │   ├── review-package.v1.json
│   │   │   │   ├── run-demo.sh
│   │   │   │   ├── snapshot
│   │   │   │   │   ├── INT-013.acceptance-contract.yaml
│   │   │   │   │   ├── INT-013.as-read.json
│   │   │   │   │   ├── INT-013.backlog-lines.md
│   │   │   │   │   ├── README.md
│   │   │   │   │   └── SNAPSHOT.sha256
│   │   │   │   ├── supplied.json
│   │   │   │   ├── validation.v1.json
│   │   │   │   └── validation.v2-blocked.json
│   │   │   ├── LIMITS.md
│   │   │   ├── README.md
│   │   │   ├── ROLES.md
│   │   │   └── SCHEMA.md
│   │   └── work-readiness
│   │       ├── DELIVERY.md
│   │       ├── INTERFACE-HANDOFFS.md
│   │       └── README.md
│   ├── origination-acceptance-contracts.yaml
│   ├── plan.md
│   ├── product
│   │   └── CODER-ALPHA-NORTH-STAR.md
│   ├── productization
│   │   ├── CLEAN-MACHINE-PREP-RUNBOOK.md
│   │   ├── install
│   │   │   ├── ADV-FINDINGS.md
│   │   │   ├── LIMITATIONS.md
│   │   │   ├── OPERATOR.md
│   │   │   ├── README.md
│   │   │   └── STRANGER.md
│   │   └── onboard
│   │       ├── CHECKLIST.md
│   │       ├── FIRST-RUN.md
│   │       ├── HONESTY.md
│   │       └── README.md
│   ├── PROJECT-ATLAS-CURRENT-STATE.md
│   ├── prp.md
│   ├── releases
│   │   ├── 1.0.0
│   │   │   ├── CHECKLIST.md
│   │   │   ├── compatibility-anchor.json
│   │   │   ├── COMPATIBILITY-SNAPSHOT.md
│   │   │   ├── EVIDENCE-INDEX.md
│   │   │   ├── README.md
│   │   │   ├── RECEIPT.md
│   │   │   ├── RECEIPT-TEMPLATE.md
│   │   │   └── RELEASE-NOTES.md
│   │   └── 2.0.0
│   │       ├── CHECKLIST.md
│   │       ├── COMPATIBILITY-NOTES.md
│   │       ├── EVIDENCE-INDEX.md
│   │       ├── final-cert-pilot-waiver.json
│   │       ├── PILOT-REPORT.md
│   │       ├── README.md
│   │       ├── RECEIPT.md
│   │       └── RELEASE-NOTES.md
│   ├── scripts
│   │   ├── adv_clean_clone_rehearsal.py
│   │   ├── d144_certification_runner.py
│   │   ├── d147_broker_reconcile.py
│   │   ├── d148_authentic_o2_runner.py
│   │   ├── f4_protected_region_divergence_harness.py
│   │   ├── f8_near_miss_controls.py
│   │   ├── f9_diagnostic_parity.py
│   │   └── seal_retracted_claim_sweep.py
│   ├── security
│   │   └── REGRESSION-SUITE-SEED.md
│   ├── security-findings.md
│   ├── strategy
│   │   ├── ATLAS-2.1-RELEASE-CRITICAL-DAG.md
│   │   ├── ATLAS-2.2-EXECUTABLE-ROADMAP.md
│   │   ├── ATLAS-2.3-STRATEGIC-BACKLOG.md
│   │   ├── ATLAS-3.0-NORTH-STAR-BACKLOG.md
│   │   ├── ATLAS-GAP-REGISTER.md
│   │   ├── ATLAS-NORTH-STAR-GAP-ANALYSIS.md
│   │   └── README.md
│   ├── superpowers
│   │   └── plans
│   │       └── 2026-09-10-atlas-task-context-continuity.md
│   └── work-packages
│       ├── AS-EXT-001A.md
│       └── AS-GH-001.md
├── fixtures
│   ├── demo
│   │   ├── estate
│   │   │   ├── project-a
│   │   │   │   ├── ARCHITECTURE.md
│   │   │   │   ├── DEPENDENCIES.md
│   │   │   │   ├── docs
│   │   │   │   │   └── ADR-001-database.md
│   │   │   │   ├── README.md
│   │   │   │   ├── REQUIREMENTS.md
│   │   │   │   └── src
│   │   │   │       └── RUNTIME.md
│   │   │   ├── project-b
│   │   │   │   ├── DEPENDENCIES.md
│   │   │   │   ├── docs
│   │   │   │   │   └── ARCHITECTURE.md
│   │   │   │   └── README.md
│   │   │   └── project-c
│   │   │       ├── docs
│   │   │       │   ├── ADR-002-mysql-superseded.md
│   │   │       │   └── NOTES.md
│   │   │       ├── INVENTORY.md
│   │   │       └── README.md
│   │   ├── README.md
│   │   └── story
│   │       ├── ASK-PROMPTS.md
│   │       ├── EXPECTED-OUTCOMES.json
│   │       └── HERO-SCENARIO.md
│   └── eval
│       ├── configs
│       │   ├── autolab.paths.json
│       │   ├── scoring.paths.json
│       │   └── training.paths.json
│       ├── holdouts
│       │   └── hidden
│       │       ├── ACCESS.md
│       │       └── cases
│       │           ├── EV-HOLD-101-exact.json
│       │           └── EV-HOLD-102-prefix.json
│       ├── opt-gate
│       │   ├── hard-gate-policy.json
│       │   ├── honesty-catalog.json
│       │   ├── scoring-policy.json
│       │   └── thresholds.json
│       ├── public
│       │   └── cases
│       │       ├── EV-PUB-001-exact.json
│       │       └── EV-PUB-002-prefix.json
│       ├── README.md
│       └── regression
│           ├── cases
│           │   ├── EV-REG-001-exact.json
│           │   └── EV-REG-002-prefix.json
│           └── README.md
├── GOVERNANCE.md
├── integrations
│   └── chatgpt-atlas
│       ├── atlas_gateway.py
│       ├── conftest.py
│       ├── pytest.ini
│       ├── README.md
│       ├── requirements.txt
│       ├── server.py
│       ├── test-requirements.txt
│       ├── tests
│       │   ├── conftest.py
│       │   ├── test_atlas_gateway.py
│       │   └── test_mcp_server.py
│       └── web
│           └── atlas-card.html
├── pyproject.toml
├── README.md
├── RELEASING.md
├── scripts
│   ├── atlas-governor-service-run.cmd
│   ├── atlas-governor-service-run.sh
│   ├── demo.ps1
│   ├── verify_dep_integrity.py
│   └── windows
│       ├── _AtlasCommon.ps1
│       ├── atlas-onboard.ps1
│       ├── atlas-preflight.ps1
│       ├── atlas-start.ps1
│       ├── atlas-stop.ps1
│       └── tests
│           ├── Test-EnvIsolation.ps1
│           └── Test-ProcessIdentity.ps1
├── SECURITY.md
├── src
│   ├── atlas_contracts
│   │   ├── agent_event.py
│   │   ├── event_package.py
│   │   ├── identity.py
│   │   ├── __init__.py
│   │   ├── paths.py
│   │   ├── provenance.py
│   │   ├── __pycache__
│   │   │   ├── agent_event.cpython-312.pyc
│   │   │   ├── event_package.cpython-312.pyc
│   │   │   ├── identity.cpython-312.pyc
│   │   │   ├── __init__.cpython-312.pyc
│   │   │   ├── paths.cpython-312.pyc
│   │   │   ├── provenance.cpython-312.pyc
│   │   │   ├── receipts.cpython-312.pyc
│   │   │   └── versions.cpython-312.pyc
│   │   ├── receipts.py
│   │   ├── schemas
│   │   │   ├── agent-event.schema.json
│   │   │   ├── event-package.schema.json
│   │   │   ├── provenance.schema.json
│   │   │   └── receipt-reference.schema.json
│   │   └── versions.py
│   ├── project_atlas
│   │   ├── adv_release_cert.py
│   │   ├── agent_eval_shadow.py
│   │   ├── agent_handoff.py
│   │   ├── agentos.py
│   │   ├── agentos_transitions.py
│   │   ├── api_server.py
│   │   ├── api_surface_registry.py
│   │   ├── app_service.py
│   │   ├── ask2.py
│   │   ├── ask_atlas_live.py
│   │   ├── atlas3
│   │   │   ├── adv_bind.py
│   │   │   ├── autonomy_gate.py
│   │   │   ├── capabilities.py
│   │   │   ├── causal.py
│   │   │   ├── claim_nodes.py
│   │   │   ├── cli.py
│   │   │   ├── compat.py
│   │   │   ├── conflict_unknown.py
│   │   │   ├── contracts.py
│   │   │   ├── decided.py
│   │   │   ├── decision_explorer.py
│   │   │   ├── domain.py
│   │   │   ├── engineering_nodes.py
│   │   │   ├── estate_nodes.py
│   │   │   ├── events.py
│   │   │   ├── federation_reuse.py
│   │   │   ├── file_graph.py
│   │   │   ├── foundation.py
│   │   │   ├── graph_authority.py
│   │   │   ├── home.py
│   │   │   ├── impact.py
│   │   │   ├── impact_ux.py
│   │   │   ├── __init__.py
│   │   │   ├── inventory.py
│   │   │   ├── iv_bind.py
│   │   │   ├── ledger_obs.py
│   │   │   ├── ledger.py
│   │   │   ├── memory
│   │   │   │   ├── chatgpt.py
│   │   │   │   ├── claude.py
│   │   │   │   ├── codex.py
│   │   │   │   ├── compiler.py
│   │   │   │   ├── conflicts.py
│   │   │   │   ├── connector.py
│   │   │   │   ├── context_compiler.py
│   │   │   │   ├── context_serve.py
│   │   │   │   ├── cursor.py
│   │   │   │   ├── dedup.py
│   │   │   │   ├── envelope.py
│   │   │   │   ├── extract.py
│   │   │   │   ├── freshness.py
│   │   │   │   ├── gemini.py
│   │   │   │   ├── handoff.py
│   │   │   │   ├── honesty.py
│   │   │   │   ├── incremental.py
│   │   │   │   ├── __init__.py
│   │   │   │   ├── intent.py
│   │   │   │   ├── lineage.py
│   │   │   │   ├── normalize.py
│   │   │   │   ├── pipeline.py
│   │   │   │   ├── privacy.py
│   │   │   │   ├── providers.py
│   │   │   │   ├── __pycache__
│   │   │   │   │   ├── chatgpt.cpython-312.pyc
│   │   │   │   │   ├── claude.cpython-312.pyc
│   │   │   │   │   ├── codex.cpython-312.pyc
│   │   │   │   │   ├── compiler.cpython-312.pyc
│   │   │   │   │   ├── conflicts.cpython-312.pyc
│   │   │   │   │   ├── connector.cpython-312.pyc
│   │   │   │   │   ├── context_compiler.cpython-312.pyc
│   │   │   │   │   ├── context_serve.cpython-312.pyc
│   │   │   │   │   ├── cursor.cpython-312.pyc
│   │   │   │   │   ├── dedup.cpython-312.pyc
│   │   │   │   │   ├── envelope.cpython-312.pyc
│   │   │   │   │   ├── freshness.cpython-312.pyc
│   │   │   │   │   ├── gemini.cpython-312.pyc
│   │   │   │   │   ├── honesty.cpython-312.pyc
│   │   │   │   │   ├── incremental.cpython-312.pyc
│   │   │   │   │   ├── __init__.cpython-312.pyc
│   │   │   │   │   ├── intent.cpython-312.pyc
│   │   │   │   │   ├── lineage.cpython-312.pyc
│   │   │   │   │   ├── normalize.cpython-312.pyc
│   │   │   │   │   ├── privacy.cpython-312.pyc
│   │   │   │   │   ├── providers.cpython-312.pyc
│   │   │   │   │   ├── reconcile.cpython-312.pyc
│   │   │   │   │   ├── routing.cpython-312.pyc
│   │   │   │   │   └── search.cpython-312.pyc
│   │   │   │   ├── reconcile.py
│   │   │   │   ├── routing.py
│   │   │   │   └── search.py
│   │   │   ├── mission.py
│   │   │   ├── multi_project.py
│   │   │   ├── next_honesty.py
│   │   │   ├── org_identity.py
│   │   │   ├── proof.py
│   │   │   ├── provider_register.py
│   │   │   ├── provider_sync.py
│   │   │   ├── pulse.py
│   │   │   ├── __pycache__
│   │   │   │   ├── adv_bind.cpython-312.pyc
│   │   │   │   ├── capabilities.cpython-312.pyc
│   │   │   │   ├── causal.cpython-312.pyc
│   │   │   │   ├── claim_nodes.cpython-312.pyc
│   │   │   │   ├── cli.cpython-312.pyc
│   │   │   │   ├── compat.cpython-312.pyc
│   │   │   │   ├── conflict_unknown.cpython-312.pyc
│   │   │   │   ├── contracts.cpython-312.pyc
│   │   │   │   ├── decided.cpython-312.pyc
│   │   │   │   ├── decision_explorer.cpython-312.pyc
│   │   │   │   ├── domain.cpython-312.pyc
│   │   │   │   ├── engineering_nodes.cpython-312.pyc
│   │   │   │   ├── estate_nodes.cpython-312.pyc
│   │   │   │   ├── events.cpython-312.pyc
│   │   │   │   ├── file_graph.cpython-312.pyc
│   │   │   │   ├── graph_authority.cpython-312.pyc
│   │   │   │   ├── home.cpython-312.pyc
│   │   │   │   ├── impact.cpython-312.pyc
│   │   │   │   ├── __init__.cpython-312.pyc
│   │   │   │   ├── inventory.cpython-312.pyc
│   │   │   │   ├── iv_bind.cpython-312.pyc
│   │   │   │   ├── ledger.cpython-312.pyc
│   │   │   │   ├── mission.cpython-312.pyc
│   │   │   │   ├── multi_project.cpython-312.pyc
│   │   │   │   ├── org_identity.cpython-312.pyc
│   │   │   │   ├── proof.cpython-312.pyc
│   │   │   │   ├── provider_register.cpython-312.pyc
│   │   │   │   ├── pulse.cpython-312.pyc
│   │   │   │   ├── rel_expand.cpython-312.pyc
│   │   │   │   ├── start.cpython-312.pyc
│   │   │   │   ├── surface.cpython-312.pyc
│   │   │   │   ├── timeline.cpython-312.pyc
│   │   │   │   ├── transport.cpython-312.pyc
│   │   │   │   ├── truth_graph.cpython-312.pyc
│   │   │   │   ├── twin.cpython-312.pyc
│   │   │   │   └── twin_health.cpython-312.pyc
│   │   │   ├── rel_expand.py
│   │   │   ├── security_catalog.py
│   │   │   ├── security.py
│   │   │   ├── stale_conflict.py
│   │   │   ├── start.py
│   │   │   ├── surface.py
│   │   │   ├── timeline.py
│   │   │   ├── time_machine_ux.py
│   │   │   ├── transport.py
│   │   │   ├── truth_graph.py
│   │   │   ├── twin_health.py
│   │   │   └── twin.py
│   │   ├── attention_hygiene.py
│   │   ├── authority_evaluator.py
│   │   ├── authority_registry.py
│   │   ├── authority_roles.py
│   │   ├── authz.py
│   │   ├── autonomy_l3.py
│   │   ├── autonomy_levels.py
│   │   ├── backup.py
│   │   ├── bitemporal_catalog.py
│   │   ├── bitemporal.py
│   │   ├── capture_io.py
│   │   ├── capture_sources.py
│   │   ├── chatgpt_bridge.py
│   │   ├── chatgpt_capture.py
│   │   ├── claim_identity.py
│   │   ├── classification.py
│   │   ├── cli.py
│   │   ├── collab_live.py
│   │   ├── collaboration_stubs.py
│   │   ├── compat_anchor.py
│   │   ├── compilation.py
│   │   ├── compile_cache.py
│   │   ├── config.py
│   │   ├── conflict_projections.py
│   │   ├── connect_perf.py
│   │   ├── connect.py
│   │   ├── context_pack_composition.py
│   │   ├── context_pack.py
│   │   ├── conversation_capture.py
│   │   ├── data
│   │   │   ├── autonomy-trusted-anchor-initial.json
│   │   │   └── final-cert-pilot-waiver.json
│   │   ├── demo_readiness.py
│   │   ├── discovery.py
│   │   ├── doctor.py
│   │   ├── dogfood_compiler_coverage.py
│   │   ├── domain
│   │   │   ├── authority_semantics.py
│   │   │   ├── claims.py
│   │   │   ├── concepts.py
│   │   │   ├── conflicts.py
│   │   │   ├── diagnostics.py
│   │   │   ├── findings.py
│   │   │   ├── __init__.py
│   │   │   ├── knowledge_query.py
│   │   │   ├── parser_output.py
│   │   │   ├── __pycache__
│   │   │   │   ├── authority_semantics.cpython-312.pyc
│   │   │   │   ├── claims.cpython-312.pyc
│   │   │   │   ├── concepts.cpython-312.pyc
│   │   │   │   ├── conflicts.cpython-312.pyc
│   │   │   │   ├── diagnostics.cpython-312.pyc
│   │   │   │   ├── findings.cpython-312.pyc
│   │   │   │   ├── __init__.cpython-312.pyc
│   │   │   │   ├── knowledge_query.cpython-312.pyc
│   │   │   │   ├── parser_output.cpython-312.pyc
│   │   │   │   ├── relationships.cpython-312.pyc
│   │   │   │   ├── semantic.cpython-312.pyc
│   │   │   │   ├── semantic_subject.cpython-312.pyc
│   │   │   │   ├── source_registry.cpython-312.pyc
│   │   │   │   ├── sources.cpython-312.pyc
│   │   │   │   ├── temporal.cpython-312.pyc
│   │   │   │   └── vocabulary.cpython-312.pyc
│   │   │   ├── relationships.py
│   │   │   ├── semantic.py
│   │   │   ├── semantic_subject.py
│   │   │   ├── source_registry.py
│   │   │   ├── sources.py
│   │   │   ├── temporal.py
│   │   │   └── vocabulary.py
│   │   ├── estate_discovery.py
│   │   ├── estate_intel_fixture.py
│   │   ├── estate_path_index.py
│   │   ├── eval_substrate.py
│   │   ├── event_retention.py
│   │   ├── event_tombstones.py
│   │   ├── evidence_compiler.py
│   │   ├── evidence_profiles.py
│   │   ├── explain_graph_sidecars.py
│   │   ├── explain_receipts.py
│   │   ├── federation_lens.py
│   │   ├── federation.py
│   │   ├── final_cert_pilot.py
│   │   ├── fresh_agent_challenge.py
│   │   ├── full_product_demo.py
│   │   ├── graph_acceptance.py
│   │   ├── graph_projections.py
│   │   ├── graph_quarantine.py
│   │   ├── graph_relationships.py
│   │   ├── graph_resolution.py
│   │   ├── human_loop.py
│   │   ├── hybrid_retrieval.py
│   │   ├── impact_graph.py
│   │   ├── incremental_connect.py
│   │   ├── indexes.py
│   │   ├── ingestion.py
│   │   ├── __init__.py
│   │   ├── intelligence
│   │   │   ├── agent_context.py
│   │   │   ├── boundary.py
│   │   │   ├── change.py
│   │   │   ├── contradictions.py
│   │   │   ├── decision.py
│   │   │   ├── delta.py
│   │   │   ├── dependencies.py
│   │   │   ├── derived_state.py
│   │   │   ├── evidence.py
│   │   │   ├── explain_graph.py
│   │   │   ├── explain.py
│   │   │   ├── gap_priority.py
│   │   │   ├── gaps.py
│   │   │   ├── handoff.py
│   │   │   ├── __init__.py
│   │   │   ├── next_action.py
│   │   │   ├── normalize.py
│   │   │   ├── observe.py
│   │   │   ├── portfolio_attention.py
│   │   │   ├── portfolio_deps.py
│   │   │   ├── portfolio.py
│   │   │   ├── __pycache__
│   │   │   │   ├── agent_context.cpython-312.pyc
│   │   │   │   ├── boundary.cpython-312.pyc
│   │   │   │   ├── change.cpython-312.pyc
│   │   │   │   ├── contradictions.cpython-312.pyc
│   │   │   │   ├── decision.cpython-312.pyc
│   │   │   │   ├── delta.cpython-312.pyc
│   │   │   │   ├── dependencies.cpython-312.pyc
│   │   │   │   ├── derived_state.cpython-312.pyc
│   │   │   │   ├── evidence.cpython-312.pyc
│   │   │   │   ├── explain.cpython-312.pyc
│   │   │   │   ├── explain_graph.cpython-312.pyc
│   │   │   │   ├── gap_priority.cpython-312.pyc
│   │   │   │   ├── gaps.cpython-312.pyc
│   │   │   │   ├── handoff.cpython-312.pyc
│   │   │   │   ├── __init__.cpython-312.pyc
│   │   │   │   ├── next_action.cpython-312.pyc
│   │   │   │   ├── normalize.cpython-312.pyc
│   │   │   │   ├── observe.cpython-312.pyc
│   │   │   │   ├── portfolio_attention.cpython-312.pyc
│   │   │   │   ├── portfolio.cpython-312.pyc
│   │   │   │   ├── portfolio_deps.cpython-312.pyc
│   │   │   │   ├── query.cpython-312.pyc
│   │   │   │   ├── risk.cpython-312.pyc
│   │   │   │   ├── temporal_intel.cpython-312.pyc
│   │   │   │   ├── timewin.cpython-312.pyc
│   │   │   │   └── types.cpython-312.pyc
│   │   │   ├── query.py
│   │   │   ├── risk.py
│   │   │   ├── temporal_intel.py
│   │   │   ├── timewin.py
│   │   │   └── types.py
│   │   ├── inventory_drift.py
│   │   ├── kci.py
│   │   ├── kf2_fabric.py
│   │   ├── kf2_inventory.py
│   │   ├── knowledge_ci_harness.py
│   │   ├── knowledge_compiler.py
│   │   ├── knowledge_diff.py
│   │   ├── knowledge_inbox.py
│   │   ├── knowledge_query.py
│   │   ├── lifecycle_cert.py
│   │   ├── lineage.py
│   │   ├── locator_migration.py
│   │   ├── logging.py
│   │   ├── mcp_registry.py
│   │   ├── mcp_server.py
│   │   ├── migrations
│   │   │   ├── claim_v2_migration.py
│   │   │   ├── __init__.py
│   │   │   └── __pycache__
│   │   │       ├── claim_v2_migration.cpython-312.pyc
│   │   │       └── __init__.cpython-312.pyc
│   │   ├── obsidian_capture_note.py
│   │   ├── obsidian_capture.py
│   │   ├── obsidian_projection.py
│   │   ├── obsidian_ux.py
│   │   ├── obsidian_workspace.py
│   │   ├── obs_live.py
│   │   ├── obs_perf.py
│   │   ├── okf_renderer.py
│   │   ├── openai_importer_fixtures.py
│   │   ├── openai_import_path.py
│   │   ├── openai_import_real.py
│   │   ├── openai_responses_poc.py
│   │   ├── ops_events.py
│   │   ├── ops_health.py
│   │   ├── ops_receipts.py
│   │   ├── ops_report.py
│   │   ├── opt_gate.py
│   │   ├── orchestration
│   │   │   ├── agent_transport.py
│   │   │   ├── autonomy
│   │   │   │   ├── adversarial.py
│   │   │   │   ├── authentic_estate.py
│   │   │   │   ├── cli.py
│   │   │   │   ├── continuation_broker.py
│   │   │   │   ├── continuation.py
│   │   │   │   ├── dag.py
│   │   │   │   ├── discovery.py
│   │   │   │   ├── evidence.py
│   │   │   │   ├── exact_main_closure.py
│   │   │   │   ├── governor.py
│   │   │   │   ├── __init__.py
│   │   │   │   ├── iv_routing.py
│   │   │   │   ├── lease_projection.py
│   │   │   │   ├── lease_recovery.py
│   │   │   │   ├── leases.py
│   │   │   │   ├── local_dispatch_port.py
│   │   │   │   ├── loop.py
│   │   │   │   ├── models.py
│   │   │   │   ├── overlap.py
│   │   │   │   ├── owner_gates.py
│   │   │   │   ├── __pycache__
│   │   │   │   │   ├── adversarial.cpython-312.pyc
│   │   │   │   │   ├── continuation.cpython-312.pyc
│   │   │   │   │   ├── dag.cpython-312.pyc
│   │   │   │   │   ├── discovery.cpython-312.pyc
│   │   │   │   │   ├── evidence.cpython-312.pyc
│   │   │   │   │   ├── governor.cpython-312.pyc
│   │   │   │   │   ├── __init__.cpython-312.pyc
│   │   │   │   │   ├── iv_routing.cpython-312.pyc
│   │   │   │   │   ├── lease_projection.cpython-312.pyc
│   │   │   │   │   ├── leases.cpython-312.pyc
│   │   │   │   │   ├── models.cpython-312.pyc
│   │   │   │   │   ├── overlap.cpython-312.pyc
│   │   │   │   │   ├── owner_gates.cpython-312.pyc
│   │   │   │   │   ├── remediation.cpython-312.pyc
│   │   │   │   │   └── trust.cpython-312.pyc
│   │   │   │   ├── rehydration.py
│   │   │   │   ├── remediation.py
│   │   │   │   ├── return_gate.py
│   │   │   │   └── trust.py
│   │   │   ├── cursor_bridge.py
│   │   │   ├── dispatcher.py
│   │   │   ├── __init__.py
│   │   │   ├── live_integration
│   │   │   │   ├── bridge.py
│   │   │   │   ├── cli.py
│   │   │   │   ├── __init__.py
│   │   │   │   ├── models.py
│   │   │   │   └── __pycache__
│   │   │   │       ├── bridge.cpython-312.pyc
│   │   │   │       ├── cli.cpython-312.pyc
│   │   │   │       ├── __init__.cpython-312.pyc
│   │   │   │       └── models.cpython-312.pyc
│   │   │   ├── local_process_transport.py
│   │   │   ├── models.py
│   │   │   ├── origination
│   │   │   │   ├── acceptance_contracts.py
│   │   │   │   ├── adapter.py
│   │   │   │   ├── cli.py
│   │   │   │   ├── facts.py
│   │   │   │   ├── identity.py
│   │   │   │   ├── __init__.py
│   │   │   │   ├── materialize.py
│   │   │   │   ├── pipeline.py
│   │   │   │   ├── policy.py
│   │   │   │   ├── projection.py
│   │   │   │   ├── proposal.py
│   │   │   │   ├── __pycache__
│   │   │   │   │   ├── acceptance_contracts.cpython-312.pyc
│   │   │   │   │   ├── adapter.cpython-312.pyc
│   │   │   │   │   ├── cli.cpython-312.pyc
│   │   │   │   │   ├── facts.cpython-312.pyc
│   │   │   │   │   ├── identity.cpython-312.pyc
│   │   │   │   │   ├── __init__.cpython-312.pyc
│   │   │   │   │   ├── materialize.cpython-312.pyc
│   │   │   │   │   ├── pipeline.cpython-312.pyc
│   │   │   │   │   ├── policy.cpython-312.pyc
│   │   │   │   │   ├── projection.cpython-312.pyc
│   │   │   │   │   ├── proposal.cpython-312.pyc
│   │   │   │   │   ├── risk.cpython-312.pyc
│   │   │   │   │   ├── sources.cpython-312.pyc
│   │   │   │   │   └── tasklist_adapter.cpython-312.pyc
│   │   │   │   ├── risk.py
│   │   │   │   ├── sources.py
│   │   │   │   └── tasklist_adapter.py
│   │   │   ├── policy.py
│   │   │   ├── program
│   │   │   │   ├── acceptance.py
│   │   │   │   ├── adapters
│   │   │   │   │   ├── base.py
│   │   │   │   │   ├── claude_code.py
│   │   │   │   │   ├── codex.py
│   │   │   │   │   ├── __init__.py
│   │   │   │   │   ├── local_command.py
│   │   │   │   │   └── __pycache__
│   │   │   │   │       ├── base.cpython-312.pyc
│   │   │   │   │       ├── claude_code.cpython-312.pyc
│   │   │   │   │       ├── codex.cpython-312.pyc
│   │   │   │   │       ├── __init__.cpython-312.pyc
│   │   │   │   │       └── local_command.cpython-312.pyc
│   │   │   │   ├── cli.py
│   │   │   │   ├── control.py
│   │   │   │   ├── credentials.py
│   │   │   │   ├── enrollment.py
│   │   │   │   ├── __init__.py
│   │   │   │   ├── loader.py
│   │   │   │   ├── models.py
│   │   │   │   ├── profiles.py
│   │   │   │   ├── __pycache__
│   │   │   │   │   ├── acceptance.cpython-312.pyc
│   │   │   │   │   ├── cli.cpython-312.pyc
│   │   │   │   │   ├── control.cpython-312.pyc
│   │   │   │   │   ├── credentials.cpython-312.pyc
│   │   │   │   │   ├── enrollment.cpython-312.pyc
│   │   │   │   │   ├── __init__.cpython-312.pyc
│   │   │   │   │   ├── loader.cpython-312.pyc
│   │   │   │   │   ├── models.cpython-312.pyc
│   │   │   │   │   ├── profiles.cpython-312.pyc
│   │   │   │   │   ├── recovery.cpython-312.pyc
│   │   │   │   │   ├── runtimes.cpython-312.pyc
│   │   │   │   │   ├── service.cpython-312.pyc
│   │   │   │   │   ├── store.cpython-312.pyc
│   │   │   │   │   ├── supervisor.cpython-312.pyc
│   │   │   │   │   └── waiting.cpython-312.pyc
│   │   │   │   ├── recovery.py
│   │   │   │   ├── runtimes.py
│   │   │   │   ├── service.py
│   │   │   │   ├── store.py
│   │   │   │   ├── supervisor.py
│   │   │   │   └── waiting.py
│   │   │   ├── __pycache__
│   │   │   │   ├── agent_transport.cpython-312.pyc
│   │   │   │   ├── cursor_bridge.cpython-312.pyc
│   │   │   │   ├── dispatcher.cpython-312.pyc
│   │   │   │   ├── __init__.cpython-312.pyc
│   │   │   │   ├── models.cpython-312.pyc
│   │   │   │   ├── policy.cpython-312.pyc
│   │   │   │   ├── router.cpython-312.pyc
│   │   │   │   ├── transitions.cpython-312.pyc
│   │   │   │   └── validator.cpython-312.pyc
│   │   │   ├── router.py
│   │   │   ├── sdk
│   │   │   │   ├── audit_provenance.py
│   │   │   │   ├── auth.py
│   │   │   │   ├── backend.py
│   │   │   │   ├── ci_observer.py
│   │   │   │   ├── cli_execution_port.py
│   │   │   │   ├── cli.py
│   │   │   │   ├── closed_loop_port.py
│   │   │   │   ├── cloud_run_recovery.py
│   │   │   │   ├── cost_guard.py
│   │   │   │   ├── event_log.py
│   │   │   │   ├── external_observers.py
│   │   │   │   ├── host.py
│   │   │   │   ├── idempotency.py
│   │   │   │   ├── __init__.py
│   │   │   │   ├── lease_registry.py
│   │   │   │   ├── live_dag.py
│   │   │   │   ├── local_proof.py
│   │   │   │   ├── merge_sequence_gate.py
│   │   │   │   ├── mission_reconciler.py
│   │   │   │   ├── models.py
│   │   │   │   ├── mutation_attribution.py
│   │   │   │   ├── nonblocking_scheduler.py
│   │   │   │   ├── package_registry.py
│   │   │   │   ├── __pycache__
│   │   │   │   │   ├── audit_provenance.cpython-312.pyc
│   │   │   │   │   ├── auth.cpython-312.pyc
│   │   │   │   │   ├── backend.cpython-312.pyc
│   │   │   │   │   ├── ci_observer.cpython-312.pyc
│   │   │   │   │   ├── cli_execution_port.cpython-312.pyc
│   │   │   │   │   ├── cloud_run_recovery.cpython-312.pyc
│   │   │   │   │   ├── cost_guard.cpython-312.pyc
│   │   │   │   │   ├── event_log.cpython-312.pyc
│   │   │   │   │   ├── external_observers.cpython-312.pyc
│   │   │   │   │   ├── host.cpython-312.pyc
│   │   │   │   │   ├── idempotency.cpython-312.pyc
│   │   │   │   │   ├── __init__.cpython-312.pyc
│   │   │   │   │   ├── lease_registry.cpython-312.pyc
│   │   │   │   │   ├── live_dag.cpython-312.pyc
│   │   │   │   │   ├── models.cpython-312.pyc
│   │   │   │   │   ├── mutation_attribution.cpython-312.pyc
│   │   │   │   │   ├── nonblocking_scheduler.cpython-312.pyc
│   │   │   │   │   ├── package_registry.cpython-312.pyc
│   │   │   │   │   ├── recovery.cpython-312.pyc
│   │   │   │   │   ├── registries.cpython-312.pyc
│   │   │   │   │   ├── result_adapter.cpython-312.pyc
│   │   │   │   │   ├── result_plane.cpython-312.pyc
│   │   │   │   │   ├── role_pool.cpython-312.pyc
│   │   │   │   │   ├── scheduler.cpython-312.pyc
│   │   │   │   │   ├── security_gates.cpython-312.pyc
│   │   │   │   │   └── supervisor.cpython-312.pyc
│   │   │   │   ├── recovery.py
│   │   │   │   ├── registries.py
│   │   │   │   ├── resident_driver.py
│   │   │   │   ├── resident_mission.py
│   │   │   │   ├── resident_status.py
│   │   │   │   ├── resident_windows.py
│   │   │   │   ├── result_adapter.py
│   │   │   │   ├── result_plane.py
│   │   │   │   ├── role_pool.py
│   │   │   │   ├── scheduler.py
│   │   │   │   ├── security_gates.py
│   │   │   │   ├── speculative_certification_oracle.py
│   │   │   │   ├── speculative_certification.py
│   │   │   │   ├── supervisor.py
│   │   │   │   └── windows_bridge.py
│   │   │   ├── taskcontract
│   │   │   │   ├── cli.py
│   │   │   │   ├── diff.py
│   │   │   │   ├── draft.py
│   │   │   │   ├── __init__.py
│   │   │   │   ├── models.py
│   │   │   │   ├── __pycache__
│   │   │   │   │   ├── cli.cpython-312.pyc
│   │   │   │   │   ├── diff.cpython-312.pyc
│   │   │   │   │   ├── draft.cpython-312.pyc
│   │   │   │   │   ├── __init__.cpython-312.pyc
│   │   │   │   │   ├── models.cpython-312.pyc
│   │   │   │   │   ├── render.cpython-312.pyc
│   │   │   │   │   └── validate.cpython-312.pyc
│   │   │   │   ├── render.py
│   │   │   │   └── validate.py
│   │   │   ├── transitions.py
│   │   │   ├── validator.py
│   │   │   └── work_readiness
│   │   │       ├── adapters.py
│   │   │       ├── backlog_reader.py
│   │   │       ├── capacity.py
│   │   │       ├── cli.py
│   │   │       ├── handoff.py
│   │   │       ├── __init__.py
│   │   │       ├── models.py
│   │   │       ├── project.py
│   │   │       ├── __pycache__
│   │   │       │   ├── adapters.cpython-312.pyc
│   │   │       │   ├── backlog_reader.cpython-312.pyc
│   │   │       │   ├── capacity.cpython-312.pyc
│   │   │       │   ├── cli.cpython-312.pyc
│   │   │       │   ├── handoff.cpython-312.pyc
│   │   │       │   ├── __init__.cpython-312.pyc
│   │   │       │   ├── models.cpython-312.pyc
│   │   │       │   ├── project.cpython-312.pyc
│   │   │       │   └── select.cpython-312.pyc
│   │   │       └── select.py
│   │   ├── overview.py
│   │   ├── parser_registry.py
│   │   ├── perf_baselines.py
│   │   ├── pilot_auth_prep.py
│   │   ├── portfolio.py
│   │   ├── project_architecture.py
│   │   ├── project_brief.py
│   │   ├── project_changed.py
│   │   ├── project_decisions.py
│   │   ├── project_next.py
│   │   ├── project_roadmap.py
│   │   ├── project_state.py
│   │   ├── project_unknown.py
│   │   ├── protected_regions.py
│   │   ├── provider_adapters.py
│   │   ├── provider_live.py
│   │   ├── __pycache__
│   │   │   ├── adv_release_cert.cpython-312.pyc
│   │   │   ├── agent_handoff.cpython-312.pyc
│   │   │   ├── api_server.cpython-312.pyc
│   │   │   ├── app_service.cpython-312.pyc
│   │   │   ├── ask2.cpython-312.pyc
│   │   │   ├── ask_atlas_live.cpython-312.pyc
│   │   │   ├── attention_hygiene.cpython-312.pyc
│   │   │   ├── authority_evaluator.cpython-312.pyc
│   │   │   ├── authority_registry.cpython-312.pyc
│   │   │   ├── authority_roles.cpython-312.pyc
│   │   │   ├── authz.cpython-312.pyc
│   │   │   ├── autonomy_l3.cpython-312.pyc
│   │   │   ├── backup.cpython-312.pyc
│   │   │   ├── bitemporal_catalog.cpython-312.pyc
│   │   │   ├── bitemporal.cpython-312.pyc
│   │   │   ├── capture_io.cpython-312.pyc
│   │   │   ├── capture_sources.cpython-312.pyc
│   │   │   ├── claim_identity.cpython-312.pyc
│   │   │   ├── classification.cpython-312.pyc
│   │   │   ├── cli.cpython-312.pyc
│   │   │   ├── compat_anchor.cpython-312.pyc
│   │   │   ├── compilation.cpython-312.pyc
│   │   │   ├── config.cpython-312.pyc
│   │   │   ├── conflict_projections.cpython-312.pyc
│   │   │   ├── connect.cpython-312.pyc
│   │   │   ├── context_pack.cpython-312.pyc
│   │   │   ├── conversation_capture.cpython-312.pyc
│   │   │   ├── discovery.cpython-312.pyc
│   │   │   ├── doctor.cpython-312.pyc
│   │   │   ├── dogfood_compiler_coverage.cpython-312.pyc
│   │   │   ├── estate_discovery.cpython-312.pyc
│   │   │   ├── estate_path_index.cpython-312.pyc
│   │   │   ├── event_retention.cpython-312.pyc
│   │   │   ├── evidence_compiler.cpython-312.pyc
│   │   │   ├── evidence_profiles.cpython-312.pyc
│   │   │   ├── federation.cpython-312.pyc
│   │   │   ├── graph_acceptance.cpython-312.pyc
│   │   │   ├── graph_relationships.cpython-312.pyc
│   │   │   ├── graph_resolution.cpython-312.pyc
│   │   │   ├── human_loop.cpython-312.pyc
│   │   │   ├── hybrid_retrieval.cpython-312.pyc
│   │   │   ├── incremental_connect.cpython-312.pyc
│   │   │   ├── indexes.cpython-312.pyc
│   │   │   ├── ingestion.cpython-312.pyc
│   │   │   ├── __init__.cpython-312.pyc
│   │   │   ├── inventory_drift.cpython-312.pyc
│   │   │   ├── kci.cpython-312.pyc
│   │   │   ├── kf2_fabric.cpython-312.pyc
│   │   │   ├── knowledge_compiler.cpython-312.pyc
│   │   │   ├── knowledge_diff.cpython-312.pyc
│   │   │   ├── knowledge_inbox.cpython-312.pyc
│   │   │   ├── knowledge_query.cpython-312.pyc
│   │   │   ├── lifecycle_cert.cpython-312.pyc
│   │   │   ├── lineage.cpython-312.pyc
│   │   │   ├── logging.cpython-312.pyc
│   │   │   ├── mcp_registry.cpython-312.pyc
│   │   │   ├── mcp_server.cpython-312.pyc
│   │   │   ├── obsidian_capture.cpython-312.pyc
│   │   │   ├── obsidian_capture_note.cpython-312.pyc
│   │   │   ├── obsidian_projection.cpython-312.pyc
│   │   │   ├── obs_live.cpython-312.pyc
│   │   │   ├── okf_renderer.cpython-312.pyc
│   │   │   ├── openai_importer_fixtures.cpython-312.pyc
│   │   │   ├── openai_import_real.cpython-312.pyc
│   │   │   ├── openai_responses_poc.cpython-312.pyc
│   │   │   ├── ops_events.cpython-312.pyc
│   │   │   ├── ops_health.cpython-312.pyc
│   │   │   ├── ops_receipts.cpython-312.pyc
│   │   │   ├── ops_report.cpython-312.pyc
│   │   │   ├── overview.cpython-312.pyc
│   │   │   ├── parser_registry.cpython-312.pyc
│   │   │   ├── perf_baselines.cpython-312.pyc
│   │   │   ├── pilot_auth_prep.cpython-312.pyc
│   │   │   ├── portfolio.cpython-312.pyc
│   │   │   ├── project_architecture.cpython-312.pyc
│   │   │   ├── project_brief.cpython-312.pyc
│   │   │   ├── project_changed.cpython-312.pyc
│   │   │   ├── project_decisions.cpython-312.pyc
│   │   │   ├── project_next.cpython-312.pyc
│   │   │   ├── project_roadmap.cpython-312.pyc
│   │   │   ├── project_state.cpython-312.pyc
│   │   │   ├── project_unknown.cpython-312.pyc
│   │   │   ├── protected_regions.cpython-312.pyc
│   │   │   ├── provider_adapters.cpython-312.pyc
│   │   │   ├── quarantine.cpython-312.pyc
│   │   │   ├── query_plan.cpython-312.pyc
│   │   │   ├── receipt_revocation.cpython-312.pyc
│   │   │   ├── retrieval.cpython-312.pyc
│   │   │   ├── retrieval_fusion.cpython-312.pyc
│   │   │   ├── runtime_22.cpython-312.pyc
│   │   │   ├── scaffold.cpython-312.pyc
│   │   │   ├── scheduler_live.cpython-312.pyc
│   │   │   ├── schema_compat.cpython-312.pyc
│   │   │   ├── schema.cpython-312.pyc
│   │   │   ├── secrets.cpython-312.pyc
│   │   │   ├── semantic_compiler.cpython-312.pyc
│   │   │   ├── session_capture.cpython-312.pyc
│   │   │   ├── source_health.cpython-312.pyc
│   │   │   ├── source_identity.cpython-312.pyc
│   │   │   ├── status_dimensions.cpython-312.pyc
│   │   │   ├── subject_derivation.cpython-312.pyc
│   │   │   ├── sync_plan.cpython-312.pyc
│   │   │   ├── temporal_evaluator.cpython-312.pyc
│   │   │   ├── temporal_evidence.cpython-312.pyc
│   │   │   ├── terminal_io.cpython-312.pyc
│   │   │   ├── twin_fixtures.cpython-312.pyc
│   │   │   ├── validation.cpython-312.pyc
│   │   │   ├── vault_identity.cpython-312.pyc
│   │   │   ├── verify_profile.cpython-312.pyc
│   │   │   ├── web_actions.cpython-312.pyc
│   │   │   ├── web_mission_workspace.cpython-312.pyc
│   │   │   ├── workspace_registry.cpython-312.pyc
│   │   │   ├── xproj_duplicates.cpython-312.pyc
│   │   │   ├── xproj_edges.cpython-312.pyc
│   │   │   ├── xproj_registry.cpython-312.pyc
│   │   │   └── yaml_structured.cpython-312.pyc
│   │   ├── py.typed
│   │   ├── quarantine.py
│   │   ├── query_plan.py
│   │   ├── reality_gap.py
│   │   ├── reality_gap_ui.py
│   │   ├── receipt_revocation.py
│   │   ├── retrieval_fusion.py
│   │   ├── retrieval.py
│   │   ├── runtime_22.py
│   │   ├── scaffold.py
│   │   ├── scale_harness.py
│   │   ├── scheduler_dry_run.py
│   │   ├── scheduler_live.py
│   │   ├── schema_compat.py
│   │   ├── schema.py
│   │   ├── schemas
│   │   │   ├── adv-release-cert-report.schema.json
│   │   │   ├── agent-eval-shadow-receipt.schema.json
│   │   │   ├── agentos-phase-transition.schema.json
│   │   │   ├── agentos-session-envelope.schema.json
│   │   │   ├── agent-result-envelope.schema.json
│   │   │   ├── api-surface-registry.schema.json
│   │   │   ├── ask-atlas-2-answer-lens.schema.json
│   │   │   ├── authority-record.schema.json
│   │   │   ├── autonomy-governor-report.schema.json
│   │   │   ├── autonomy-lease.schema.json
│   │   │   ├── autonomy-level-catalog.schema.json
│   │   │   ├── autonomy-loop-state.schema.json
│   │   │   ├── autonomy-trusted-anchor.schema.json
│   │   │   ├── autonomy-work-node.schema.json
│   │   │   ├── backup-manifest.schema.json
│   │   │   ├── backup-meta.schema.json
│   │   │   ├── backup-receipt.schema.json
│   │   │   ├── bitemporal-as-of-result.schema.json
│   │   │   ├── chatgpt-capture-receipt.schema.json
│   │   │   ├── claim-alias.schema.json
│   │   │   ├── claim-lifecycle.schema.json
│   │   │   ├── claim.schema.json
│   │   │   ├── claim-validity-catalog.schema.json
│   │   │   ├── claim-validity-window.schema.json
│   │   │   ├── collaboration-stub-registry.schema.json
│   │   │   ├── compatibility-anchor.schema.json
│   │   │   ├── compile-cache-receipt.schema.json
│   │   │   ├── concept-record.schema.json
│   │   │   ├── conflict-record.schema.json
│   │   │   ├── context-pack-composition.schema.json
│   │   │   ├── context-pack.schema.json
│   │   │   ├── conversation-capture.schema.json
│   │   │   ├── diagnostic.schema.json
│   │   │   ├── dispatch-receipt.schema.json
│   │   │   ├── dispatch-record.schema.json
│   │   │   ├── estate-intel-fixture.schema.json
│   │   │   ├── eval-score-receipt.schema.json
│   │   │   ├── event-retention-policy.schema.json
│   │   │   ├── event-retention-report.schema.json
│   │   │   ├── event-tombstone-index.schema.json
│   │   │   ├── explain-graph-sidecar.schema.json
│   │   │   ├── explain-receipt.schema.json
│   │   │   ├── federation-join-inventory.schema.json
│   │   │   ├── federation-read-lens.schema.json
│   │   │   ├── graph-acceptance-receipt.schema.json
│   │   │   ├── graph-health-snapshot.schema.json
│   │   │   ├── graph-identity-explanation.schema.json
│   │   │   ├── graphify-edge.schema.json
│   │   │   ├── graphify-envelope.schema.json
│   │   │   ├── graphify-metadata.schema.json
│   │   │   ├── graphify-node.schema.json
│   │   │   ├── graph-incremental-state.schema.json
│   │   │   ├── graph-quarantine-receipt.schema.json
│   │   │   ├── graph-quarantine-record.schema.json
│   │   │   ├── graph-relationship-quarantine.schema.json
│   │   │   ├── graph-relationship.schema.json
│   │   │   ├── graph-resolved-node.schema.json
│   │   │   ├── handoff-packet.schema.json
│   │   │   ├── hybrid-retrieval-plan.schema.json
│   │   │   ├── hybrid-retrieval-rrf.schema.json
│   │   │   ├── impact-graph.schema.json
│   │   │   ├── kci-compile-receipt.schema.json
│   │   │   ├── kci-compile-request.schema.json
│   │   │   ├── kdiff-as-of-snapshot.schema.json
│   │   │   ├── kdiff-record.schema.json
│   │   │   ├── kf2-entity.schema.json
│   │   │   ├── kf2-fabric-inventory.schema.json
│   │   │   ├── kf2-namespace.schema.json
│   │   │   ├── kf2-relationship.schema.json
│   │   │   ├── knowledge-answer.schema.json
│   │   │   ├── knowledge-ci-harness.schema.json
│   │   │   ├── knowledge-inbox-receipt.schema.json
│   │   │   ├── knowledge-multifield-answer.schema.json
│   │   │   ├── lifecycle-cert-report.schema.json
│   │   │   ├── mcp-tool-registry.schema.json
│   │   │   ├── obsidian-lens-registry.schema.json
│   │   │   ├── obsidian-workspace-binding.schema.json
│   │   │   ├── openai-import-fixture-receipt.schema.json
│   │   │   ├── openai-import-path-receipt.schema.json
│   │   │   ├── ops-event.schema.json
│   │   │   ├── ops-event-stream.schema.json
│   │   │   ├── ops-health-snapshot.schema.json
│   │   │   ├── ops-report.schema.json
│   │   │   ├── opt-experiment-receipt.schema.json
│   │   │   ├── orchestration-route.schema.json
│   │   │   ├── parser-output.schema.json
│   │   │   ├── project-roadmap.schema.json
│   │   │   ├── provenance-reference.schema.json
│   │   │   ├── provider-adapter-registry.schema.json
│   │   │   ├── provider-quarantine-envelope.schema.json
│   │   │   ├── query-diagnostic.schema.json
│   │   │   ├── query-multi-plan.schema.json
│   │   │   ├── raw-capture.schema.json
│   │   │   ├── reality-gap-inventory.schema.json
│   │   │   ├── reality-gap-ui-catalog.schema.json
│   │   │   ├── receipt-revocation-index.schema.json
│   │   │   ├── review-entry.schema.json
│   │   │   ├── runtime-context-compiler.schema.json
│   │   │   ├── runtime-hybrid-retrieval.schema.json
│   │   │   ├── scale-harness-plan.schema.json
│   │   │   ├── scheduler-dry-run.schema.json
│   │   │   ├── schema-compat-report.schema.json
│   │   │   ├── scoring-broker-result.schema.json
│   │   │   ├── security-adv-matrix.schema.json
│   │   │   ├── security-continuous-receipt.schema.json
│   │   │   ├── semantic-records.schema.json
│   │   │   ├── source-record.schema.json
│   │   │   ├── source-registry.schema.json
│   │   │   ├── sync-plan-dry-run.schema.json
│   │   │   ├── sync-production-plan.schema.json
│   │   │   ├── sync-queue-dry-run.schema.json
│   │   │   ├── sync-receipts-dry-run.schema.json
│   │   │   ├── task-context-packet.schema.json
│   │   │   ├── task-directive.schema.json
│   │   │   ├── twin-fixture-scenario.schema.json
│   │   │   ├── twin-production-projection.schema.json
│   │   │   ├── twin-projection-fixture.schema.json
│   │   │   ├── ux-mode-catalog.schema.json
│   │   │   ├── validation-finding.schema.json
│   │   │   ├── web-ask-atlas-contract.schema.json
│   │   │   ├── web-surface-catalog.schema.json
│   │   │   ├── work-readiness-handoff.schema.json
│   │   │   ├── workspace-registry-dry-run.schema.json
│   │   │   ├── xproj-conflict-report.schema.json
│   │   │   ├── xproj-duplicate-candidate.schema.json
│   │   │   ├── xproj-edge-quarantine.schema.json
│   │   │   ├── xproj-global-edge.schema.json
│   │   │   ├── xproj-global-entity.schema.json
│   │   │   ├── xproj-index-document.schema.json
│   │   │   ├── xproj-join-key.schema.json
│   │   │   └── xproj-quarantine-candidate.schema.json
│   │   ├── scoring_broker.py
│   │   ├── scoring_broker_server.py
│   │   ├── secrets.py
│   │   ├── security_adv.py
│   │   ├── security_continuous.py
│   │   ├── semantic_compiler.py
│   │   ├── semantic_migration.py
│   │   ├── session_capture.py
│   │   ├── source_drift_scope.py
│   │   ├── source_health.py
│   │   ├── source_identity.py
│   │   ├── status_dimensions.py
│   │   ├── subject_derivation.py
│   │   ├── sync_plan.py
│   │   ├── sync_production.py
│   │   ├── sync_queue.py
│   │   ├── sync_receipts.py
│   │   ├── task_context
│   │   │   ├── adapters.py
│   │   │   ├── assemble.py
│   │   │   ├── budget.py
│   │   │   ├── cli.py
│   │   │   ├── compare.py
│   │   │   ├── freshness.py
│   │   │   ├── __init__.py
│   │   │   ├── models.py
│   │   │   ├── paths.py
│   │   │   ├── __pycache__
│   │   │   │   ├── adapters.cpython-312.pyc
│   │   │   │   ├── assemble.cpython-312.pyc
│   │   │   │   ├── budget.cpython-312.pyc
│   │   │   │   ├── cli.cpython-312.pyc
│   │   │   │   ├── compare.cpython-312.pyc
│   │   │   │   ├── freshness.cpython-312.pyc
│   │   │   │   ├── __init__.cpython-312.pyc
│   │   │   │   ├── models.cpython-312.pyc
│   │   │   │   ├── paths.cpython-312.pyc
│   │   │   │   ├── select.cpython-312.pyc
│   │   │   │   └── views.cpython-312.pyc
│   │   │   ├── select.py
│   │   │   └── views.py
│   │   ├── temporal_evaluator.py
│   │   ├── temporal_evidence.py
│   │   ├── terminal_io.py
│   │   ├── twin_fixture_scenarios.py
│   │   ├── twin_fixtures.py
│   │   ├── twin_production.py
│   │   ├── ux_mode_catalog.py
│   │   ├── validation.py
│   │   ├── vault_identity.py
│   │   ├── verify_profile.py
│   │   ├── web_actions.py
│   │   ├── web_api
│   │   │   ├── architecture.py
│   │   │   ├── architecture_read.py
│   │   │   ├── bitemporal_read.py
│   │   │   ├── brief.py
│   │   │   ├── changed_read.py
│   │   │   ├── conflicts.py
│   │   │   ├── decisions_read.py
│   │   │   ├── discovery.py
│   │   │   ├── graph.py
│   │   │   ├── health.py
│   │   │   ├── index_status.py
│   │   │   ├── __init__.py
│   │   │   ├── intelligence.py
│   │   │   ├── knowledge.py
│   │   │   ├── next_read.py
│   │   │   ├── overview_read.py
│   │   │   ├── portfolio_read.py
│   │   │   ├── projects.py
│   │   │   ├── __pycache__
│   │   │   │   ├── architecture.cpython-312.pyc
│   │   │   │   ├── architecture_read.cpython-312.pyc
│   │   │   │   ├── bitemporal_read.cpython-312.pyc
│   │   │   │   ├── brief.cpython-312.pyc
│   │   │   │   ├── changed_read.cpython-312.pyc
│   │   │   │   ├── conflicts.cpython-312.pyc
│   │   │   │   ├── decisions_read.cpython-312.pyc
│   │   │   │   ├── discovery.cpython-312.pyc
│   │   │   │   ├── graph.cpython-312.pyc
│   │   │   │   ├── health.cpython-312.pyc
│   │   │   │   ├── index_status.cpython-312.pyc
│   │   │   │   ├── __init__.cpython-312.pyc
│   │   │   │   ├── intelligence.cpython-312.pyc
│   │   │   │   ├── knowledge.cpython-312.pyc
│   │   │   │   ├── next_read.cpython-312.pyc
│   │   │   │   ├── overview_read.cpython-312.pyc
│   │   │   │   ├── portfolio_read.cpython-312.pyc
│   │   │   │   ├── projects.cpython-312.pyc
│   │   │   │   ├── roadmap.cpython-312.pyc
│   │   │   │   ├── roadmap_read.cpython-312.pyc
│   │   │   │   ├── source_health.cpython-312.pyc
│   │   │   │   ├── state_read.cpython-312.pyc
│   │   │   │   └── unknown_read.cpython-312.pyc
│   │   │   ├── roadmap.py
│   │   │   ├── roadmap_read.py
│   │   │   ├── source_health.py
│   │   │   ├── state_read.py
│   │   │   └── unknown_read.py
│   │   ├── web_ask_atlas.py
│   │   ├── web_mission_workspace.py
│   │   ├── web_surface_catalog.py
│   │   ├── workflow_metrics.py
│   │   ├── workspace_registry.py
│   │   ├── xproj_duplicates.py
│   │   ├── xproj_edges.py
│   │   ├── xproj_indexes.py
│   │   ├── xproj_registry.py
│   │   └── yaml_structured.py
│   └── project_atlas.egg-info
│       ├── dependency_links.txt
│       ├── entry_points.txt
│       ├── PKG-INFO
│       ├── requires.txt
│       ├── SOURCES.txt
│       └── top_level.txt
├── SUPPORT.md
├── tests
│   ├── fixtures
│   │   ├── adversarial-project
│   │   │   ├── adversarial-project-id-override.yaml
│   │   │   ├── benign-multiline-control.md
│   │   │   ├── benign-multilingual-separators-control.md
│   │   │   ├── canary-bearing.md
│   │   │   ├── carriage-return-mid-keyword-reproduction.md
│   │   │   ├── cyrillic-homoglyph.md
│   │   │   ├── diacritic-e-reproduction.md
│   │   │   ├── diacritic-i-reproduction.md
│   │   │   ├── diacritic-o-reproduction.md
│   │   │   ├── em-space-mid-keyword-reproduction.md
│   │   │   ├── em-space-reproduction.md
│   │   │   ├── form-feed-reproduction.md
│   │   │   ├── greek-iota-reproduction.md
│   │   │   ├── greek-omicron-reproduction.md
│   │   │   ├── instruction-bearing.md
│   │   │   ├── line-feed-mid-keyword-reproduction.md
│   │   │   ├── line-separator-mid-keyword-reproduction.md
│   │   │   ├── line-separator-reproduction.md
│   │   │   ├── no-break-space-reproduction.md
│   │   │   ├── non-adversarial-control.md
│   │   │   ├── paragraph-separator-mid-keyword-reproduction.md
│   │   │   ├── quoted-research.md
│   │   │   ├── README.md
│   │   │   ├── soft-hyphen-insertion.md
│   │   │   ├── tab-mid-keyword-reproduction.md
│   │   │   ├── uppercase-cyrillic-reproduction.md
│   │   │   ├── vertical-tab-reproduction.md
│   │   │   └── zero-width-insertion.md
│   │   ├── as-core-004
│   │   │   ├── CONFLICT-INVENTORY.json
│   │   │   └── real-fixtures
│   │   │       ├── conflict-0156b0179de3db14dfaf.md
│   │   │       ├── conflict-1206a69904bd485243c9.md
│   │   │       ├── conflict-45bf6f992b1f4bae833e.md
│   │   │       ├── conflict-6a2ddcbcb3748172eed8.md
│   │   │       ├── conflict-8f138e2b6c962499a740.md
│   │   │       ├── conflict-9e8effd046434b39e849.md
│   │   │       ├── conflict-e319b7924971dd6bcf10.md
│   │   │       ├── conflict-ee101ef66159eb9a35c4.md
│   │   │       └── conflict-f1b4b22b94985a86751a.md
│   │   ├── as-core-005
│   │   │   └── real-sources
│   │   │       ├── docs__evidence__AS-CORE-002-post-merge-receipt.yaml
│   │   │       ├── docs__evidence__AS-CORE-002-source-lifecycle-recertification.yaml
│   │   │       ├── docs__evidence__AS-CORE-003-claim-identity-amendment-plan.yaml
│   │   │       ├── docs__evidence__AS-CORE-003-receipt.yaml
│   │   │       ├── docs__evidence__AS-CORE-003-v2-candidate-003-review.yaml
│   │   │       ├── docs__evidence__AS-CORE-003-v2-candidate-003.yaml
│   │   │       ├── docs__evidence__AS-CORE-003-v2-candidate-004.yaml
│   │   │       ├── docs__evidence__AS-CORE-003-v2-candidate-005-review.yaml
│   │   │       ├── docs__evidence__AS-CORE-003-v2-candidate-005.yaml
│   │   │       ├── docs__evidence__AS-CORE-003-v2-candidate-006-review-addendum.yaml
│   │   │       ├── docs__evidence__AS-CORE-003-v2-candidate-006.yaml
│   │   │       ├── docs__evidence__AS-CORE-003-v2-remediation-receipt.yaml
│   │   │       ├── docs__evidence__AS-ID-001-final-certification-remediation-receipt.yaml
│   │   │       ├── docs__evidence__AS-ID-001-governor-remediation-receipt.yaml
│   │   │       ├── docs__evidence__AS-ID-001-receipt.yaml
│   │   │       ├── docs__evidence__AS-ID-001-retired-slot-resolution-wiring-receipt.yaml
│   │   │       ├── docs__evidence__AS-RET-001-post-merge-receipt.yaml
│   │   │       ├── docs__evidence__AS-RET-001-receipt.yaml
│   │   │       ├── docs__evidence__AS-SEC-001-certification-carry-forward.yaml
│   │   │       ├── docs__evidence__AS-SEC-001-post-merge-validation.yaml
│   │   │       └── docs__plan.md
│   │   ├── as-ext-001a
│   │   │   ├── PROVENANCE.md
│   │   │   ├── real
│   │   │   │   ├── evidence-flat-as-core-002-post-merge-receipt.yaml
│   │   │   │   ├── f01-verify-collision-excerpt.md
│   │   │   │   ├── f01-verify-structured-document.md
│   │   │   │   ├── f02-backlog-historical-4e2b436.md
│   │   │   │   ├── f03-evidence-nested-as-core-003-receipt.yaml
│   │   │   │   ├── f04-adr-family-a-adr-003.md
│   │   │   │   ├── f05-adr-family-b-adr-006.md
│   │   │   │   ├── f06-worklog-entry-excerpt.md
│   │   │   │   ├── f07-implementation-roadmap-repeated-headings.md
│   │   │   │   ├── f07-master-roadmap-repeated-headings.md
│   │   │   │   └── f08-plan-foreign-h1-excerpt.md
│   │   │   └── synthetic
│   │   │       ├── alias-amplification.yaml
│   │   │       ├── duplicate-yaml-keys.yaml
│   │   │       ├── malformed-yaml.yaml
│   │   │       ├── many-unknown-fields.yaml
│   │   │       ├── one-to-many-migration.md
│   │   │       ├── partial-candidate.md
│   │   │       ├── promotion-failure.md
│   │   │       ├── reordered-mapping-a.yaml
│   │   │       ├── reordered-mapping-b.yaml
│   │   │       ├── sequence-provisional-index.yaml
│   │   │       ├── sequence-stable-key.yaml
│   │   │       ├── unicode-equivalent-keys-nfd.yaml
│   │   │       ├── unicode-equivalent-keys.yaml
│   │   │       ├── unknown-receipt-profile.yaml
│   │   │       └── unsupported-source.xyz
│   │   ├── atlas-2.0
│   │   │   ├── openai-importer
│   │   │   │   └── sample-chat-export.md
│   │   │   └── twin-projection
│   │   │       └── sample-projection.json
│   │   ├── atlas3
│   │   │   └── llm-memory
│   │   │       └── postgres-cross-llm.json
│   │   ├── demo
│   │   │   ├── estate
│   │   │   │   ├── harbor-api
│   │   │   │   │   ├── ARCHITECTURE.md
│   │   │   │   │   ├── DEPENDENCIES.md
│   │   │   │   │   ├── docs
│   │   │   │   │   │   ├── ADR-001-database.md
│   │   │   │   │   │   ├── ADR-002-database-superseded.md
│   │   │   │   │   │   ├── audit-logging.md
│   │   │   │   │   │   └── datastore-architecture.md
│   │   │   │   │   ├── README.md
│   │   │   │   │   ├── REQUIREMENTS.md
│   │   │   │   │   └── src
│   │   │   │   │       ├── datastore-runtime.md
│   │   │   │   │       └── RUNTIME.md
│   │   │   │   ├── harbor-ops
│   │   │   │   │   ├── docs
│   │   │   │   │   │   └── NOTES.md
│   │   │   │   │   ├── INVENTORY.md
│   │   │   │   │   └── README.md
│   │   │   │   └── harbor-portal
│   │   │   │       ├── DEPENDENCIES.md
│   │   │   │       ├── docs
│   │   │   │       │   └── ARCHITECTURE.md
│   │   │   │       └── README.md
│   │   │   └── README.md
│   │   ├── expected
│   │   │   ├── manifests
│   │   │   │   └── pilots-manifest.json
│   │   │   └── portfolio
│   │   │       ├── capability-report.json
│   │   │       ├── dependency-report.json
│   │   │       ├── documentation-coverage.json
│   │   │       ├── maturity-matrix.json
│   │   │       ├── overview.json
│   │   │       ├── portfolio-overview.md
│   │   │       └── stale-knowledge.json
│   │   ├── graphify-present
│   │   │   └── graphify-out
│   │   │       ├── edges.jsonl
│   │   │       ├── graph.json
│   │   │       ├── metadata.yaml
│   │   │       └── nodes.jsonl
│   │   ├── integrated-atlas-project
│   │   │   ├── ARCHITECTURE.md
│   │   │   └── README.md
│   │   ├── k007-canary-secrets
│   │   │   ├── CONFIG-NOTES.md
│   │   │   └── README.md
│   │   ├── live_integration
│   │   │   ├── LCI-002-TEST-OWNED.contract.json
│   │   │   └── LCI-002-TEST-OWNED.source.md
│   │   ├── okf
│   │   │   └── project-one-concepts.md
│   │   ├── pilots
│   │   │   ├── black-agency-os
│   │   │   │   └── README.md
│   │   │   ├── dark-factory
│   │   │   │   ├── DEPENDENCIES.md
│   │   │   │   ├── ROADMAP-A.md
│   │   │   │   └── ROADMAP-B.md
│   │   │   └── nebula
│   │   │       ├── ARCHITECTURE.md
│   │   │       ├── DEPENDENCIES.md
│   │   │       ├── README.md
│   │   │       ├── SECURITY.md
│   │   │       └── VALIDATION.md
│   │   ├── roadmap
│   │   │   └── v1
│   │   │       └── harbor-slice
│   │   │           ├── generated
│   │   │           │   └── ops
│   │   │           │       └── receipts
│   │   │           │           ├── connect.json
│   │   │           │           └── identity.json
│   │   │           └── projects
│   │   │               └── harbor-slice
│   │   │                   ├── project.md
│   │   │                   └── roadmap.md
│   │   ├── task-context-continuity
│   │   │   ├── contract.json
│   │   │   ├── evidence
│   │   │   │   └── bundle.json
│   │   │   └── repo
│   │   │       ├── docs
│   │   │       │   ├── architecture.md
│   │   │       │   ├── conflict-a.md
│   │   │       │   ├── conflict-b.md
│   │   │       │   ├── injection-bait.md
│   │   │       │   └── unrelated-history.md
│   │   │       └── src
│   │   │           └── api.py
│   │   └── work_readiness
│   │       └── positive_and_negative.v1.json
│   ├── __init__.py
│   ├── integration
│   │   ├── d040_cross_surface.py
│   │   ├── test_agent_event_ingestion.py
│   │   ├── test_as_2_2_eval_broker_adversarial.py
│   │   ├── test_as_backup_001_recovery_journey.py
│   │   ├── test_as_core_model_001a_pilot_matrix.py
│   │   ├── test_as_core_model_001b_capability_matrix.py
│   │   ├── test_as_core_model_001c_acceptance_matrix.py
│   │   ├── test_as_demo_2_2_golden_fixture.py
│   │   ├── test_as_demo_2_2_recovery_id_bootstrap.py
│   │   ├── test_as_e2e_001_fixture_matrix.py
│   │   ├── test_as_graph_003_store_graph_cli.py
│   │   ├── test_as_ingest_manifest_001_pipeline.py
│   │   ├── test_as_mvp_001_portfolio.py
│   │   ├── test_as_mvp_001_release_closure.py
│   │   ├── test_as_obsidian_capture_001_journey.py
│   │   ├── test_as_opt_gate_broker.py
│   │   ├── test_as_ret_001_lexical_indexes.py
│   │   ├── test_as_sec_001_quarantine_boundary.py
│   │   ├── test_as_xproj_001_register_cli.py
│   │   ├── test_as_xproj_002_register_edge_cli.py
│   │   ├── test_as_xproj_003_detect_cli.py
│   │   ├── test_cli.py
│   │   ├── test_codex_sec_001_002_provenance.py
│   │   ├── test_concurrency.py
│   │   ├── test_core_claims_authority_conflicts.py
│   │   ├── test_core_semantic_lifecycle.py
│   │   ├── test_core_vertical_slice.py
│   │   ├── test_cross_surface_consistency_d040.py
│   │   ├── test_cursor_hook_contract.py
│   │   ├── test_dogfood_001_source_marker_identity_write.py
│   │   ├── test_evidence_compiler_pipeline.py
│   │   ├── test_historical_completeness.py
│   │   ├── test_human_truth_loop_v2_d040.py
│   │   ├── test_ingestion_security.py
│   │   ├── test_int_013_bounded_multi_project_pilot.py
│   │   ├── test_int_013_origination_truth.py
│   │   ├── test_migration.py
│   │   ├── test_okf_public_conformance.py
│   │   ├── test_orchestration_autonomy_pilot.py
│   │   └── test_orchestration_result_binding_windows.py
│   ├── __pycache__
│   │   └── __init__.cpython-312.pyc
│   ├── security
│   │   ├── git_history_scan.py
│   │   ├── __init__.py
│   │   ├── registry.py
│   │   ├── test_git_history_scan_differential.py
│   │   └── test_security_regression_seed.py
│   └── unit
│       ├── _as_accept_002_helpers.py
│       ├── _atlas_2_2_maturity.py
│       ├── opt_gate_helpers.py
│       ├── orchestration
│       │   ├── __pycache__
│       │   │   └── test_work_readiness.cpython-312-pytest-9.1.1.pyc
│       │   └── test_work_readiness.py
│       ├── _program_fixture_worker.py
│       ├── __pycache__
│       │   ├── test_live_component_integration_002.cpython-312-pytest-9.1.1.pyc
│       │   ├── test_task_context_continuity_001.cpython-312-pytest-9.1.1.pyc
│       │   ├── test_taskcontract_authority_and_evidence.cpython-312-pytest-9.1.1.pyc
│       │   └── test_taskcontract_preparation.cpython-312-pytest-9.1.1.pyc
│       ├── test_as_2_0_agentos_001.py
│       ├── test_as_2_0_api_001.py
│       ├── test_as_2_0_api_chatgpt_estate_001.py
│       ├── test_as_2_0_change_001.py
│       ├── test_as_2_0_collab_scale_sec_001.py
│       ├── test_as_2_0_ctx_001.py
│       ├── test_as_2_0_ctx_agent_002.py
│       ├── test_as_2_0_decision_001.py
│       ├── test_as_2_0_delta_001.py
│       ├── test_as_2_0_dep_001.py
│       ├── test_as_2_0_explain_001.py
│       ├── test_as_2_0_fed_001.py
│       ├── test_as_2_0_final_cert_sync_twin_001.py
│       ├── test_as_2_0_gap_002.py
│       ├── test_as_2_0_handoff_001.py
│       ├── test_as_2_0_inbox_sched_sec_001.py
│       ├── test_as_2_0_intel_001.py
│       ├── test_as_2_0_intel_002.py
│       ├── test_as_2_0_intel_003b.py
│       ├── test_as_2_0_intel_003c.py
│       ├── test_as_2_0_intel_003.py
│       ├── test_as_2_0_intel_004.py
│       ├── test_as_2_0_intel_005.py
│       ├── test_as_2_0_intel_obs_001.py
│       ├── test_as_2_0_intel_perf_001.py
│       ├── test_as_2_0_intel_perf_002.py
│       ├── test_as_2_0_intel_perf_003.py
│       ├── test_as_2_0_intel_wave1_perf.py
│       ├── test_as_2_0_kci_ctx_001.py
│       ├── test_as_2_0_kf2_fed_002.py
│       ├── test_as_2_0_mcp_001.py
│       ├── test_as_2_0_next_001.py
│       ├── test_as_2_0_oai_import_001.py
│       ├── test_as_2_0_oai_reality_kci_001.py
│       ├── test_as_2_0_obs_auto_001.py
│       ├── test_as_2_0_obs_ux_001.py
│       ├── test_as_2_0_portfolio_001.py
│       ├── test_as_2_0_portfolio_002.py
│       ├── test_as_2_0_portfolio_003.py
│       ├── test_as_2_0_prov_001.py
│       ├── test_as_2_0_reality_gap_001.py
│       ├── test_as_2_0_ret_hybrid_001.py
│       ├── test_as_2_0_risk_001.py
│       ├── test_as_2_0_state_001.py
│       ├── test_as_2_0_tempint_001.py
│       ├── test_as_2_0_temporal_001.py
│       ├── test_as_2_0_twin_agent_001.py
│       ├── test_as_2_0_twin_fixture_001.py
│       ├── test_as_2_0_ux_001_entry_gate.py
│       ├── test_as_2_0_ux_002.py
│       ├── test_as_2_0_wave1_compat_kf.py
│       ├── test_as_2_0_web_001.py
│       ├── test_as_2_0_web_nav.py
│       ├── test_as_2_0_web_surfaces_001.py
│       ├── test_as_2_1_adv_host_cors_001.py
│       ├── test_as_2_1_adv_live_001.py
│       ├── test_as_2_1_api_adv_deepen_001.py
│       ├── test_as_2_1_api_bridge_resource_hardening_001.py
│       ├── test_as_2_1_ask_atlas_live_web.py
│       ├── test_as_2_1_autonomy_l3_001.py
│       ├── test_as_2_1_first_wave_001.py
│       ├── test_as_2_1_l3_job_matrix_adv.py
│       ├── test_as_2_1_mcp_adv_001.py
│       ├── test_as_2_1_mcp_brief_001.py
│       ├── test_as_2_1_obs_perf_001.py
│       ├── test_as_2_1_ops_receipt_adapter.py
│       ├── test_as_2_1_pilot_oai_poc_001.py
│       ├── test_as_2_1_track_b_deepen_001.py
│       ├── test_as_2_1_track_b_deepen_002.py
│       ├── test_as_2_1_track_b_deepen_003.py
│       ├── test_as_2_1_track_b_deepen_004.py
│       ├── test_as_2_1_track_b_deepen_005.py
│       ├── test_as_2_1_track_b_deepen_007.py
│       ├── test_as_2_1_wave2_001.py
│       ├── test_as_2_1_web_mission_workspace_ux.py
│       ├── test_as_2_2_adv_pool_prep_001.py
│       ├── test_as_2_2_ask2_answer_lens_001.py
│       ├── test_as_2_2_ask2_deepen_prep_001.py
│       ├── test_as_2_2_chatgpt_live_deepen_prep_001.py
│       ├── test_as_2_2_chatgpt_live_prep_001.py
│       ├── test_as_2_2_compat_pin_deepen_prep_001.py
│       ├── test_as_2_2_compat_pin_prep_001.py
│       ├── test_as_2_2_conflict_ux_deepen_prep_001.py
│       ├── test_as_2_2_conflict_ux_prep_001.py
│       ├── test_as_2_2_ctx_deepen_prep_001.py
│       ├── test_as_2_2_doc_charter_deepen_prep_001.py
│       ├── test_as_2_2_doc_charter_matrix_sync_001.py
│       ├── test_as_2_2_doc_charter_prep_001.py
│       ├── test_as_2_2_dod_deepen_prep_001.py
│       ├── test_as_2_2_estate_ops_deepen_prep_001.py
│       ├── test_as_2_2_estate_ops_prep_001.py
│       ├── test_as_2_2_eval_001.py
│       ├── test_as_2_2_eval_broker_secret.py
│       ├── test_as_2_2_eval_holdout_isolation_regression.py
│       ├── test_as_2_2_intel_slice_deepen_prep_001.py
│       ├── test_as_2_2_intel_slice_prep_001.py
│       ├── test_as_2_2_kci_engine_deepen_prep_001.py
│       ├── test_as_2_2_kdiff_001.py
│       ├── test_as_2_2_kdiff_live_project_web.py
│       ├── test_as_2_2_kf2_fabric_deepen_prep_001.py
│       ├── test_as_2_2_kf2_fabric_prep_001.py
│       ├── test_as_2_2_mem_gov_deepen_prep_001.py
│       ├── test_as_2_2_mem_gov_prep_001.py
│       ├── test_as_2_2_prep_fixture_rollup_001.py
│       ├── test_as_2_2_reality_gap_deepen_prep_001.py
│       ├── test_as_2_2_reality_gap_prep_001.py
│       ├── test_as_2_2_reality_live_deepen_prep_001.py
│       ├── test_as_2_2_reality_live_prep_001.py
│       ├── test_as_2_2_research_deepen_prep_001.py
│       ├── test_as_2_2_research_prep_001.py
│       ├── test_as_2_2_ret_hybrid_deepen_prep_001.py
│       ├── test_as_2_2_ret_semidx_prep_001.py
│       ├── test_as_2_2_roadmap_crosswalk_deepen_prep_001.py
│       ├── test_as_2_2_roadmap_crosswalk_sync_001.py
│       ├── test_as_2_2_runtime_001.py
│       ├── test_as_2_2_runtime_scope_001.py
│       ├── test_as_2_2_temporal_ux_deepen_prep_001.py
│       ├── test_as_2_2_temporal_ux_prep_001.py
│       ├── test_as_2_2_time_machine_deepen_prep_001.py
│       ├── test_as_2_2_xproj_deepen_prep_001.py
│       ├── test_as_2_2_xproj_prep_001.py
│       ├── test_as_accept_001_authority.py
│       ├── test_as_accept_001_compiler.py
│       ├── test_as_accept_001_query.py
│       ├── test_as_accept_001_temporal.py
│       ├── test_as_accept_002_authority_temporal.py
│       ├── test_as_accept_002_graph.py
│       ├── test_as_accept_002_health.py
│       ├── test_as_accept_002_mixed.py
│       ├── test_as_accept_002_query.py
│       ├── test_as_adv_clean_clone_rehearsal_docs.py
│       ├── test_as_adv_release_001_fixture_cert.py
│       ├── test_as_adv_release_002_clean_clone.py
│       ├── test_as_adv_release_003_perf_determinism.py
│       ├── test_as_adv_release_004_migration_recovery.py
│       ├── test_as_adv_sec_fixture_matrices_docs.py
│       ├── test_as_backup_001_verified_snapshot.py
│       ├── test_as_coder_alpha_039_architecture.py
│       ├── test_as_coder_alpha_040_architecture.py
│       ├── test_as_coder_alpha_040_attention_source.py
│       ├── test_as_coder_alpha_042_conversation_capture.py
│       ├── test_as_coder_alpha_043_pass_blockers.py
│       ├── test_as_coder_alpha_044_d041_high.py
│       ├── test_as_coder_alpha_049_estate_discovery.py
│       ├── test_as_coder_alpha_050_d050_residuals.py
│       ├── test_as_coder_alpha_057_copied_uuid.py
│       ├── test_as_coder_alpha_architecture_read_001.py
│       ├── test_as_coder_alpha_architecture_surface_001.py
│       ├── test_as_coder_alpha_bitemporal_read_001.py
│       ├── test_as_coder_alpha_capture_001.py
│       ├── test_as_coder_alpha_changed_001.py
│       ├── test_as_coder_alpha_changed_read_001.py
│       ├── test_as_coder_alpha_connect_001.py
│       ├── test_as_coder_alpha_connect_perf_001.py
│       ├── test_as_coder_alpha_context_freshness_adv_001.py
│       ├── test_as_coder_alpha_context_handoff_001.py
│       ├── test_as_coder_alpha_context_web.py
│       ├── test_as_coder_alpha_decisions_read_001.py
│       ├── test_as_coder_alpha_decisions_unknown_brief.py
│       ├── test_as_coder_alpha_demo_readiness_001.py
│       ├── test_as_coder_alpha_dogfood_compiler_coverage_001.py
│       ├── test_as_coder_alpha_fresh_agent_challenge_v2.py
│       ├── test_as_coder_alpha_honesty_tail_382.py
│       ├── test_as_coder_alpha_honesty_tail_384.py
│       ├── test_as_coder_alpha_human_loop_001.py
│       ├── test_as_coder_alpha_inbox_list_001.py
│       ├── test_as_coder_alpha_incremental_connect_001.py
│       ├── test_as_coder_alpha_index_status_001.py
│       ├── test_as_coder_alpha_inventory_drift_001.py
│       ├── test_as_coder_alpha_isolation_adv_001.py
│       ├── test_as_coder_alpha_lens_drift_convergence_001.py
│       ├── test_as_coder_alpha_next_001.py
│       ├── test_as_coder_alpha_next_read_001.py
│       ├── test_as_coder_alpha_obsidian_001.py
│       ├── test_as_coder_alpha_obsidian_r1_001.py
│       ├── test_as_coder_alpha_overview_001.py
│       ├── test_as_coder_alpha_overview_read_001.py
│       ├── test_as_coder_alpha_portfolio_read_001.py
│       ├── test_as_coder_alpha_roadmap_read_001.py
│       ├── test_as_coder_alpha_source_drift_scope_001.py
│       ├── test_as_coder_alpha_source_health_api_001.py
│       ├── test_as_coder_alpha_state_001.py
│       ├── test_as_coder_alpha_state_read_001.py
│       ├── test_as_coder_alpha_unknown_read_001.py
│       ├── test_as_coder_alpha_web_001.py
│       ├── test_as_coder_alpha_web_live_hook_honesty.py
│       ├── test_as_coder_alpha_workflow_metrics_001.py
│       ├── test_as_core_004_claim_integration.py
│       ├── test_as_core_004_real_fixtures.py
│       ├── test_as_core_005_eight_groups.py
│       ├── test_as_core_005_temporal_safety.py
│       ├── test_as_core_006_authority.py
│       ├── test_as_core_007_knowledge_query.py
│       ├── test_as_core_008_multifield_query.py
│       ├── test_as_core2_008_adversarial.py
│       ├── test_as_core2_008_conflict_projections.py
│       ├── test_as_core2_008_review_queue.py
│       ├── test_as_core2_009_promote_recovery.py
│       ├── test_as_core2_010_lifecycle_cert.py
│       ├── test_as_core_model_001a_maturity_rules.py
│       ├── test_as_core_model_001b_capability_rules.py
│       ├── test_as_core_model_001c_composition_rules.py
│       ├── test_as_core_ops_001_promote_accounting.py
│       ├── test_as_d_006_parser_registry.py
│       ├── test_as_d049_063_truth_hardening.py
│       ├── test_as_d049_064_high_remediation.py
│       ├── test_as_d049_067_high_remediation.py
│       ├── test_as_d049_078_authorized_volume_root.py
│       ├── test_as_d049_080_candidate_selection.py
│       ├── test_as_d049_084_fair_selection.py
│       ├── test_as_d049_087_path_index_performance.py
│       ├── test_as_demo_2_1_001_docs.py
│       ├── test_as_demo_2_1_browser_e2e_001.py
│       ├── test_as_demo_2_2_recovery_id_001.py
│       ├── test_as_e_006_classification_method.py
│       ├── test_as_explain_001_band_b_sidecars.py
│       ├── test_as_explain_001_receipts.py
│       ├── test_as_gh_001_governance.py
│       ├── test_as_graph_001_artifact_acceptance.py
│       ├── test_as_graph_002_adversarial.py
│       ├── test_as_graph_002_entity_resolution.py
│       ├── test_as_graph_003_adversarial.py
│       ├── test_as_graph_003_relationship_store.py
│       ├── test_as_graph_004_adversarial.py
│       ├── test_as_graph_004_quarantine_health.py
│       ├── test_as_graph_004_quarantine_store.py
│       ├── test_as_graph_005_adversarial.py
│       ├── test_as_graph_005_f4_canonical_semantics.py
│       ├── test_as_graph_005_projections.py
│       ├── test_as_h_010_severity_exits.py
│       ├── test_as_incr_compile_001_adversarial.py
│       ├── test_as_incr_compile_001_cache.py
│       ├── test_as_ingest_manifest_001.py
│       ├── test_as_int_009_retention.py
│       ├── test_as_int_010_tombstones.py
│       ├── test_as_int_011_receipt_revocation.py
│       ├── test_as_int_012_schema_compat.py
│       ├── test_as_j_005_adversarial.py
│       ├── test_as_j_005_impact_graph.py
│       ├── test_as_lane_y_001_docs_reconciliation.py
│       ├── test_as_mvp_001_freshness_truth.py
│       ├── test_as_mvp_001_relationship_edges.py
│       ├── test_as_obs_001_health_snapshot.py
│       ├── test_as_obs_002_adversarial.py
│       ├── test_as_obs_002_ops_events.py
│       ├── test_as_obs_003_adversarial.py
│       ├── test_as_obs_003_ops_report.py
│       ├── test_as_obsidian_capture_001_f10_refusal_parity.py
│       ├── test_as_obsidian_capture_001_f11_mkdir_boundary.py
│       ├── test_as_obsidian_capture_001_f12_instruments_execute.py
│       ├── test_as_obsidian_capture_001_f3.py
│       ├── test_as_obsidian_capture_001_f5_newline_fidelity.py
│       ├── test_as_obsidian_capture_001_f6_error_boundary.py
│       ├── test_as_obsidian_capture_001_f7_bom_ownership.py
│       ├── test_as_obsidian_capture_001_f9_diagnostic_uniformity.py
│       ├── test_as_obsidian_capture_001.py
│       ├── test_as_opt_gate_001.py
│       ├── test_as_opt_gate_anti_gaming.py
│       ├── test_as_opt_gate_fail_closed.py
│       ├── test_as_opt_gate_honesty_seal.py
│       ├── test_as_opt_gate_security.py
│       ├── test_as_orch_autonomous_mission_reconciler_001.py
│       ├── test_as_orch_closed_loop_port_001.py
│       ├── test_as_orch_continuation_broker_001.py
│       ├── test_as_orch_continuation_broker_hooks.py
│       ├── test_as_orch_cursor_sdk_runtime_083.py
│       ├── test_as_orch_d092_runtime_wiring.py
│       ├── test_as_orch_d095_audit_provenance.py
│       ├── test_as_orch_d098_lease_execution.py
│       ├── test_as_orch_d104_runtime_remediation.py
│       ├── test_as_orch_d106_d105_runtime_remediation.py
│       ├── test_as_orch_d106_sdk_backend_runtime.py
│       ├── test_as_orch_d112_missing_agent_cloud_fallback.py
│       ├── test_as_orch_d112_sdk_backend_reattack.py
│       ├── test_as_orch_d116_cloud_remote_attribution.py
│       ├── test_as_orch_d119_cloud_recovery_compat.py
│       ├── test_as_orch_durable_lease_projection_001.py
│       ├── test_as_orch_nonblocking_scheduler_liveness_001.py
│       ├── test_as_orch_sdk_durable_runtime_082.py
│       ├── test_as_orch_self_wake_resident_driver_001.py
│       ├── test_as_orch_six_p1_security_088.py
│       ├── test_as_orch_speculative_certification_001.py
│       ├── test_as_pilot_fixture_only_waiver.py
│       ├── test_as_prod_install_001.py
│       ├── test_as_prod_onboard_001.py
│       ├── test_as_project_roadmap_001.py
│       ├── test_as_project_roadmap_nav.py
│       ├── test_as_project_roadmap_web.py
│       ├── test_as_query_001_list_kinds.py
│       ├── test_as_query_diag_001.py
│       ├── test_as_query_multi_001_adversarial.py
│       ├── test_as_query_multi_001_plans.py
│       ├── test_as_rel_001_tip_pin.py
│       ├── test_as_ret_001_vault_retriever.py
│       ├── test_as_ret_hybrid_p2_rrf.py
│       ├── test_as_sec_009_api_auth.py
│       ├── test_as_sec_cont_001_fixture_gates.py
│       ├── test_as_sec_cont_002_fixture_deepen.py
│       ├── test_as_strategy_gap_docs_001.py
│       ├── test_as_sync_001_scaffold_dry_run.py
│       ├── test_as_sync_002_scaffold_plan.py
│       ├── test_as_sync_003_queue_scaffold.py
│       ├── test_as_sync_004_receipts.py
│       ├── test_as_val_001_freshness_orphan.py
│       ├── test_as_web_001_web_api.py
│       ├── test_as_web_accept_001_checklist.py
│       ├── test_as_web_accept_002_closeout.py
│       ├── test_as_web_accept_003_signoff_pack.py
│       ├── test_as_web_accept_005_governor_evidence.py
│       ├── test_as_web_mission_control_001.py
│       ├── test_as_web_ops_health_001.py
│       ├── test_as_web_workspace_001.py
│       ├── test_as_xproj_001_global_entities.py
│       ├── test_as_xproj_002_cross_project_edges.py
│       ├── test_as_xproj_003_duplicate_detection.py
│       ├── test_as_xproj_004_conflict_indexes.py
│       ├── test_atlas3_adv_020_control_001.py
│       ├── test_atlas3_adv_bind_052.py
│       ├── test_atlas3_autonomy_gate_053.py
│       ├── test_atlas3_capabilities_004.py
│       ├── test_atlas3_causal_060.py
│       ├── test_atlas3_chatgpt_036.py
│       ├── test_atlas3_chronicle_horizon_001.py
│       ├── test_atlas3_claim_nodes_020.py
│       ├── test_atlas3_claude_037.py
│       ├── test_atlas3_cli_001.py
│       ├── test_atlas3_codex_058.py
│       ├── test_atlas3_compat_005.py
│       ├── test_atlas3_conflicts_042.py
│       ├── test_atlas3_conflict_unknown_022.py
│       ├── test_atlas3_context_compiler_054.py
│       ├── test_atlas3_context_serve_055.py
│       ├── test_atlas3_cursor_057.py
│       ├── test_atlas3_decided_062.py
│       ├── test_atlas3_decision_explorer_094.py
│       ├── test_atlas3_dedup_041.py
│       ├── test_atlas3_demo_isolation_001.py
│       ├── test_atlas3_engineering_nodes_013.py
│       ├── test_atlas3_estate_nodes_012.py
│       ├── test_atlas3_events_001.py
│       ├── test_atlas3_extract_040.py
│       ├── test_atlas3_federation_reuse_112.py
│       ├── test_atlas3_file_graph_011.py
│       ├── test_atlas3_foundation_001.py
│       ├── test_atlas3_freshness_044.py
│       ├── test_atlas3_gemini_038.py
│       ├── test_atlas3_graph_authority_023.py
│       ├── test_atlas3_handoff_056.py
│       ├── test_atlas3_home_090.py
│       ├── test_atlas3_honesty_061.py
│       ├── test_atlas3_impact_080.py
│       ├── test_atlas3_impact_ux_095.py
│       ├── test_atlas3_incremental_046.py
│       ├── test_atlas3_intent_043.py
│       ├── test_atlas3_inventory_010.py
│       ├── test_atlas3_iv_bind_051.py
│       ├── test_atlas3_ledger_001.py
│       ├── test_atlas3_ledger_integrity_001.py
│       ├── test_atlas3_ledger_obs_101.py
│       ├── test_atlas3_lineage_045.py
│       ├── test_atlas3_memory_001.py
│       ├── test_atlas3_memory_project_isolation_001.py
│       ├── test_atlas3_memory_security_001.py
│       ├── test_atlas3_mission_096.py
│       ├── test_atlas3_multi_project_110.py
│       ├── test_atlas3_next_honesty_082.py
│       ├── test_atlas3_normalize_039.py
│       ├── test_atlas3_org_identity_111.py
│       ├── test_atlas3_privacy_047.py
│       ├── test_atlas3_program_docs_001.py
│       ├── test_atlas3_proof_001.py
│       ├── test_atlas3_provider_register_072.py
│       ├── test_atlas3_provider_sync_102.py
│       ├── test_atlas3_pulse_001.py
│       ├── test_atlas3_reconcile_049.py
│       ├── test_atlas3_rel_expand_021.py
│       ├── test_atlas3_search_048.py
│       ├── test_atlas3_security_catalog_006.py
│       ├── test_atlas3_stale_conflict_081.py
│       ├── test_atlas3_start_001.py
│       ├── test_atlas3_surface_070.py
│       ├── test_atlas3_timeline_091.py
│       ├── test_atlas3_time_machine_ux_093.py
│       ├── test_atlas3_transport_071.py
│       ├── test_atlas3_truth_graph_092.py
│       ├── test_atlas3_twin_002.py
│       ├── test_atlas3_twin_health_100.py
│       ├── test_atlas_contracts.py
│       ├── test_autonomy_return_gate_d146.py
│       ├── test_backlog_lifecycle_labels.py
│       ├── test_ci_observer_watch_disposition_d144.py
│       ├── test_claim_identity.py
│       ├── test_classification.py
│       ├── test_cli_surface_contract.py
│       ├── test_codex_sec_006_secret_import.py
│       ├── test_compilation.py
│       ├── test_config.py
│       ├── test_d146_remediation_adv.py
│       ├── test_d147_broker_reconcile_adv.py
│       ├── test_d147_continuation_enforcement.py
│       ├── test_d147r_exact_main_closure.py
│       ├── test_d148_authentic_estate.py
│       ├── test_d149_owner_gate_non_escalation.py
│       ├── test_d149_terminal_evidence_integrity.py
│       ├── test_d150_ask2_adversarial_grounding_matrix.py
│       ├── test_d154_stop_hook_return_gate_matrix.py
│       ├── test_d178_ask2_grounding_matrix.py
│       ├── test_d178_full_product_demo_honesty.py
│       ├── test_d178_kdiff_tz_aware.py
│       ├── test_d181_ask2_precision_matrix.py
│       ├── test_d183_demo_estate_valid_time.py
│       ├── test_diagnostics.py
│       ├── test_discovery_error_policy.py
│       ├── test_discovery_symlinked_event_scope.py
│       ├── test_domain_models.py
│       ├── test_duplicate_semantic_subject_withholding.py
│       ├── test_durable_host_sdk_ops_d164.py
│       ├── test_env_iso_remedi.py
│       ├── test_evaluator_case_classes.py
│       ├── test_evidence_compiler.py
│       ├── test_evidence_profiles.py
│       ├── test_heading_locator.py
│       ├── test_knowledge_compiler.py
│       ├── test_linux_filesystem_portability.py
│       ├── test_live_component_integration_002.py
│       ├── test_locator_migration.py
│       ├── test_logging.py
│       ├── test_merge_sequence_gate_d138.py
│       ├── test_okf_conformance.py
│       ├── test_orch001d_011_iv_probes.py
│       ├── test_orchestration_acceptance_contracts.py
│       ├── test_orchestration_agent_transport.py
│       ├── test_orchestration_autonomy_discovery_successor_topology.py
│       ├── test_orchestration_autonomy_lease_recovery.py
│       ├── test_orchestration_autonomy_loop.py
│       ├── test_orchestration_autonomy_pin_retarget.py
│       ├── test_orchestration_autonomy.py
│       ├── test_orchestration_autonomy_rehydration.py
│       ├── test_orchestration_autonomy_trust_catchup.py
│       ├── test_orchestration_autonomy_trust_checkpoint.py
│       ├── test_orchestration_autonomy_trust_merge_interlock.py
│       ├── test_orchestration_cursor_bridge.py
│       ├── test_orchestration_dispatcher.py
│       ├── test_orchestration_d_phase2a_2_governor_bridge.py
│       ├── test_orchestration_explicit_completion.py
│       ├── test_orchestration_local_dispatch_port.py
│       ├── test_orchestration_local_process_transport.py
│       ├── test_orchestration_origination_cli.py
│       ├── test_orchestration_origination.py
│       ├── test_orchestration_origination_rehydration.py
│       ├── test_orchestration_origination_sources.py
│       ├── test_orchestration_origination_supersession.py
│       ├── test_orchestration_policy.py
│       ├── test_orchestration_program_atlas_entrypoint.py
│       ├── test_orchestration_program_concurrency.py
│       ├── test_orchestration_program_control.py
│       ├── test_orchestration_program_enrollment.py
│       ├── test_orchestration_program_lifecycle.py
│       ├── test_orchestration_program_outcomes.py
│       ├── test_orchestration_program_runtimes.py
│       ├── test_orchestration_program_service.py
│       ├── test_orchestration_program_supervisor.py
│       ├── test_orchestration_program_template.py
│       ├── test_orchestration_result_binding.py
│       ├── test_orchestration_result_contract.py
│       ├── test_orchestration_router.py
│       ├── test_orchestration_transitions.py
│       ├── test_parser_output.py
│       ├── test_prepguard_maturity.py
│       ├── test_prod_doctor_001.py
│       ├── test_program_budget_exhaustion_classification.py
│       ├── test_quarantine_fuzz.py
│       ├── test_quarantine.py
│       ├── test_scaffold.py
│       ├── test_schema.py
│       ├── test_sec_004_018_path_containment.py
│       ├── test_sec_adv004_scan_b_highs.py
│       ├── test_sec_id_path_validation_001.py
│       ├── test_sec_scan_tip_highs.py
│       ├── test_semantic_migration.py
│       ├── test_semantic_models.py
│       ├── test_semantic_subject.py
│       ├── test_semantic_subject_schema_parity.py
│       ├── test_source_identity.py
│       ├── test_status_dimensions.py
│       ├── test_subject_derivation.py
│       ├── test_task_context_continuity_001.py
│       ├── test_taskcontract_authority_and_evidence.py
│       ├── test_taskcontract_preparation.py
│       ├── test_terminal_io_c002.py
│       ├── test_verify_profile.py
│       ├── test_windows_no_window_creationflags_d676.py
│       └── test_yaml_structured.py
├── VERSIONING.md
└── WORKLOG.md

352 directories, 3314 files
* Branch: 
* Push: **not** performed
