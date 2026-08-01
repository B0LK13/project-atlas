"""Shared fixtures for the atlas-vault-documentation test suite."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

ATLAS_ENV_VARS = (
    "ATLAS_VAULT",
    "ATLAS_SPOOL",
    "ATLAS_SPOOL_ROOT",
    "ATLAS_PROJECT_ID",
    "ATLAS_PROJECT_SLUG",
    "ATLAS_AGENT",
    "ATLAS_AGENT_ID",
    "ATLAS_AGENT_CONFIG",
    "ATLAS_SESSION_ID",
    "ATLAS_WORK_PACKAGE",
    "ATLAS_REPOSITORY",
    "ATLAS_BRANCH",
    "ATLAS_COMMIT",
    "ATLAS_STRICT",
    "ATLAS_MDA_COMMAND",
    "ATLAS_PROVIDER",
    "ATLAS_NORMALIZATION_TIMEOUT",
    "ATLAS_NORMALIZATION_RETRIES",
    "ATLAS_OUTPUT_MODE",
    "ATLAS_OUTPUT_DIR",
    "ATLAS_SKILL",
    "ATLAS_SKILL_DIR",
    "MDA_MOCK_MODE",
)

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


@pytest.fixture(autouse=True)
def clean_atlas_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Isolate every test from ambient ATLAS_* configuration."""
    for name in ATLAS_ENV_VARS:
        monkeypatch.delenv(name, raising=False)


@pytest.fixture()
def vault(tmp_path: Path) -> Path:
    root = tmp_path / "atlas-vault"
    root.mkdir()
    return root


@pytest.fixture()
def spool_repo(tmp_path: Path) -> Path:
    root = tmp_path / "repository"
    root.mkdir()
    return root
