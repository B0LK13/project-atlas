from pathlib import Path


def test_windows_bootstrap_script_supports_expected_modes() -> None:
    script = Path("scripts/bootstrap-dev-tooling.ps1").read_text()
    assert "-Check" in script
    assert "-DryRun" in script
    assert "-Install" in script


def test_windows_bootstrap_script_pins_core_mcp_versions() -> None:
    script = Path("scripts/bootstrap-dev-tooling.ps1").read_text()
    assert '"codebase-memory-mcp" = "0.10.8"' in script
    assert '"@playwright/mcp" = "0.0.80"' in script
    assert '"@upstash/context7-mcp" = "4.0.5"' in script


def test_windows_bootstrap_script_avoids_plaintext_github_token() -> None:
    script = Path("scripts/bootstrap-dev-tooling.ps1").read_text()
    assert "gh auth token" not in script
    assert "GITHUB_TOKEN=" not in script
