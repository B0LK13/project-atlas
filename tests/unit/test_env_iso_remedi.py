"""ADVANCE-005 ENV-ISO-001/002 remedi contracts (Windows tip isolation).

PRODUCTIZATION / NOT RELEASE / NOT PILOT.
EXTERNAL_SECURITY_REVALIDATION_REQUIRED=YES
CODEX_VALIDATED=NO
"""

from __future__ import annotations

from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCRIPTS = _REPO_ROOT / "scripts" / "windows"
_COMMON = _SCRIPTS / "_AtlasCommon.ps1"
_START = _SCRIPTS / "atlas-start.ps1"
_PREFLIGHT = _SCRIPTS / "atlas-preflight.ps1"
_PS_TEST = _SCRIPTS / "tests" / "Test-EnvIsolation.ps1"


def test_env_iso_helpers_present_in_common() -> None:
    text = _COMMON.read_text(encoding="utf-8")
    for token in (
        "function Get-AtlasTipVenvPythonPath",
        "function Get-AtlasPythonCommand",
        "function Test-AtlasInterpreterIsTipVenv",
        "function Resolve-AtlasScriptsDir",
        "function Test-AtlasPythonPathTipSafe",
        "function Test-AtlasImportLocationTipSafe",
        "function Test-AtlasPathUnderRoot",
        "pythonpath_foreign_shadow",
        "import_wrong_worktree",
        ".venv\\Scripts\\python.exe",
        "TipLocal",
    ):
        assert token in text, f"_AtlasCommon.ps1 missing {token!r}"


def test_env_iso_start_refuses_global_editable_rewrite() -> None:
    text = _START.read_text(encoding="utf-8")
    assert "Ensure-AtlasTipLocalVenv" in text
    assert "Refusing editable install into a non-tip interpreter" in text
    assert "ENV-ISO-002 fail-closed" in text
    assert "ENV-ISO-001 fail-closed" in text
    assert "no global editable rewrite" in text
    assert "Test-AtlasPythonPathTipSafe" in text
    assert "Test-AtlasImportLocationTipSafe" in text
    # Repair path must target tip .venv, not shared global Scripts.
    assert "will install into tip .venv only" in text
    assert "Will reinstall editable package into tip .venv" in text


def test_env_iso_python_selection_prefers_tip_venv() -> None:
    start = _START.read_text(encoding="utf-8")
    common = _COMMON.read_text(encoding="utf-8")
    preflight = _PREFLIGHT.read_text(encoding="utf-8")
    assert "Get-AtlasPythonCommand -RepoRoot" in start
    assert "Get-AtlasPythonCommand -RepoRoot" in preflight
    assert "Get-AtlasTipVenvPythonPath" in common
    assert "tip-venv" in common
    # Prefer tip path before py -3.12 fallback.
    tip_idx = common.index("Get-AtlasTipVenvPythonPath")
    py_idx = common.index('Label    = "py -3.12"')
    assert tip_idx < py_idx


def test_env_iso_scripts_dir_venv_aware() -> None:
    """Avoid Scripts\\Scripts when sys.executable already lives under Scripts."""
    text = _COMMON.read_text(encoding="utf-8")
    assert "function Resolve-AtlasScriptsDir" in text
    assert 'Equals("Scripts"' in text
    assert 'Equals("bin"' in text
    assert "do not" in text.lower() or "already lives" in text
    # Old sole implementation must not remain only in atlas-start.
    assert "function Resolve-AtlasScriptsDir" not in _START.read_text(encoding="utf-8")


def test_env_iso_powershell_selftest_present() -> None:
    assert _PS_TEST.is_file(), f"missing {_PS_TEST}"
    text = _PS_TEST.read_text(encoding="utf-8")
    assert "ENV-ISO" in text
    assert "Test-AtlasPythonPathTipSafe" in text
    assert "Resolve-AtlasScriptsDir" in text
    assert "EXTERNAL_SECURITY_REVALIDATION_REQUIRED=YES" in text
    assert "CODEX_VALIDATED=NO" in text
