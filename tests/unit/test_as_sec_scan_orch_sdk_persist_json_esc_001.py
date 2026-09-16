"""AS-SEC-SCAN-ORCH-SDK-RUNTIME-PERSIST-JSON-ESC-001 — decoded keys/values.

SDK incremental stores ``json.loads`` JSON ``\\u0041KI…`` escapes that
``scan_text`` misses on raw bytes, then rewrite plaintext
``AKIAAAAAAAAAAAAAAAAA`` as object keys or values (NFR-004 / AT-014).

Synthetic token only. Distinct from #823-#997 persist remedi.
"""

from __future__ import annotations

import json
from pathlib import Path

from project_atlas.orchestration.sdk.lease_registry import (
    leases_path,
    persist_durable_lease,
)
from project_atlas.orchestration.sdk.models import (
    PACKAGE_ID,
    AgentRecord,
    AgentRole,
    AgentRuntime,
    RunRecord,
    RunStatus,
)
from project_atlas.orchestration.sdk.mutation_attribution import (
    RunMutationBaseline,
    agent_remote_high_water_path,
    attribution_store_path,
    persist_agent_remote_high_water,
    persist_run_mutation_baseline,
)
from project_atlas.orchestration.sdk.registries import (
    AgentRegistryState,
    CloudAgentRegistry,
    RunRegistry,
    RunRegistryState,
    _seal_agents,
    _seal_runs,
)
from project_atlas.orchestration.sdk.resident_status import (
    load_status,
    persist_status,
    status_path,
)
from project_atlas.orchestration.sdk.result_plane import (
    ingest_pending_against_registry,
    ingested_index_path,
    result_plane_path,
)
from project_atlas.orchestration.sdk.scheduler import PARKED_NAME, DagToAgentScheduler
from project_atlas.orchestration.sdk.security_gates import (
    CANONICAL_BRANCH,
    CANONICAL_PR,
    GovernorLease,
)
from project_atlas.secrets import scan_text

TOKEN = "AKIAAAAAAAAAAAAAAAAA"
ESC = r"\u0041KIAAAAAAAAAAAAAAAAA"
PIN = "7e797468a2eca37c959920912b1fa264df4be638"


def _plant(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    raw = path.read_text(encoding="utf-8")
    assert ESC in raw
    assert TOKEN not in raw
    assert scan_text(raw) == []


def _agent(agent_id: str) -> AgentRecord:
    return AgentRecord(
        agent_id=agent_id,
        runtime=AgentRuntime.CLOUD,
        role=AgentRole.IMPLEMENTER,
        package_id=PACKAGE_ID,
        base_main=PIN,
        created_at="2026-01-01T00:00:00Z",
    )


def _run(run_id: str, *, agent_id: str = "bc-abc123") -> RunRecord:
    return RunRecord(
        run_id=run_id,
        agent_id=agent_id,
        package_id=PACKAGE_ID,
        role=AgentRole.IMPLEMENTER,
        prompt_digest="a" * 64,
        idempotency_key=f"idem-{run_id}-xxxxxxxx",
        status=RunStatus.CREATING,
        started_at="2026-01-01T00:00:00Z",
    )


def test_attribution_store_omits_json_escaped_key(tmp_path: Path) -> None:
    raw = '{"' + ESC + '": {"run_id": "old-run"}}'
    assert json.loads(raw)[TOKEN]["run_id"] == "old-run"
    store = attribution_store_path(tmp_path)
    _plant(store, raw + "\n")
    persist_run_mutation_baseline(
        tmp_path,
        RunMutationBaseline(
            run_id="run-new",
            agent_id="bc-abc123",
            runtime=AgentRuntime.CLOUD,
            base_main=PIN,
            dag_generation=1,
        ),
    )
    written = store.read_text(encoding="utf-8")
    loaded = json.loads(written)
    assert TOKEN not in written
    assert TOKEN not in loaded
    assert "run-new" in loaded
    assert scan_text(written) == []


def test_high_water_omits_json_escaped_key(tmp_path: Path) -> None:
    store = agent_remote_high_water_path(tmp_path)
    _plant(store, '{"' + ESC + '": "deadbeefcafebabe"}\n')
    persist_agent_remote_high_water(tmp_path, "bc-other", "1234567abcdef")
    written = store.read_text(encoding="utf-8")
    loaded = json.loads(written)
    assert TOKEN not in written
    assert TOKEN not in loaded
    assert loaded["bc-other"] == "1234567abcdef"
    assert scan_text(written) == []


def test_scheduler_parked_omits_json_escaped_key(tmp_path: Path) -> None:
    from project_atlas.orchestration.sdk.models import STATE_DIR_RELATIVE

    parked = tmp_path / STATE_DIR_RELATIVE / PARKED_NAME
    _plant(
        parked,
        '{"' + ESC + '": {"code": "X", "attempt": 1, "next_retry_at": 0, "parked_at": 0}}\n',
    )
    sched = DagToAgentScheduler.__new__(DagToAgentScheduler)
    sched.root = tmp_path
    sched._park_node("safe-node", code="AGENT_BUSY", attempt=1)
    written = parked.read_text(encoding="utf-8")
    loaded = json.loads(written)
    assert TOKEN not in written
    assert TOKEN not in loaded
    assert "safe-node" in loaded
    assert scan_text(written) == []


def test_lease_registry_omits_json_escaped_key(tmp_path: Path) -> None:
    planted = GovernorLease(
        lease_id="lease-ok",
        package_id=PACKAGE_ID,
        canonical_pr=CANONICAL_PR,
        branch=CANONICAL_BRANCH,
        role=AgentRole.IMPLEMENTER,
        dag_generation=1,
        candidate_head="b" * 40,
    )
    body = json.dumps(planted.model_dump(mode="json"), sort_keys=True)
    _plant(leases_path(tmp_path), "{\n  \"" + ESC + "\": " + body + "\n}\n")
    persist_durable_lease(
        tmp_path,
        GovernorLease(
            lease_id="lease-new",
            package_id=PACKAGE_ID,
            canonical_pr=CANONICAL_PR,
            branch=CANONICAL_BRANCH,
            role=AgentRole.IMPLEMENTER,
            dag_generation=1,
            candidate_head="c" * 40,
        ),
    )
    written = leases_path(tmp_path).read_text(encoding="utf-8")
    loaded = json.loads(written)
    assert TOKEN not in written
    assert TOKEN not in loaded
    assert "lease-new" in loaded
    assert scan_text(written) == []


def test_result_plane_ingested_omits_json_escaped_values(tmp_path: Path) -> None:
    ingested = ingested_index_path(tmp_path)
    _plant(
        ingested,
        '{"result_ids": ["' + ESC + '"], "records": [{"note": "' + ESC + '"}]}\n',
    )
    result_plane_path(tmp_path).parent.mkdir(parents=True, exist_ok=True)
    result_plane_path(tmp_path).write_text("", encoding="utf-8")
    ingest_pending_against_registry(tmp_path, runs=RunRegistry(tmp_path))
    written = ingested.read_text(encoding="utf-8")
    loaded = json.loads(written)
    assert TOKEN not in written
    assert TOKEN not in json.dumps(loaded)
    assert scan_text(written) == []


def test_agent_registry_omits_json_escaped_key(tmp_path: Path) -> None:
    planted = _agent("bc-abc123")
    sealed = _seal_agents(
        AgentRegistryState(agents={TOKEN: planted}, record_digest="0" * 64)
    )
    text = json.dumps(sealed.model_dump(mode="json"), sort_keys=True, indent=2)
    text = text.replace(f'"{TOKEN}"', f'"{ESC}"')
    path = CloudAgentRegistry(tmp_path).path
    _plant(path, text + "\n")
    CloudAgentRegistry(tmp_path).upsert(_agent("bc-otherxyz"))
    written = path.read_text(encoding="utf-8")
    loaded = json.loads(written)
    assert TOKEN not in written
    assert TOKEN not in loaded.get("agents", {})
    assert "bc-otherxyz" in loaded["agents"]
    assert scan_text(written) == []


def test_run_registry_omits_json_escaped_key(tmp_path: Path) -> None:
    planted = _run("run-old")
    sealed = _seal_runs(
        RunRegistryState(
            runs={TOKEN: planted},
            by_idempotency={},
            record_digest="0" * 64,
        )
    )
    text = json.dumps(sealed.model_dump(mode="json"), sort_keys=True, indent=2)
    text = text.replace(f'"{TOKEN}"', f'"{ESC}"')
    path = RunRegistry(tmp_path).path
    _plant(path, text + "\n")
    RunRegistry(tmp_path).upsert(_run("run-new2"))
    written = path.read_text(encoding="utf-8")
    loaded = json.loads(written)
    assert TOKEN not in written
    assert TOKEN not in loaded.get("runs", {})
    assert "run-new2" in loaded["runs"]
    assert scan_text(written) == []


def test_resident_status_omits_json_escaped_event(tmp_path: Path) -> None:
    path = status_path(tmp_path)
    status = persist_status(tmp_path, load_status(tmp_path))
    dumped = status.model_dump(mode="json")
    dumped["LAST_EVENT_CONSUMED"] = TOKEN
    text = json.dumps(dumped, sort_keys=True, indent=2).replace(f'"{TOKEN}"', f'"{ESC}"')
    _plant(path, text + "\n")
    persist_status(tmp_path, load_status(tmp_path))
    written = path.read_text(encoding="utf-8")
    loaded = json.loads(written)
    assert TOKEN not in written
    assert loaded.get("LAST_EVENT_CONSUMED") != TOKEN
    assert scan_text(written) == []
