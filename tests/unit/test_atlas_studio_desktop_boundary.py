from __future__ import annotations

import importlib.util
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
STUDIO_ROOT = REPO_ROOT / "apps" / "studio"
BRIDGE_PATH = STUDIO_ROOT / "bridge" / "atlas_studio_bridge.py"


def _bridge_module():
    spec = importlib.util.spec_from_file_location("atlas_studio_bridge", BRIDGE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_desktop_shell_registers_no_native_command_or_shell_plugin() -> None:
    rust = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (STUDIO_ROOT / "src-tauri" / "src").rglob("*.rs")
    )
    cargo = (STUDIO_ROOT / "src-tauri" / "Cargo.toml").read_text(encoding="utf-8")
    capability = json.loads(
        (STUDIO_ROOT / "src-tauri" / "capabilities" / "default.json").read_text(
            encoding="utf-8"
        )
    )

    assert "invoke_handler" not in rust
    assert "Command::new" not in rust
    assert "tauri-plugin-shell" not in cargo
    assert "tauri-plugin-fs" not in cargo
    assert capability["permissions"] == ["core:default"]


def test_bridge_exposes_only_read_methods_and_fixed_repository_input() -> None:
    bridge = BRIDGE_PATH.read_text(encoding="utf-8")
    assert "def do_GET" in bridge
    assert "def do_OPTIONS" in bridge
    for mutation in ("do_POST", "do_PUT", "do_PATCH", "do_DELETE"):
        assert mutation not in bridge
    assert 'default="B0LK13/project-atlas"' in bridge
    assert "shell=True" not in bridge
    assert "subprocess" not in bridge


def test_bridge_fails_closed_before_building_projection(monkeypatch) -> None:
    bridge = _bridge_module()
    monkeypatch.setattr(
        bridge,
        "github_read_available",
        lambda repository: (False, "GITHUB_READ_UNAVAILABLE"),
    )

    try:
        bridge.build_current_projection("B0LK13/project-atlas", None)
    except RuntimeError as exc:
        assert str(exc) == "GITHUB_READ_UNAVAILABLE"
    else:
        raise AssertionError("unavailable GitHub state must fail closed")
