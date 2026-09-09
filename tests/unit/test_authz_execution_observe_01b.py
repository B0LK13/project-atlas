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


# ---------------------------------------------------------------------------
# ULT-01b-1-T (proposed): behavioural tests for guards that the round-4 ADV
# harness found protected only by the sha-pin freeze guard (Z06, Z08, Z09,
# Z10, Z11, Z16). Each is a code-holds guard; these tests make the controls
# script, not the pin, the thing that proves it.


def test_cli_gate_refuses_an_unknown_required_capability_before_reading_the_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Z06: the unknown-capability check precedes the allow-list: with no
    # allow-list at all the refusal names the unknown capability, never
    # "elevation required" (which would invite the operator to grant it).
    monkeypatch.delenv(CLI_ELEVATE_CAPS_ENV, raising=False)
    with pytest.raises(AuthzError, match=r"^authz-unknown-capability:execution\.observ$"):
        require_cli_elevated_operator("op", required={"execution.observ"})  # type: ignore[arg-type]
    monkeypatch.setenv(CLI_ELEVATE_CAPS_ENV, "execution.observ,execution.observe")
    with pytest.raises(AuthzError, match=r"^authz-unknown-capability:execution\.observ$"):
        require_cli_elevated_operator("op", required={"execution.observ"})  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "value",
    [
        "*",  # Z08 wildcard
        "EXECUTION.OBSERVE",  # Z09 case
        "Execution.Observe",
        "execution",  # Z10 prefix / segment
        "execution.",
        "execution.observer",
        "execution.observe.extra",
        "execution.*",
        "execution.observe​",
        "executi\u043en.observe",  # Cyrillic small o as a confusable
        "'execution.observe'",
        "execution.observe;vault.write",
        "execution.observe\tvault.write",
    ],
)
def test_cli_allow_list_grants_only_the_exact_token(
    monkeypatch: pytest.MonkeyPatch, value: str
) -> None:
    monkeypatch.setenv(CLI_ELEVATE_CAPS_ENV, value)
    with pytest.raises(AuthzError, match=r"authz-cli-elevation-incomplete:execution\.observe"):
        require_cli_elevated_operator("op", required={CAP})


def test_elevated_operator_refuses_near_miss_capabilities() -> None:
    # Z11: the unknown-capability check in elevated_operator is load-bearing
    for bogus in ("execution.observ", "EXECUTION.OBSERVE", "execution.observe ", "*"):
        with pytest.raises(AuthzError, match=r"authz-unknown-capability:"):
            elevated_operator("x", extra={bogus})  # type: ignore[arg-type]


def test_read_credential_is_the_read_only_intersection_even_for_a_fully_privileged_launch() -> None:
    # Z16: a launch operator holding EVERY privileged capability still yields a
    # read credential that is exactly the read-only intersection
    launch = elevated_operator("root-ish", extra=set(PRIVILEGED_CAPABILITIES))
    assert launch.allows(CAP) and launch.allows("vault.write")
    store = mint_api_session(launch)
    read_caps = store.credentials.read_operator.capabilities
    assert read_caps == (launch.capabilities & READ_ONLY_CAPABILITIES)
    assert read_caps.isdisjoint(PRIVILEGED_CAPABILITIES)
    assert store.credentials.privileged_operator is launch
    assert store.credentials.read_token != store.credentials.privileged_token
