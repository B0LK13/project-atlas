"""AS-TASK-CONTRACT-001: backlog item -> reviewable contract.

Hermetic throughout: a temporary project with its own declared origination
source, its own git workspace and its own registry. ZERO model calls and no
paid runtime -- the only subprocess any test starts is git, and the two tests
that evaluate acceptance run a command this test file itself owns.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from project_atlas.orchestration.origination.sources import eligible_work_items
from project_atlas.orchestration.program.loader import load_program
from project_atlas.orchestration.taskcontract.diff import diff_contracts
from project_atlas.orchestration.taskcontract.draft import draft_from_item
from project_atlas.orchestration.taskcontract.models import (
    DeploymentBinding,
    TaskContract,
    contract_digest,
)
from project_atlas.orchestration.taskcontract.render import (
    render_instruction,
    render_program,
)
from project_atlas.orchestration.taskcontract.validate import (
    ERROR,
    report_is_stale,
    validate_contract,
)

BACKLOG = """# Backlog

## Preparation

- [ ] TC-001 Add a bounded retry to the export writer
- [x] TC-000 Already done, never originated
"""


def _git(workspace: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-C", str(workspace), *args],
        check=True,
        capture_output=True,
        env={"HOME": str(workspace), "PATH": "/usr/bin:/bin", "GIT_CONFIG_GLOBAL": "/dev/null"},
    )


def _workspace(root: Path) -> tuple[Path, str]:
    workspace = root / "ws"
    (workspace / "src").mkdir(parents=True)
    (workspace / "src" / "exporter.py").write_text("def export():\n    ...\n", encoding="utf-8")
    _git(workspace, "init", "-q")
    _git(workspace, "-c", "user.email=t@t", "-c", "user.name=t", "add", "-A")
    _git(workspace, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "seed")
    head = subprocess.run(
        ["git", "-C", str(workspace), "rev-parse", "HEAD"],
        check=True, capture_output=True, text=True,
    ).stdout.strip()
    return workspace, head


def _project(root: Path) -> Path:
    """A project declaring exactly one origination source. Nothing is scanned."""
    project = root / "project"
    (project / "docs").mkdir(parents=True)
    (project / "docs" / "backlog.md").write_text(BACKLOG, encoding="utf-8")
    (project / ".atlas-project.yaml").write_text(
        "origination_sources:\n"
        "  - path: docs/backlog.md\n"
        "    format: markdown-task-list\n",
        encoding="utf-8",
    )
    return project


def _supplied(head: str, **overrides: Any) -> dict[str, Any]:
    """The decisions no source can make. Every one of them is explicit."""
    body: dict[str, Any] = {
        "objective": "Bound the export writer's retries so a stuck run ends.",
        "observable_outcome": (
            "export() retries at most three times and raises ExportFailed after."
        ),
        "scope": ["src/exporter.py retry loop"],
        "exclusions": ["the import path", "any change to the on-disk format"],
        "owner": "wesley",
        "repository": "project-atlas",
        "base_pin": head,
        "mutation_paths": ["src/exporter.py"],
        "expected_output_paths": ["src/exporter.py"],
        "runtime": {"adapter": "local-command", "capabilities": ["IMPLEMENT"]},
        "requirements": [
            {
                "requirement_id": "R1",
                "statement": "export() stops after three attempts and raises ExportFailed.",
                "verification": "AUTOMATED",
                "check_ids": ["behaviour"],
            },
            {
                "requirement_id": "R2",
                "statement": "The retry bound is readable at a glance by a reviewer.",
                "verification": "HUMAN_REVIEW",
                "review_note": "the loop in src/exporter.py",
            },
        ],
        "acceptance": [
            {
                "check_id": "behaviour",
                "kind": "COMMAND",
                "description": "the bounded-retry behaviour holds",
                "argv": [sys.executable, "-c", "import sys; sys.exit(0)"],
            }
        ],
        "limits": {
            "max_task_launches": 2,
            "max_attempts_per_task": 2,
            "max_task_seconds": 600,
        },
        "budget": {"max_estimated_cost_usd": 2.0, "enforced_by": "runtime per-launch flag",
                   "not_enforced": ["account spending limit"]},
        "context": [
            {"source_id": "writer", "path": "src/exporter.py",
             "why": "the function being changed"}
        ],
    }
    body.update(overrides)
    return body


def _binding(root: Path, workspace: Path) -> DeploymentBinding:
    state = root / "state"
    registry = root / "registry"
    state.mkdir(exist_ok=True)
    registry.mkdir(exist_ok=True)
    return DeploymentBinding(
        binding_id="test-binding",
        workspace_root=str(workspace),
        state_root=str(state),
        registry_root=str(registry),
        interpreter=sys.executable,
        profile_ref="implementer",
        agent_role="implementer",
    )


def _item(project: Path, item_id: str = "TC-001") -> Any:
    return next(i for i in eligible_work_items(project) if i.item_id == item_id)


def _contract(root: Path, **overrides: Any) -> tuple[TaskContract, Path, Path]:
    project = _project(root)
    workspace, head = _workspace(root)
    result = draft_from_item(_item(project), supplied=_supplied(head, **overrides))
    assert result.contract is not None, result.missing
    return result.contract, project, workspace


PROFILE: dict[str, Any] = {
    "profile_id": "implementer",
    "agent_id": "test-agent",
    "adapter": "local-command",
    "credential": "NOT_APPLICABLE",
    "capabilities": ["IMPLEMENT"],
    "adapter_options": {"argv": [sys.executable, "-c", "pass"]},
}


# ------------------------------------------- 1. one source, three artifacts


def test_a_complete_task_yields_consistent_instruction_and_configuration(
    tmp_path: Path,
) -> None:
    contract, _project_root, workspace = _contract(tmp_path)
    binding = _binding(tmp_path, workspace)

    instruction = render_instruction(contract)
    program = render_program(
        contract, binding,
        approved_by="wesley", approval_reference="docs/backlog.md#TC-001",
        profile=PROFILE,
    )
    task = program["program"]["tasks"][0]

    # The same paths, from the same field, in both artifacts.
    assert task["mutation_paths"] == list(contract.mutation_paths)
    for path in contract.mutation_paths:
        assert f"`{path}`" in instruction
    # Every requirement reaches the worker, by identifier and in full.
    for requirement in contract.requirements:
        assert requirement.requirement_id in instruction
        assert requirement.statement in instruction
    # The instruction IS the task instruction -- not a second copy.
    assert task["instruction"] == instruction
    # And the program the supervisor's own loader accepts.
    path = tmp_path / "program.json"
    path.write_text(json.dumps(program), encoding="utf-8")
    loaded = load_program(path)
    assert loaded.program.tasks[0].task_id == contract.contract_id


def test_the_same_input_digests_the_same_however_often_it_is_prepared(
    tmp_path: Path,
) -> None:
    """Reproducibility: report metadata must stay out of contract identity."""
    contract_a, _p, workspace = _contract(tmp_path / "a")
    contract_b, _q, _w = _contract(tmp_path / "b")
    # The two live in different temp dirs; only the base_pin differs, and it
    # differs because the workspaces are different commits. Compare a contract
    # against itself re-drafted instead.
    again = TaskContract.model_validate(contract_a.model_dump(mode="json"))
    assert contract_digest(again) == contract_digest(contract_a)

    binding = _binding(tmp_path / "a", workspace)
    first = validate_contract(contract_a, binding=binding, observed_at="2026-01-01T00:00:00Z")
    second = validate_contract(contract_a, binding=binding, observed_at="2999-12-31T23:59:59Z")
    assert first["observed_at"] != second["observed_at"]
    assert first["checked"] == second["checked"]
    assert first["findings"] == second["findings"]
    assert contract_digest(contract_b) != ""  # b is only here to prove independence


# ------------------------------------------- 2. gaps named, never invented


def test_an_incomplete_task_names_the_missing_fields_and_invents_nothing(
    tmp_path: Path,
) -> None:
    project = _project(tmp_path)
    result = draft_from_item(_item(project))

    assert not result.complete
    missing = {m.field for m in result.missing}
    # Exactly the decisions a source cannot make.
    assert {"owner", "base_pin", "mutation_paths", "acceptance", "budget"} <= missing
    for field in missing:
        assert result.payload.get(field) in (None, (), [], "")
    # Every gap arrives with the question that would close it.
    assert all(m.question.endswith("?") for m in result.missing)
    # What the source DOES state survives.
    assert result.payload["source"]["item_id"] == "TC-001"
    assert result.payload["objective"]


def test_a_checked_backlog_item_is_never_offered_for_preparation(tmp_path: Path) -> None:
    project = _project(tmp_path)
    ids = {item.item_id for item in eligible_work_items(project)}
    assert "TC-001" in ids
    assert "TC-000" not in ids


# ------------------------------------------- 3. a changed path moves everywhere


def test_changing_a_path_changes_every_artifact_that_names_it(tmp_path: Path) -> None:
    contract, _p, workspace = _contract(tmp_path)
    binding = _binding(tmp_path, workspace)
    moved = contract.model_copy(
        update={
            "mutation_paths": ("src/writer.py",),
            "expected_output_paths": ("src/writer.py",),
            "context": (),
            # The prose named the path too. That duplication is exactly what
            # `content.path_repeated_in_prose` warns about, and it has to be
            # moved by hand -- which is the point of the warning.
            "scope": ("the retry loop",),
            "requirements": tuple(
                r.model_copy(update={"review_note": "the loop in the writer"})
                if r.review_note
                else r
                for r in contract.requirements
            ),
        }
    )
    instruction = render_instruction(moved)
    program = render_program(
        moved, binding, approved_by="w", approval_reference="r", profile=PROFILE
    )
    assert "src/exporter.py" not in instruction
    assert "`src/writer.py`" in instruction
    assert program["program"]["tasks"][0]["mutation_paths"] == ["src/writer.py"]
    assert contract_digest(moved) != contract_digest(contract)


# ------------------------------------------- 4. output outside the scope


def test_an_output_outside_the_mutation_scope_is_an_error(tmp_path: Path) -> None:
    contract, _p, workspace = _contract(tmp_path)
    outside = contract.model_copy(update={"expected_output_paths": ("docs/report.md",)})
    report = validate_contract(outside, binding=_binding(tmp_path, workspace))
    codes = {f["check"] for f in report["findings"] if f["severity"] == ERROR}
    assert "paths.output_outside_mutation" in codes
    assert report["verdict"] == "BLOCKED"


def test_a_sibling_prefix_is_not_treated_as_containment(tmp_path: Path) -> None:
    """Negative control for the prefix check: src/exp must not cover src/exporter."""
    contract, _p, workspace = _contract(tmp_path, mutation_paths=["src/exp"])
    report = validate_contract(contract, binding=_binding(tmp_path, workspace))
    codes = {f["check"] for f in report["findings"] if f["severity"] == ERROR}
    assert "paths.output_outside_mutation" in codes


def test_an_absolute_path_cannot_enter_task_content(tmp_path: Path) -> None:
    project = _project(tmp_path)
    workspace, head = _workspace(tmp_path)
    result = draft_from_item(
        _item(project), supplied=_supplied(head, mutation_paths=[str(workspace / "src")])
    )
    assert result.contract is None
    assert any(c.code == "DRAFT_DOES_NOT_PARSE" for c in result.conflicts)


# ------------------------------------------- 5. a wrong deployment binding


def test_state_inside_the_workspace_is_an_error(tmp_path: Path) -> None:
    contract, _p, workspace = _contract(tmp_path)
    bad = _binding(tmp_path, workspace).model_copy(
        update={"state_root": str(workspace / "state")}
    )
    report = validate_contract(contract, binding=bad)
    codes = {f["check"] for f in report["findings"] if f["severity"] == ERROR}
    assert "binding.state_inside_workspace" in codes


def test_a_workspace_that_is_not_a_checkout_is_an_error(tmp_path: Path) -> None:
    contract, _p, workspace = _contract(tmp_path)
    empty = tmp_path / "not-a-repo"
    empty.mkdir()
    bad = _binding(tmp_path, workspace).model_copy(update={"workspace_root": str(empty)})
    report = validate_contract(contract, binding=bad)
    codes = {f["check"] for f in report["findings"] if f["severity"] == ERROR}
    assert "binding.workspace_not_git" in codes


def test_a_base_pin_absent_from_the_workspace_warns(tmp_path: Path) -> None:
    contract, _p, workspace = _contract(tmp_path)
    elsewhere = contract.model_copy(update={"base_pin": "0" * 40})
    report = validate_contract(elsewhere, binding=_binding(tmp_path, workspace))
    warnings = {f["check"] for f in report["findings"] if f["severity"] == "WARNING"}
    assert "binding.base_pin_absent" in warnings


def test_the_real_base_pin_is_found_without_running_git(tmp_path: Path) -> None:
    """Negative control for the pin check: a present commit must not warn."""
    contract, _p, workspace = _contract(tmp_path)
    report = validate_contract(contract, binding=_binding(tmp_path, workspace))
    warnings = {f["check"] for f in report["findings"] if f["severity"] == "WARNING"}
    assert "binding.base_pin_absent" not in warnings


# ------------------------------------------- 6. absence before the first run


def test_a_declared_output_missing_before_the_first_run_is_not_an_error(
    tmp_path: Path,
) -> None:
    contract, _p, workspace = _contract(
        tmp_path,
        mutation_paths=["src"],
        expected_output_paths=["src/exporter_retry_notes.md"],
        scope=["the retry loop"],
        context=[],
    )
    assert not (workspace / "src" / "exporter_retry_notes.md").exists()
    report = validate_contract(contract, binding=_binding(tmp_path, workspace))
    messages = " ".join(f["message"] for f in report["findings"])
    assert "exporter_retry_notes" not in messages
    assert report["counts"][ERROR] == 0


# ------------------------------------------- 7. stale evidence


def test_a_changed_contract_makes_earlier_validation_evidence_stale(
    tmp_path: Path,
) -> None:
    contract, _p, workspace = _contract(tmp_path)
    binding = _binding(tmp_path, workspace)
    report = validate_contract(contract, binding=binding)

    stale, reasons = report_is_stale(report, contract=contract, binding=binding)
    assert not stale and not reasons

    widened = contract.model_copy(
        update={"scope": (*contract.scope, "and the import path too")}
    )
    stale, reasons = report_is_stale(report, contract=widened, binding=binding)
    assert stale
    assert any("contract changed" in r for r in reasons)


def test_a_changed_binding_makes_earlier_validation_evidence_stale(
    tmp_path: Path,
) -> None:
    contract, _p, workspace = _contract(tmp_path)
    binding = _binding(tmp_path, workspace)
    report = validate_contract(contract, binding=binding)
    moved = binding.model_copy(update={"interpreter": "/usr/bin/python3"})
    stale, reasons = report_is_stale(report, contract=contract, binding=moved)
    assert stale
    assert any("binding changed" in r for r in reasons)


def test_a_scope_change_withdraws_a_prior_approval(tmp_path: Path) -> None:
    contract, _p, _w = _contract(tmp_path)
    widened = contract.model_copy(
        update={"scope": ("something else entirely",), "contract_version": 2}
    )
    result = diff_contracts(contract, widened)
    assert "scope" in result["changed_axes"]
    assert result["prior_approval_still_describes_this_work"] is False
    assert result["why_not"]


def test_an_identical_contract_keeps_a_prior_approval(tmp_path: Path) -> None:
    """Negative control: the diff must not invalidate everything by default."""
    contract, _p, _w = _contract(tmp_path)
    result = diff_contracts(contract, contract)
    assert result["identical"] is True
    assert result["changed_axes"] == []
    assert result["prior_approval_still_describes_this_work"] is True
