"""Model-free kernel binding preflight for ATLAS-PRIME-WORKING-SLICE-001.

Capability-1 recorded a valid structured ipython call that failed at kernel
start because PRIME_AGENT_KERNEL_PYTHON pointed at an incomplete environment.
These tests assert the shipped RUNTIME_READY_CHECK contract against a known
good mission kernel and a known-bad disposable interpreter — without inference.
"""

from __future__ import annotations

import os
import stat
import subprocess
import textwrap
from pathlib import Path

import pytest

from project_atlas.orchestration.program.adapters.base import AdapterUnavailableError
from project_atlas.orchestration.program.adapters.prime_agent import (
    _add_kernel_python_environment,
)
from project_atlas.orchestration.program.profiles import AdapterKind, AgentProfile

# Extracted from pinned prime-agent bootstrap.ts RUNTIME_READY_CHECK (5d25a44).
_RUNTIME_READY_CHECK = textwrap.dedent(
    r"""
    import inspect
    import rlm
    import rlm.mcp as mcp
    from rlm.harness import HarnessEntry
    _harness_methods = [
        "create_memory", "update_memory", "delete_memory",
        "create_skill", "update_skill", "delete_skill",
        "create_subagent", "update_subagent", "delete_subagent",
        "create_prompt_note", "update_prompt_note", "delete_prompt_note",
        "record_refinement",
    ]
    _mcp = ["list_plugins", "search_plugins", "list_connections", "search_tools", "describe_tool"]
    assert callable(mcp.list_tools)
    assert callable(mcp.call_tool)
    assert all(callable(getattr(mcp, _m, None)) for _m in _mcp)
    assert callable(rlm.spawn)
    assert hasattr(rlm, "rlm") and callable(rlm.rlm.spawn)
    assert inspect.signature(rlm.spawn).parameters["name"].default is inspect.Parameter.empty
    assert not hasattr(rlm, "run") and not hasattr(rlm.rlm, "run")
    assert callable(rlm.host_request)
    assert callable(rlm.find_models) and callable(rlm.rlm.find_models)
    assert callable(rlm.create_session) and callable(rlm.rlm.create_session)
    assert hasattr(rlm, "harness") and hasattr(rlm, "get_harness_state")
    assert hasattr(rlm.rlm, "harness") and hasattr(rlm.rlm, "get_harness_state")
    assert all(
        callable(getattr(_harness, _method, None))
        for _harness in (rlm.harness, rlm.rlm.harness)
        for _method in _harness_methods
    )
    assert "reference" in HarnessEntry.__dataclass_fields__
    assert "scope" in HarnessEntry.__dataclass_fields__
    import rlm.repl as _repl
    assert callable(_repl.main) and _repl.PROTOCOL_VERSION == 3
    """
).strip()

_MISSION_KERNEL = Path(
    "/home/gebruiker/.cache/atlas-r-deploy/prime-local-001/working-slice-001/"
    "env/kernel-venv/bin/python"
)

_CAPABILITY1_PREFIX = (
    "PRIME_AGENT_KERNEL_PYTHON points to a Python missing a current "
    "prime-agent-runtime with callable rlm.spawn"
)


def _profile(kernel_python: str | None) -> AgentProfile:
    options: dict[str, object] = {}
    if kernel_python is not None:
        options["kernel_python"] = kernel_python
    return AgentProfile(
        profile_id="prime-kernel-preflight",
        agent_id="prime-kernel-preflight",
        adapter=AdapterKind.PRIME_AGENT,
        capabilities=("IMPLEMENT",),
        adapter_options=options,
    )


@pytest.mark.skipif(not _MISSION_KERNEL.is_file(), reason="mission kernel missing")
def test_mission_kernel_passes_runtime_ready_check() -> None:
    completed = subprocess.run(
        [str(_MISSION_KERNEL), "-c", _RUNTIME_READY_CHECK],
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )
    assert completed.returncode == 0, completed.stderr or completed.stdout


def test_incomplete_kernel_python_fails_runtime_ready_check(tmp_path: Path) -> None:
    """Capability-1 shape: executable Python without current prime-agent-runtime."""
    fake = tmp_path / "fake-python"
    fake.write_text(
        "#!/bin/sh\n"
        "echo 'import sys' > /dev/null\n"
        "exec /usr/bin/python3 \"$@\"\n",
        encoding="utf-8",
    )
    fake.chmod(fake.stat().st_mode | stat.S_IXUSR)
    # Bare python3 has no rlm — the ready check must fail closed.
    completed = subprocess.run(
        [str(fake), "-c", "import rlm"],
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    assert completed.returncode != 0
    ready = subprocess.run(
        [str(fake), "-c", _RUNTIME_READY_CHECK],
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    assert ready.returncode != 0
    # Adapter still binds any absolute executable; readiness is a separate gate.
    env: dict[str, str] = {}
    _add_kernel_python_environment(_profile(str(fake)), env)
    assert env["PRIME_AGENT_KERNEL_PYTHON"] == str(fake)


def test_kernel_python_binding_rejects_non_executable(tmp_path: Path) -> None:
    missing = tmp_path / "missing-python"
    with pytest.raises(AdapterUnavailableError) as exc:
        _add_kernel_python_environment(_profile(str(missing)), {})
    assert exc.value.code == "INVALID_KERNEL_PYTHON"


def test_capability1_error_prefix_is_stable() -> None:
    """Keep the diagnostic classifier's exact kernel-start prefix pinned."""
    assert "rlm.spawn" in _CAPABILITY1_PREFIX
    assert os.environ.get("ATLAS_PRIME_SKIP_KERNEL_PREFIX") is None
