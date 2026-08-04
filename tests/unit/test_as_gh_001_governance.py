"""AS-GH-001 repository-governance-baseline validation.

Deterministic, repository-file-only checks for the governance artifacts
introduced by AS-GH-001 (docs/adr/ADR-006-github-repository-governance-baseline.md,
docs/work-packages/AS-GH-001.md). These tests validate static repository
content only; they never claim to verify live GitHub settings, branch
protection, or Actions run history -- that requires the independent GitHub
API/UI inspection ADR-006 itself calls for.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]


class _DupCheckLoader(yaml.SafeLoader):
    pass


def _construct_mapping(
    loader: _DupCheckLoader, node: yaml.MappingNode, deep: bool = False
) -> dict[str, Any]:
    mapping: dict[str, Any] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in mapping:
            raise ValueError(f"Duplicate key found: {key!r}")
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


_DupCheckLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _construct_mapping)


def _load_yaml_no_duplicates(path: Path) -> Any:
    with path.open(encoding="utf-8") as handle:
        return yaml.load(handle, Loader=_DupCheckLoader)


def _workflow_files() -> list[Path]:
    workflows_dir = REPO_ROOT / ".github" / "workflows"
    return sorted(workflows_dir.glob("*.yml")) + sorted(workflows_dir.glob("*.yaml"))


# ---------------------------------------------------------------------------
# SECURITY.md
# ---------------------------------------------------------------------------


def test_security_md_exists_and_states_current_limitation() -> None:
    path = REPO_ROOT / "SECURITY.md"
    assert path.is_file(), "SECURITY.md must exist"
    text = path.read_text(encoding="utf-8")
    assert "not currently operational" in text.lower()
    assert "ordinary" in text.lower() and "issue" in text.lower()
    lowered = text.lower()
    assert "already-established private" in lowered or "already established private" in lowered


def test_security_md_publishes_no_invented_contact() -> None:
    text = (REPO_ROOT / "SECURITY.md").read_text(encoding="utf-8")
    # Any email-shaped string at all is disallowed in this policy today.
    assert not re.search(r"[\w.+-]+@[\w.-]+\.[a-zA-Z]{2,}", text), (
        "SECURITY.md must not publish any email-shaped contact address"
    )
    assert "security@" not in text.lower()


# ---------------------------------------------------------------------------
# CONTRIBUTING.md
# ---------------------------------------------------------------------------


def test_contributing_md_exists_and_documents_bootstrap_approval_state() -> None:
    path = REPO_ROOT / "CONTRIBUTING.md"
    assert path.is_file(), "CONTRIBUTING.md must exist"
    text = path.read_text(encoding="utf-8")
    assert "pull request" in text.lower()
    # Must not claim a live "1 approval required" state while the documented
    # bootstrap disposition is "0".
    lowered = text.lower()
    assert (
        "`0`" in text
        or "count is 0" in lowered
        or "required-approving-review count is" in lowered
    )


# ---------------------------------------------------------------------------
# Pull request template
# ---------------------------------------------------------------------------


def test_pull_request_template_exists_with_required_sections() -> None:
    path = REPO_ROOT / ".github" / "pull_request_template.md"
    assert path.is_file(), ".github/pull_request_template.md must exist"
    text = path.read_text(encoding="utf-8").lower()
    for required in (
        "base",
        "changed paths",
        "security impact",
        "validation",
        "check names",
        "evidence",
        "rollback",
        "known limitations",
        "reviewer checklist",
    ):
        assert required in text, f"pull request template missing required section: {required!r}"


# ---------------------------------------------------------------------------
# CODEOWNERS
# ---------------------------------------------------------------------------


def test_codeowners_exists_and_has_a_valid_pattern_line() -> None:
    path = REPO_ROOT / ".github" / "CODEOWNERS"
    assert path.is_file(), ".github/CODEOWNERS must exist"
    lines = [
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]
    assert lines, "CODEOWNERS must have at least one non-comment ownership line"
    for line in lines:
        parts = line.split()
        assert len(parts) >= 2, f"CODEOWNERS line must be '<pattern> <owner...>': {line!r}"
        for owner in parts[1:]:
            assert owner.startswith("@"), f"CODEOWNERS owner must start with '@': {owner!r}"


# ---------------------------------------------------------------------------
# Dependabot
# ---------------------------------------------------------------------------


def test_dependabot_configures_only_real_ecosystems() -> None:
    path = REPO_ROOT / ".github" / "dependabot.yml"
    assert path.is_file(), ".github/dependabot.yml must exist"
    config = _load_yaml_no_duplicates(path)
    ecosystems = {entry["package-ecosystem"] for entry in config["updates"]}
    assert ecosystems == {"pip", "github-actions"}, (
        f"Dependabot must configure exactly pip and github-actions, found: {ecosystems}"
    )
    for entry in config["updates"]:
        assert entry.get("open-pull-requests-limit", 0) > 0
        assert entry.get("schedule", {}).get("interval")


# ---------------------------------------------------------------------------
# Workflow YAML validity and duplicate-key freedom
# ---------------------------------------------------------------------------


def test_all_workflow_and_dependabot_yaml_parse_without_duplicate_keys() -> None:
    targets = [*_workflow_files(), REPO_ROOT / ".github" / "dependabot.yml"]
    assert targets, "expected at least one workflow file to check"
    for path in targets:
        try:
            _load_yaml_no_duplicates(path)
        except ValueError as exc:
            raise AssertionError(f"duplicate key in {path}: {exc}") from exc


def test_all_docs_evidence_yaml_parse_without_duplicate_keys() -> None:
    evidence_dir = REPO_ROOT / "docs" / "evidence"
    for path in sorted(evidence_dir.glob("*.yaml")):
        try:
            _load_yaml_no_duplicates(path)
        except ValueError as exc:
            raise AssertionError(f"duplicate key in {path}: {exc}") from exc


# ---------------------------------------------------------------------------
# Action pinning
# ---------------------------------------------------------------------------


_SHA_PIN = re.compile(r"^[a-f0-9]{40}$")


def test_every_third_party_action_is_pinned_to_a_full_commit_sha() -> None:
    uses_pattern = re.compile(r"uses:\s*([^\s#]+)")
    for path in _workflow_files():
        text = path.read_text(encoding="utf-8")
        for match in uses_pattern.finditer(text):
            reference = match.group(1)
            assert "@" in reference, f"{path}: action missing a version pin: {reference!r}"
            action, _, pin = reference.rpartition("@")
            assert _SHA_PIN.match(pin), (
                f"{path}: action {action!r} is not pinned to a full commit SHA (found {pin!r})"
            )


# ---------------------------------------------------------------------------
# Workflow permissions
# ---------------------------------------------------------------------------


def test_every_workflow_declares_explicit_least_privilege_permissions() -> None:
    for path in _workflow_files():
        config = _load_yaml_no_duplicates(path)
        assert "permissions" in config, f"{path}: missing a top-level 'permissions' block"
        permissions = config["permissions"]
        assert permissions == {"contents": "read"} or permissions == "read-all" or (
            isinstance(permissions, dict) and permissions.get("contents") == "read"
        ), f"{path}: permissions must be read-only unless explicitly justified: {permissions!r}"


def test_no_workflow_uses_pull_request_target() -> None:
    for path in _workflow_files():
        config = _load_yaml_no_duplicates(path)
        triggers = config.get("on") or config.get(True) or {}
        assert "pull_request_target" not in triggers, f"{path}: pull_request_target not permitted"


def test_ci_workflow_preserves_the_quality_job_name() -> None:
    ci_path = REPO_ROOT / ".github" / "workflows" / "ci.yml"
    config = _load_yaml_no_duplicates(ci_path)
    assert "quality" in config["jobs"], (
        "the existing project-owned 'quality' job/check name must be preserved, not renamed"
    )


def test_atlas_documentation_gate_remains_workflow_dispatch_only() -> None:
    path = REPO_ROOT / ".github" / "workflows" / "atlas-documentation-gate.yml"
    config = _load_yaml_no_duplicates(path)
    triggers = config.get("on") or config.get(True) or {}
    assert set(triggers) == {"workflow_dispatch"}, (
        "atlas-documentation-gate.yml must remain workflow_dispatch-only, "
        f"found triggers: {set(triggers)}"
    )
