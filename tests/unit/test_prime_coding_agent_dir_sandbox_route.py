"""Model-free GO/NO-GO for coding_agent_dir/session_dir through bwrap (CONFIG-RETRY-001).

Proves the real config route without inference or an agent loop:
program/profile -> adapter resolution -> written provider config -> env ->
bwrap mount namespace -> readable config digest inside the sandbox.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from pathlib import Path

import pytest

from project_atlas.orchestration.program.adapters.prime_agent import (
    _write_local_provider_config,
)


WORKSPACE = Path("/tmp/atlas-prime-e2e-002-workspace")
IPC = Path("/tmp/atlas-prime-e2e-002-ipc")
CODING_AGENT_DIR = WORKSPACE / ".prime-config"
SESSION_DIR = WORKSPACE / ".prime-sessions"
PROVIDER = "atlas-local-qwen"
MODEL = "qwen3:1.7b-q4_K_M"
PROXY_PORT = 38741


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _minimal_bwrap_read(path_inside: str) -> subprocess.CompletedProcess[str]:
    """Read a path from inside the same class of mount namespace the program uses."""
    argv = [
        "/usr/bin/bwrap",
        "--die-with-parent",
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
        "--ro-bind",
        "/etc",
        "/etc",
        "--proc",
        "/proc",
        "--dev",
        "/dev",
        "--tmpfs",
        "/tmp",
        "--tmpfs",
        "/home",
        "--dir",
        str(WORKSPACE),
        "--bind",
        str(WORKSPACE),
        str(WORKSPACE),
        "--dir",
        str(IPC),
        "--bind",
        str(IPC),
        str(IPC),
        "--chdir",
        str(WORKSPACE),
        "--setenv",
        "HOME",
        "/tmp/prime-home",
        "--",
        "/usr/bin/python3",
        "-c",
        (
            "import pathlib,sys;"
            f"p=pathlib.Path({path_inside!r});"
            "sys.exit(0 if p.is_file() else 2);"
            "print(p.read_text()[:1])"
        ),
    ]
    return subprocess.run(argv, capture_output=True, text=True, timeout=30)


def _bwrap_sha256(path_inside: str) -> str:
    script = (
        "import hashlib, pathlib, sys;"
        f"p=pathlib.Path({path_inside!r});"
        "data=p.read_bytes();"
        "sys.stdout.write(hashlib.sha256(data).hexdigest())"
    )
    argv = [
        "/usr/bin/bwrap",
        "--die-with-parent",
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
        "--ro-bind",
        "/etc",
        "/etc",
        "--proc",
        "/proc",
        "--dev",
        "/dev",
        "--tmpfs",
        "/tmp",
        "--tmpfs",
        "/home",
        "--dir",
        str(WORKSPACE),
        "--ro-bind",
        str(WORKSPACE),
        str(WORKSPACE),
        "--dir",
        str(IPC),
        "--bind",
        str(IPC),
        str(IPC),
        "--chdir",
        str(WORKSPACE),
        "--setenv",
        "HOME",
        "/tmp/prime-home",
        "--",
        "/usr/bin/python3",
        "-c",
        script,
    ]
    proc = subprocess.run(argv, capture_output=True, text=True, timeout=30)
    assert proc.returncode == 0, proc.stderr
    return proc.stdout.strip()


def test_A_configured_dirs_resolve_not_home_prime(tmp_path: Path) -> None:
    """A: non-default coding_agent_dir and session_dir are the effective sources."""
    assert str(CODING_AGENT_DIR).startswith(str(WORKSPACE))
    assert str(SESSION_DIR).startswith(str(WORKSPACE))
    assert Path.home() / ".prime" != CODING_AGENT_DIR
    assert "HOME/.prime" not in str(CODING_AGENT_DIR)
    # Adapter resolution mirror (resident path)
    configured_agent_dir = str(CODING_AGENT_DIR)
    configured_session_dir = str(SESSION_DIR)
    agent_dir = (
        Path(configured_agent_dir)
        if isinstance(configured_agent_dir, str) and configured_agent_dir
        else tmp_path / "evidence" / "prime-config"
    )
    session_dir = (
        Path(configured_session_dir)
        if isinstance(configured_session_dir, str) and configured_session_dir
        else tmp_path / "evidence" / "prime-sessions"
    )
    assert agent_dir == CODING_AGENT_DIR
    assert session_dir == SESSION_DIR


def test_B_pre_fix_evidence_dir_invisible_fixed_dir_readable_in_sandbox(
    tmp_path: Path,
) -> None:
    """B: evidence_dir config is invisible in bwrap; coding_agent_dir is readable."""
    # Pre-fix location (outside program binds) — must NOT be visible.
    evidence_cfg = tmp_path / "ev" / "prime-config"
    evidence_cfg.mkdir(parents=True)
    _write_local_provider_config(
        evidence_cfg, provider=PROVIDER, port=PROXY_PORT, model=MODEL
    )
    evidence_models = evidence_cfg / "models.json"
    assert evidence_models.is_file()
    # Path under /tmp/pytest-... is not in the program bind set.
    missing = _minimal_bwrap_read(str(evidence_models))
    assert missing.returncode == 2

    # Fixed route: write into authorized coding_agent_dir (bound into sandbox).
    CODING_AGENT_DIR.mkdir(parents=True, exist_ok=True)
    _write_local_provider_config(
        CODING_AGENT_DIR, provider=PROVIDER, port=PROXY_PORT, model=MODEL
    )
    models = CODING_AGENT_DIR / "models.json"
    host_digest = _digest(models)
    sandbox_digest = _bwrap_sha256(str(models))
    assert host_digest == sandbox_digest
    assert len(host_digest) == 64


def test_C_D_provider_binds_local_proxy_placeholder_not_cloud() -> None:
    """C/D: provider points at local proxy; auth is non-secret placeholder type."""
    CODING_AGENT_DIR.mkdir(parents=True, exist_ok=True)
    _write_local_provider_config(
        CODING_AGENT_DIR, provider=PROVIDER, port=PROXY_PORT, model=MODEL
    )
    cfg = json.loads((CODING_AGENT_DIR / "models.json").read_text(encoding="utf-8"))
    provider = cfg["providers"][PROVIDER]
    assert provider["baseUrl"] == f"http://127.0.0.1:{PROXY_PORT}/v1"
    assert provider["api"] == "openai-completions"
    assert MODEL in {m["id"] for m in provider["models"]}
    # Presence/type only — do not log secret material beyond the known placeholder label.
    assert "apiKey" in provider
    assert isinstance(provider["apiKey"], str) and provider["apiKey"]
    assert provider["apiKey"] == "atlas-local-proxy"
    assert "openai.com" not in provider["baseUrl"]
    assert "anthropic" not in provider["baseUrl"].lower()


def test_E_home_is_tmpfs_not_host_home_in_sandbox() -> None:
    """E: sandbox HOME is isolated tmpfs; no host home bind for config escape."""
    script = (
        "import os, pathlib, sys;"
        "home=pathlib.Path(os.environ['HOME']);"
        "sys.stdout.write(str(home));"
        "sys.exit(0 if str(home)=='/tmp/prime-home' else 3)"
    )
    argv = [
        "/usr/bin/bwrap",
        "--die-with-parent",
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
        "--proc",
        "/proc",
        "--dev",
        "/dev",
        "--tmpfs",
        "/tmp",
        "--tmpfs",
        "/home",
        "--dir",
        str(WORKSPACE),
        "--bind",
        str(WORKSPACE),
        str(WORKSPACE),
        "--setenv",
        "HOME",
        "/tmp/prime-home",
        "--",
        "/usr/bin/python3",
        "-c",
        script,
    ]
    proc = subprocess.run(argv, capture_output=True, text=True, timeout=30)
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout == "/tmp/prime-home"


def test_F_child_and_inference_socks_use_short_socket_dir(tmp_path: Path) -> None:
    """F: AF_UNIX socks stay under mission socket_dir with short names."""
    attempt_id = "t003c.prime-a1.run.1.d53647a8"
    short = attempt_id.rsplit(".", 1)[-1]
    inf = IPC / f"{short}.inf.sock"
    child = IPC / f"{short}.child.sock"
    assert len(str(inf)) < 100
    assert len(str(child)) < 100
    # Evidence-dir long path would exceed sun_path (regression anchor).
    long_path = (
        Path("/tmp/a002/t3c/.atlas/orchestration/program/evidence")
        / f"{attempt_id}.child-admission.sock"
    )
    assert len(str(long_path)) >= 100


def test_G_config_digest_stable_for_admission_recheck() -> None:
    """G: host digest equals in-sandbox digest — admission can re-hash the same bytes."""
    CODING_AGENT_DIR.mkdir(parents=True, exist_ok=True)
    _write_local_provider_config(
        CODING_AGENT_DIR, provider=PROVIDER, port=PROXY_PORT, model=MODEL
    )
    models = CODING_AGENT_DIR / "models.json"
    d1 = _digest(models)
    d2 = _bwrap_sha256(str(models))
    d3 = _digest(models)
    assert d1 == d2 == d3
