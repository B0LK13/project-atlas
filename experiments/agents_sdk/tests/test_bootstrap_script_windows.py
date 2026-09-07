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


def test_windows_health_script_is_read_only_report() -> None:
    script = Path("scripts/check-windows-dev-health.ps1").read_text()
    assert "ConvertTo-Json" in script
    assert "gh auth status" in script
    assert "gh auth token" not in script
