from __future__ import annotations

from pathlib import Path

import pytest

from estate import build_fixture_estate


@pytest.fixture(scope="session")
def fixture_estate(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return build_fixture_estate(tmp_path_factory.mktemp("estate"))
