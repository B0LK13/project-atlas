from __future__ import annotations

from pathlib import Path

from project_atlas.orchestration.program.adapters.prime_agent import PrimeExecutorAdapter
from project_atlas.orchestration.program.profiles import AdapterKind
from project_atlas.orchestration.program.runtimes import describe
from project_atlas.orchestration.program.supervisor import _build_adapter


def test_prime_is_an_explicit_runtime_not_a_generic_command() -> None:
    assert AdapterKind.PRIME_AGENT.value == "prime-agent"
    support = describe(AdapterKind.PRIME_AGENT)
    assert support.adapter is AdapterKind.PRIME_AGENT
    assert support.tier.value == "IMPLEMENTED_FIXTURE_ONLY"
    assert "ordinary client-owned RPC" in " ".join(support.unsupported)


def test_prime_adapter_is_constructed_from_profile_options(tmp_path: Path) -> None:
    from project_atlas.orchestration.program.profiles import AgentProfile

    profile = AgentProfile(
        profile_id="prime",
        agent_id="prime-agent",
        adapter=AdapterKind.PRIME_AGENT,
        capabilities=("IMPLEMENT",),
        adapter_options={
            "executable": "/does/not/exist",
            "daemon_socket": str(tmp_path / "prime.sock"),
        },
    )
    adapter = _build_adapter(profile)
    assert adapter.capabilities.adapter_id == "prime-agent"
    assert adapter.upstream_sha.startswith("5d25a44")
    assert adapter.capabilities.supports_resume is True


def test_daemon_profile_enables_only_the_resident_capabilities(tmp_path: Path) -> None:
    adapter = PrimeExecutorAdapter(
        "/does/not/exist", daemon_socket=tmp_path / "prime.sock"
    )
    assert adapter.capabilities.supports_resume is True
    assert adapter.capabilities.accepts_assigned_session is False
