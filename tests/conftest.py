"""Shared pytest hooks. Do not leak test MDA injection across cases."""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from project_atlas.agent_control.runtime import clear_test_mda_provider


@pytest.fixture(autouse=True)
def _reset_test_mda_provider() -> Iterator[None]:
    yield
    clear_test_mda_provider()
