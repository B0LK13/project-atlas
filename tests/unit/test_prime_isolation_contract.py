"""Isolation-contract pins for the Prime Bubblewrap sandbox profile (PRIME-LOCAL-001).

Live denial evidence for this contract is produced by
``scripts/prime-local-001-sandbox-probe.sh``; these tests pin
``_validate_sandbox_argv`` so an argv-level regression fails here before it can
admit a hostile profile. The pass-through wrapper rejection (``/bin/true``) is
already covered by
``test_prime_agent_adapter.test_preflight_rejects_a_non_isolating_existing_wrapper``
and is intentionally not duplicated.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from project_atlas.orchestration.program.adapters.base import AdapterUnavailableError
from project_atlas.orchestration.program.adapters.prime_agent import (
    SENSITIVE_BWRAP_BIND_SOURCES,
    _validate_sandbox_argv,
)

_REFUSAL = "outside the approved mission scope"


def _smoke_shaped_argv(
    workspace: Path,
    runtime: Path,
    etc_bind: tuple[str, str, str] = ("--ro-bind", "/etc", "/etc"),
) -> list[str]:
    """Mirror the bwrap argv built by scripts/prime-local-001-model-free-smoke.sh."""
    return [
        "/usr/bin/bwrap",
        "--die-with-parent",
        "--new-session",
        "--unshare-all",
        "--ro-bind",
        "/usr",
        "/usr",
        "--ro-bind",
        "/bin",
        "/bin",
        "--ro-bind",
        "/lib",
        "/lib",
        "--ro-bind",
        "/lib64",
        "/lib64",
        *etc_bind,
        "--proc",
        "/proc",
        "--dev",
        "/dev",
        "--tmpfs",
        "/tmp",
        "--dir",
        "/tmp/smoke-home",
        "--tmpfs",
        "/home",
        "--ro-bind",
        str(workspace),
        "/opt/atlas",
        "--ro-bind",
        str(runtime),
        "/opt/prime",
        "--chdir",
        "/opt/atlas",
        "--setenv",
        "HOME",
        "/tmp/smoke-home",
    ]


def test_sensitive_bind_sources_are_pinned() -> None:
    assert {Path("/"), Path("/home"), Path("/root")} <= set(SENSITIVE_BWRAP_BIND_SOURCES)


def test_accepts_smoke_shaped_argv(tmp_path: Path) -> None:
    _validate_sandbox_argv(_smoke_shaped_argv(tmp_path, tmp_path / "runtime"))


@pytest.mark.parametrize("source", ["/home", "/root"])
def test_rejects_sensitive_bind_source(tmp_path: Path, source: str) -> None:
    argv = [*_smoke_shaped_argv(tmp_path, tmp_path / "runtime"), "--ro-bind", source, "/host"]

    with pytest.raises(AdapterUnavailableError, match=_REFUSAL):
        _validate_sandbox_argv(argv)


@pytest.mark.parametrize("target", ["/etc", "/somewhere"])
def test_rejects_writable_etc_bind(tmp_path: Path, target: str) -> None:
    argv = _smoke_shaped_argv(
        tmp_path,
        tmp_path / "runtime",
        etc_bind=("--bind", "/etc", target),
    )

    with pytest.raises(AdapterUnavailableError, match=_REFUSAL):
        _validate_sandbox_argv(argv)


@pytest.mark.parametrize("sensitive", [Path("/home"), Path("/root")])
def test_rejects_sensitive_bind_through_symlink_resolution(
    tmp_path: Path, sensitive: Path
) -> None:
    # The validator checks the resolved bind source, so a workspace-relative
    # symlink that escapes into a sensitive tree must still be refused.
    link = tmp_path / "workspace-link"
    link.symlink_to(sensitive)
    argv = [*_smoke_shaped_argv(tmp_path, tmp_path / "runtime"), "--ro-bind", str(link), "/host"]

    with pytest.raises(AdapterUnavailableError, match=_REFUSAL):
        _validate_sandbox_argv(argv)


def test_accepts_symlink_to_benign_workspace_bind(tmp_path: Path) -> None:
    # Companion to the symlink-resolution pin: a symlink whose target stays
    # inside the approved workspace is not refused.
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    link = tmp_path / "workspace-link"
    link.symlink_to(elsewhere)
    argv = [*_smoke_shaped_argv(tmp_path, tmp_path / "runtime"), "--ro-bind", str(link), "/extra"]

    _validate_sandbox_argv(argv)
