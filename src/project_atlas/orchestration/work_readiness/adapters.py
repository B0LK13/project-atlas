"""Optional upstream adapters. FIXTURE_ADAPTER != LIVE_INTEGRATION."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from project_atlas.orchestration.work_readiness.models import TriState


@dataclass(frozen=True)
class ContractView:
    """Minimal contract facts this package needs. Shape-compatible with AS-TASK-CONTRACT-001."""

    contract_id: str
    digest: str
    valid: bool
    objective: str
    expected_result: str
    mutation_paths: tuple[str, ...]
    required_adapter: str | None
    required_capabilities: tuple[str, ...]
    dependencies: tuple[str, ...]
    authorization_ref: str | None
    limits: dict[str, Any] = field(default_factory=dict)
    source_item_id: str | None = None
    priority: int | None = None


@dataclass(frozen=True)
class ClaimView:
    lease_id: str
    agent_id: str
    task_or_package_id: str
    mutation_paths: tuple[str, ...]
    status: str  # ACTIVE | RELEASED | UNKNOWN


@dataclass(frozen=True)
class EnrollmentView:
    agent_id: str
    adapter: str
    status: str  # ACTIVE | SUSPENDED | RETIRED | UNKNOWN
    capabilities: tuple[str, ...]


@dataclass(frozen=True)
class ResultView:
    task_id: str
    worker_exit_zero: bool | None
    acceptance_passed: bool | None
    review_complete: bool | None
    evidence_ref: str | None


@dataclass(frozen=True)
class DependencyNodeView:
    node_id: str
    status: TriState  # YES = satisfied terminal, NO = unsatisfied, UNKNOWN
    evidence: str | None = None


class ContractPort(Protocol):
    def load_for_task(self, task_id: str) -> ContractView | None: ...


class ClaimPort(Protocol):
    def active_claims(self) -> tuple[ClaimView, ...]: ...


class EnrollmentPort(Protocol):
    def agents(self) -> tuple[EnrollmentView, ...]: ...


class ResultPort(Protocol):
    def result_for(self, task_id: str) -> ResultView | None: ...


class DependencyPort(Protocol):
    def status_for(self, dependency_id: str) -> DependencyNodeView: ...


@dataclass(frozen=True)
class FixtureContractPort:
    """Versioned fixture stand-in for AS-TASK-CONTRACT-001."""

    contracts: dict[str, ContractView]
    fixture_id: str = "fixture.taskcontract.v1"

    def load_for_task(self, task_id: str) -> ContractView | None:
        return self.contracts.get(task_id)


@dataclass(frozen=True)
class FixtureClaimPort:
    claims: tuple[ClaimView, ...]
    fixture_id: str = "fixture.claims.v1"

    def active_claims(self) -> tuple[ClaimView, ...]:
        return tuple(c for c in self.claims if c.status == "ACTIVE")


@dataclass(frozen=True)
class FixtureEnrollmentPort:
    roster: tuple[EnrollmentView, ...]
    fixture_id: str = "fixture.enrollment.v1"

    def agents(self) -> tuple[EnrollmentView, ...]:
        return self.roster


@dataclass(frozen=True)
class FixtureResultPort:
    results: dict[str, ResultView]
    fixture_id: str = "fixture.qualityloop.v1"

    def result_for(self, task_id: str) -> ResultView | None:
        return self.results.get(task_id)


@dataclass(frozen=True)
class FixtureDependencyPort:
    nodes: dict[str, DependencyNodeView]
    fixture_id: str = "fixture.dependencies.v1"

    def status_for(self, dependency_id: str) -> DependencyNodeView:
        return self.nodes.get(
            dependency_id,
            DependencyNodeView(node_id=dependency_id, status=TriState.UNKNOWN, evidence=None),
        )


def load_fixture_bundle(path: Path) -> dict[str, Any]:
    """Load a versioned JSON fixture bundle. Never claims live integration."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("schema") != "work-readiness-fixture-bundle.v1":
        raise ValueError(f"unsupported fixture bundle: {path}")
    return payload


def ports_from_fixture_bundle(
    path: Path,
) -> tuple[
    FixtureContractPort,
    FixtureClaimPort,
    FixtureEnrollmentPort,
    FixtureResultPort,
    FixtureDependencyPort,
    tuple[str, ...],
]:
    raw = load_fixture_bundle(path)
    contracts = {
        row["task_id"]: ContractView(
            contract_id=row["contract_id"],
            digest=row["digest"],
            valid=bool(row["valid"]),
            objective=row["objective"],
            expected_result=row.get("expected_result", ""),
            mutation_paths=tuple(row.get("mutation_paths", ())),
            required_adapter=row.get("required_adapter"),
            required_capabilities=tuple(row.get("required_capabilities", ())),
            dependencies=tuple(row.get("dependencies", ())),
            authorization_ref=row.get("authorization_ref"),
            limits=dict(row.get("limits", {})),
            source_item_id=row.get("source_item_id"),
            priority=row.get("priority"),
        )
        for row in raw.get("contracts", [])
    }
    claims = tuple(
        ClaimView(
            lease_id=row["lease_id"],
            agent_id=row["agent_id"],
            task_or_package_id=row["task_or_package_id"],
            mutation_paths=tuple(row.get("mutation_paths", ())),
            status=row.get("status", "ACTIVE"),
        )
        for row in raw.get("claims", [])
    )
    roster = tuple(
        EnrollmentView(
            agent_id=row["agent_id"],
            adapter=row["adapter"],
            status=row.get("status", "ACTIVE"),
            capabilities=tuple(row.get("capabilities", ())),
        )
        for row in raw.get("enrollment", [])
    )
    results = {
        row["task_id"]: ResultView(
            task_id=row["task_id"],
            worker_exit_zero=row.get("worker_exit_zero"),
            acceptance_passed=row.get("acceptance_passed"),
            review_complete=row.get("review_complete"),
            evidence_ref=row.get("evidence_ref"),
        )
        for row in raw.get("results", [])
    }
    deps = {
        row["node_id"]: DependencyNodeView(
            node_id=row["node_id"],
            status=TriState(row["status"]),
            evidence=row.get("evidence"),
        )
        for row in raw.get("dependencies", [])
    }
    missing = tuple(raw.get("missing_integrations", ()))
    return (
        FixtureContractPort(contracts=contracts),
        FixtureClaimPort(claims=claims),
        FixtureEnrollmentPort(roster=roster),
        FixtureResultPort(results=results),
        FixtureDependencyPort(nodes=deps),
        missing,
    )
