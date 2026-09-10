"""Offline adversarial tests for ATLAS_AGENT_REGISTRY_V1 (FEATURE_01).

Fail-closed matrix under test (D-ATLAS-DAG-FEATURE-01):
- missing registry => no inferred write authority;
- unknown agent => UNKNOWN_AGENT, never a permissive default;
- duplicate agent IDs => registry invalid;
- unknown/malformed capability values => rejected;
- conflicting capability/prohibition declarations => rejected;
- an Ubuntu-only profile cannot imply Windows-native authority;
- write scope cannot override an active ownership mutex;
- write scope cannot override a certified-surface freeze;
- registry entries can never satisfy formal IV by themselves;
- registry data cannot convert an OWNER/IV/POLICY-gated node into
  writable work;
- inactive profiles describe dormant roles, not running sessions: no
  current authority;
- merge authority is not grantable by any registry entry.

Positive controls prove the denials are specific, not a blanket refuse-all.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from atlas_dag import agents as agents_mod  # noqa: E402

REGISTRY_PATH = REPO_ROOT / "registry" / "agents.json"


def make_profile(**overrides) -> dict:
    profile = {
        "agent_id": "ubuntu-main",
        "role": "test role",
        "active": True,
        "platforms": ["linux"],
        "capabilities": [
            "READ_REPO", "READ_GITHUB", "RUN_TESTS", "WRITE_CODE",
            "WRITE_TESTS", "POST_EVENTS", "INGEST_EVIDENCE",
            "CLAIM_OWNERSHIP", "MANAGE_WORKTREE",
        ],
        "prohibitions": [
            "AUTO_MERGE", "HISTORY_REWRITE", "FORCE_PUSH", "SELF_IV",
            "FABRICATE_VERIFIER_PRINCIPAL", "BYPASS_OWNER_GATE",
            "BYPASS_FREEZE", "EMULATE_WINDOWS_VALIDATION",
            "SUDO_SYSTEM_MUTATION", "REUSE_CERTIFICATION_AFTER_HEAD_MOVE",
            "TRUST_PROSPECTIVE_MERGE_SHA",
        ],
        "write_scopes": [
            "path:scripts/atlas_dag", "github:issue-comment:719",
            "github:pr-branch:own-lane",
        ],
        "event_permissions": ["OWNER_CLAIMED", "HEAD_MOVED", "CI_COMPLETED"],
        "verification_class": "IMPLEMENTATION",
        "principal": "github:B0LK13",
    }
    profile.update(overrides)
    return profile


def write_registry(tmp_path: Path, agents: list[dict]) -> Path:
    path = tmp_path / "agents.json"
    path.write_text(json.dumps({
        "schema": "ATLAS_AGENT_REGISTRY_V1",
        "registry_id": "test-registry",
        "version": 1,
        "agents": agents,
    }), encoding="utf-8")
    return path


@pytest.fixture
def registry(tmp_path) -> agents_mod.RegistryResult:
    return agents_mod.load_registry(write_registry(tmp_path, [make_profile()]))


# --- structural fail-closed -------------------------------------------------

def test_missing_registry_fails_closed_no_inferred_authority(tmp_path):
    result = agents_mod.load_registry(tmp_path / "nope.json")
    assert not result.valid
    resolved = agents_mod.resolve_agent(result, "ubuntu-main")
    assert resolved.status == "REGISTRY_INVALID"
    allowed, reasons = agents_mod.evaluate(None, agents_mod.AgentRequest(
        action="write", platform="linux", scope="path:scripts/atlas_dag"))
    assert not allowed
    assert "NO_INFERRED_WRITE_AUTHORITY" in reasons


def test_unknown_agent_never_permissive(registry):
    resolved = agents_mod.resolve_agent(registry, "mystery-agent")
    assert resolved.status == "UNKNOWN_AGENT"
    assert resolved.profile is None
    allowed, _ = agents_mod.evaluate(resolved.profile, agents_mod.AgentRequest(
        action="read", platform="linux"))
    assert not allowed


def test_duplicate_agent_ids_invalid_registry(tmp_path):
    result = agents_mod.load_registry(
        write_registry(tmp_path, [make_profile(), make_profile()]))
    assert not result.valid
    assert any("DUPLICATE_AGENT_ID" in e for e in result.errors)


def test_unknown_capability_value_rejected(tmp_path):
    bad = make_profile(capabilities=["WRITE_CODE", "FLY_TO_MARS"])
    result = agents_mod.load_registry(write_registry(tmp_path, [bad]))
    assert not result.valid


def test_unknown_prohibition_value_rejected(tmp_path):
    bad = make_profile(prohibitions=["AUTO_MERGE", "DO_WHATEVER"])
    result = agents_mod.load_registry(write_registry(tmp_path, [bad]))
    assert not result.valid


def test_conflicting_capability_prohibition_fails_closed(tmp_path):
    bad = make_profile(capabilities=["AUTO_MERGE"], prohibitions=["AUTO_MERGE"])
    result = agents_mod.load_registry(write_registry(tmp_path, [bad]))
    assert not result.valid
    assert any("CONFLICTING_DECLARATION" in e for e in result.errors)


def test_verifier_class_requires_verifier_role(tmp_path):
    bad = make_profile(verification_class="INDEPENDENT_VERIFIER", role="coordinator")
    result = agents_mod.load_registry(write_registry(tmp_path, [bad]))
    assert not result.valid
    assert any("VERIFIER_CLASS_REQUIRES_VERIFIER_ROLE" in e for e in result.errors)


def test_receipt_is_not_an_event_permission(tmp_path):
    bad = make_profile(event_permissions=["OWNER_CLAIMED", "ATLAS_IV_RECEIPT_V1"])
    result = agents_mod.load_registry(write_registry(tmp_path, [bad]))
    assert not result.valid
    assert any("RECEIPT_NOT_AN_EVENT_PERMISSION" in e for e in result.errors)


def test_checked_in_registry_is_valid():
    result = agents_mod.load_registry(REGISTRY_PATH)
    assert result.valid, result.errors
    ids = [a["agent_id"] for a in result.registry["agents"]]
    assert len(ids) == len(set(ids))


# --- authority boundaries (capability != authority) --------------------------

def test_shipped_ubuntu_main_write_on_own_scope_allowed():
    result = agents_mod.load_registry(REGISTRY_PATH)
    profile = agents_mod.resolve_agent(result, "ubuntu-main").profile
    allowed, _ = agents_mod.evaluate(profile, agents_mod.AgentRequest(
        action="write", platform="linux", scope="path:scripts/atlas_dag"))
    assert allowed


def test_write_outside_scope_denied():
    result = agents_mod.load_registry(REGISTRY_PATH)
    profile = agents_mod.resolve_agent(result, "ubuntu-main").profile
    allowed, reasons = agents_mod.evaluate(profile, agents_mod.AgentRequest(
        action="write", platform="linux", scope="path:src/project_atlas"))
    assert not allowed
    assert any("WRITE_SCOPE_NOT_COVERED" in r for r in reasons)


def test_ubuntu_profile_cannot_imply_windows_authority():
    result = agents_mod.load_registry(REGISTRY_PATH)
    profile = agents_mod.resolve_agent(result, "ubuntu-main").profile
    allowed, reasons = agents_mod.evaluate(profile, agents_mod.AgentRequest(
        action="run_on_platform", platform="windows"))
    assert not allowed
    assert any(r.startswith("PLATFORM_NOT_SUPPORTED") for r in reasons)
    # windows-native validation is doubly fenced: the explicit prohibition too
    assert "EMULATE_WINDOWS_VALIDATION" in profile["prohibitions"]


def test_write_scope_cannot_override_ownership_mutex():
    result = agents_mod.load_registry(REGISTRY_PATH)
    profile = agents_mod.resolve_agent(result, "ubuntu-main").profile
    allowed, reasons = agents_mod.evaluate(profile, agents_mod.AgentRequest(
        action="write", platform="linux", scope="path:scripts/atlas_dag",
        lane_owner="windows-main"))
    assert not allowed
    assert "OWNERSHIP_MUTEX_HELD_BY_OTHER" in reasons


def test_write_scope_cannot_override_freeze():
    result = agents_mod.load_registry(REGISTRY_PATH)
    profile = agents_mod.resolve_agent(result, "ubuntu-main").profile
    allowed, reasons = agents_mod.evaluate(profile, agents_mod.AgentRequest(
        action="write", platform="linux", scope="path:scripts/atlas_dag",
        lane_frozen=True))
    assert not allowed
    assert any(r.startswith("LANE_FROZEN") for r in reasons)


def test_formal_iv_never_granted_by_registry():
    result = agents_mod.load_registry(REGISTRY_PATH)
    for agent_id in ("ubuntu-main", "independent-verifier"):
        profile = agents_mod.resolve_agent(result, agent_id).profile
        allowed, reasons = agents_mod.evaluate(
            profile, agents_mod.AgentRequest(action="satisfy_formal_iv"))
        assert not allowed
        assert "FORMAL_IV_NOT_GRANTABLE_BY_REGISTRY" in reasons


def test_receipt_publication_requires_principal_binding():
    result = agents_mod.load_registry(REGISTRY_PATH)
    profile = agents_mod.resolve_agent(result, "independent-verifier").profile
    allowed, reasons = agents_mod.evaluate(
        profile, agents_mod.AgentRequest(action="post_receipt"))
    assert not allowed
    assert "VERIFIER_PRINCIPAL_AUTHENTICATION_NOT_IMPLEMENTED" in reasons
    # and the shipped verifier profile is honestly unbound
    assert profile["principal"] is None


def test_merge_authority_not_grantable():
    result = agents_mod.load_registry(REGISTRY_PATH)
    profile = agents_mod.resolve_agent(result, "ubuntu-main").profile
    allowed, reasons = agents_mod.evaluate(
        profile, agents_mod.AgentRequest(action="merge"))
    assert not allowed
    assert "MERGE_AUTHORITY_NOT_GRANTABLE_BY_REGISTRY" in reasons


def test_registry_cannot_unlock_owner_gated_node():
    """An OWNER-gated node stays unwritable even for the profile with the
    broadest shipped capabilities: the mutex is repository truth."""
    result = agents_mod.load_registry(REGISTRY_PATH)
    profile = agents_mod.resolve_agent(result, "ubuntu-main").profile
    allowed, reasons = agents_mod.evaluate(profile, agents_mod.AgentRequest(
        action="write", platform="linux", scope="path:scripts/atlas_dag",
        lane_owner="obsidian-agent"))
    assert not allowed
    assert "OWNERSHIP_MUTEX_HELD_BY_OTHER" in reasons


def test_inactive_profile_has_no_current_authority():
    """Dormant roles are not running sessions: every action denies."""
    result = agents_mod.load_registry(REGISTRY_PATH)
    for agent_id in ("windows-main", "obsidian-agent", "tooling-specialist",
                     "runtime-specialist", "independent-verifier"):
        profile = agents_mod.resolve_agent(result, agent_id).profile
        allowed, reasons = agents_mod.evaluate(profile, agents_mod.AgentRequest(
            action="write", platform="linux", scope="path:scripts/atlas_dag"))
        assert not allowed, agent_id
        assert "AGENT_INACTIVE" in reasons, agent_id


def test_unknown_action_rejected(registry):
    profile = agents_mod.resolve_agent(registry, "ubuntu-main").profile
    allowed, reasons = agents_mod.evaluate(profile, agents_mod.AgentRequest(
        action="reboot_production"))
    assert not allowed
    assert any(r.startswith("UNKNOWN_ACTION") for r in reasons)


# --- event permissions -------------------------------------------------------

def test_post_event_allowed_type(registry):
    profile = agents_mod.resolve_agent(registry, "ubuntu-main").profile
    allowed, _ = agents_mod.evaluate(profile, agents_mod.AgentRequest(
        action="post_event", event_type="OWNER_CLAIMED"))
    assert allowed


def test_post_event_unlisted_type_denied(registry):
    profile = agents_mod.resolve_agent(registry, "ubuntu-main").profile
    allowed, reasons = agents_mod.evaluate(profile, agents_mod.AgentRequest(
        action="post_event", event_type="MERGED"))
    assert not allowed
    assert any(r.startswith("EVENT_TYPE_NOT_PERMITTED") for r in reasons)


def test_claim_lane_unowned_allowed_owned_denied(registry):
    profile = agents_mod.resolve_agent(registry, "ubuntu-main").profile
    allowed, _ = agents_mod.evaluate(profile, agents_mod.AgentRequest(
        action="claim_lane"))
    assert allowed
    allowed, reasons = agents_mod.evaluate(profile, agents_mod.AgentRequest(
        action="claim_lane", lane_owner="windows-main"))
    assert not allowed
    assert "OWNERSHIP_MUTEX_HELD_BY_OTHER" in reasons


def test_windows_lane_claim_from_windows_platform_inactive_denied():
    """Platform fit is necessary, not sufficient: the profile is dormant."""
    result = agents_mod.load_registry(REGISTRY_PATH)
    profile = agents_mod.resolve_agent(result, "windows-main").profile
    allowed, reasons = agents_mod.evaluate(profile, agents_mod.AgentRequest(
        action="claim_lane", platform="windows"))
    assert not allowed
    assert "AGENT_INACTIVE" in reasons


# --- CLI (live, project-local) ----------------------------------------------

def test_cli_agents_and_agent_and_unknown_fails_closed():
    import subprocess

    base = [sys.executable, str(REPO_ROOT / "scripts" / "atlas-dag.py")]
    proc = subprocess.run([*base, "agents"], capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    assert "ubuntu-main" in proc.stdout

    proc = subprocess.run([*base, "agent", "ubuntu-main", "--eval", "merge"],
                          capture_output=True, text=True)
    assert proc.returncode == 1  # merge evaluation denies
    assert "MERGE_AUTHORITY_NOT_GRANTABLE_BY_REGISTRY" in proc.stdout

    proc = subprocess.run([*base, "agent", "nobody-here"], capture_output=True,
                          text=True)
    assert proc.returncode == 1  # unknown agent: fail closed
    assert "UNKNOWN_AGENT" in proc.stderr


def test_cli_snapshot_exposes_registry(tmp_path):
    import subprocess

    proc = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "atlas-dag.py"),
         "--repo", "B0LK13/project-atlas", "--runtime-dir", str(tmp_path),
         "--json", "snapshot"],
        capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    registry_info = payload["agent_registry"]
    assert registry_info["schema"] == "ATLAS_AGENT_REGISTRY_V1"
    assert registry_info["valid"] is True
    assert "ubuntu-main" in registry_info["agent_ids"]
