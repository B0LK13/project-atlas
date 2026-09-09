"""ULT-01b-1 operational authorization: `execution.observe` is privileged and default-off.

Owner directive GOAL = COMPLETE_ULT_01B_1_OPERATIONAL_AUTHORIZATION (O3 approved):
the capability is registered in the frozen ``project_atlas.authz`` surface under
the pinned exception OG-ULT-01B-1-AUTHZ-EXECUTION-OBSERVE-20260909. These tests pin
the intended semantics and prove that nothing else in the default privilege
model moved (AUTHZ_DEFAULT_PRIVILEGE = UNCHANGED).
"""

from __future__ import annotations

import pytest

from project_atlas.authz import (
    ALL_CAPABILITIES,
    CLI_ELEVATE_CAPS_ENV,
    DEFAULT_OPERATOR_CAPS,
    PRIVILEGED_CAPABILITIES,
    READ_ONLY_CAPABILITIES,
    AuthzError,
    default_operator,
    elevated_operator,
    mint_api_session,
    read_only_operator,
    require_cli_elevated_operator,
)

CAP = "execution.observe"

# The frozen sets as they were at preimage sha256 505ca5bb… (blob c6dd713a),
# copied verbatim: any drift here is a change to default privilege.
FROZEN_DEFAULT_OPERATOR_CAPS = frozenset(
    {
        "api.read",
        "web.read",
        "mcp.read",
        "oai.import",
        "oai.responses",
        "pilot.scan",
        "scheduler.arm",
        "chatgpt.bridge",
        "collab.session",
    }
)
FROZEN_READ_ONLY_CAPABILITIES = FROZEN_DEFAULT_OPERATOR_CAPS
FROZEN_PRIVILEGED_CAPABILITIES = frozenset(
    {"web.action", "vault.write", "autonomy.l3", "scheduler.dispatch", "provider.live"}
)
FROZEN_ALL_CAPABILITIES = FROZEN_DEFAULT_OPERATOR_CAPS | FROZEN_PRIVILEGED_CAPABILITIES


def test_execution_observe_is_registered_privileged_and_default_off() -> None:
    assert CAP in ALL_CAPABILITIES
    assert CAP in PRIVILEGED_CAPABILITIES
    assert CAP not in DEFAULT_OPERATOR_CAPS
    assert CAP not in READ_ONLY_CAPABILITIES


def test_default_privilege_model_is_unchanged_except_the_one_registration() -> None:
    assert DEFAULT_OPERATOR_CAPS == FROZEN_DEFAULT_OPERATOR_CAPS
    assert READ_ONLY_CAPABILITIES == FROZEN_READ_ONLY_CAPABILITIES
    assert FROZEN_PRIVILEGED_CAPABILITIES | {CAP} == PRIVILEGED_CAPABILITIES
    assert FROZEN_ALL_CAPABILITIES | {CAP} == ALL_CAPABILITIES
    # privileged and read-only stay disjoint; the default operator holds no
    # privileged capability
    assert PRIVILEGED_CAPABILITIES.isdisjoint(READ_ONLY_CAPABILITIES)
    assert DEFAULT_OPERATOR_CAPS.isdisjoint(PRIVILEGED_CAPABILITIES)


def test_default_operator_cannot_observe() -> None:
    assert default_operator().allows(CAP) is False
    with pytest.raises(AuthzError, match=r"authz-"):
        default_operator().require(CAP)


def test_read_only_operator_cannot_observe() -> None:
    assert read_only_operator().allows(CAP) is False
    with pytest.raises(AuthzError, match=r"authz-"):
        read_only_operator().require(CAP)


def test_cli_elevation_is_explicit_never_self_granted(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(CLI_ELEVATE_CAPS_ENV, raising=False)
    with pytest.raises(AuthzError, match=r"authz-cli-elevation-required:execution\.observe"):
        require_cli_elevated_operator("op", required={CAP})
    monkeypatch.setenv(CLI_ELEVATE_CAPS_ENV, "vault.write,provider.live")
    with pytest.raises(AuthzError, match=r"authz-cli-elevation-incomplete:execution\.observe"):
        require_cli_elevated_operator("op", required={CAP})
    monkeypatch.setenv(CLI_ELEVATE_CAPS_ENV, "execution.observe")
    profile = require_cli_elevated_operator("op", required={CAP})
    assert profile.allows(CAP)
    # elevation adds exactly the required capability on top of the defaults
    assert profile.capabilities == DEFAULT_OPERATOR_CAPS | {CAP}
    assert not profile.allows("vault.write")


def test_default_launch_mints_no_privileged_credential() -> None:
    plain = mint_api_session(default_operator())
    assert not plain.credentials.read_operator.allows(CAP)
    assert plain.credentials.privileged_token is None


def test_read_credentials_never_carry_execution_observe() -> None:
    elevated = mint_api_session(elevated_operator("obs", extra={CAP}))
    assert not elevated.credentials.read_operator.allows(CAP)
    assert elevated.credentials.read_operator.capabilities <= READ_ONLY_CAPABILITIES
    # a launch operator holding the privileged capability gets a distinct
    # privileged credential bound to that operator -- the existing SEC-009 model
    assert elevated.credentials.privileged_token is not None
    assert elevated.credentials.privileged_operator is not None
    assert elevated.credentials.privileged_operator.allows(CAP)
    assert elevated.credentials.privileged_token != elevated.credentials.read_token
