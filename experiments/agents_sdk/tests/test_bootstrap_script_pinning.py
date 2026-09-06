from pathlib import Path


def test_bootstrap_script_does_not_use_latest_release_resolution() -> None:
    script = Path("scripts/bootstrap-dev-tooling.sh").read_text()
    assert "/releases/latest" not in script
    assert "@latest" not in script


def test_bootstrap_script_pins_versions_for_all_install_targets() -> None:
    script = Path("scripts/bootstrap-dev-tooling.sh").read_text()
    expected_markers = [
        "PLAYWRIGHT_MCP_VERSION=",
        "CONTEXT7_MCP_VERSION=",
        "MARKDOWNLINT_CLI2_VERSION=",
        "GITLEAKS_VERSION=",
        "TRIVY_VERSION=",
        "SYFT_VERSION=",
        "GRYPE_VERSION=",
        "TAPLO_VERSION=",
        "ACTIONLINT_VERSION=",
    ]
    for marker in expected_markers:
        assert marker in script


def test_bootstrap_script_verifies_taplo_download_checksum() -> None:
    script = Path("scripts/bootstrap-dev-tooling.sh").read_text()
    assert "taplo_SHA256" in script
