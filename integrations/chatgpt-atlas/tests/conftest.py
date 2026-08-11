"""Shared fixtures: build a real DEMO_FIXTURE vault via the production pipeline.

Reuses the actual ``atlas`` CLI (init -> discover -> ingest -> build-indexes ->
build-portfolio) so the gateway is tested against genuine Atlas output, not a
hand-crafted stub. DEMO_FIXTURE only; no authentic pilot.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from project_atlas.cli import main

REPO_ROOT = Path(__file__).resolve().parents[3]
DEMO_ESTATE = REPO_ROOT / "tests" / "fixtures" / "demo" / "estate"


@pytest.fixture(scope="session")
def demo_vault(tmp_path_factory: pytest.TempPathFactory) -> Path:
    base = tmp_path_factory.mktemp("chatgpt-atlas-demo")
    vault = base / "vault"
    manifest = base / "manifest.json"
    assert DEMO_ESTATE.is_dir(), f"missing DEMO_FIXTURE estate: {DEMO_ESTATE}"
    assert main(["init", "--output", str(vault)]) == 0
    assert main(["discover", "--source", str(DEMO_ESTATE), "--output", str(manifest)]) == 0
    assert main(["ingest", "--manifest", str(manifest), "--vault", str(vault)]) == 0
    assert main(["build-indexes", "--vault", str(vault)]) == 0
    assert main(["build-portfolio", "--vault", str(vault)]) == 0
    return vault
