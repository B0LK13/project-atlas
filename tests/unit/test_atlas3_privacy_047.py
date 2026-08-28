"""AT3-047 — Privacy / secret gate."""

from __future__ import annotations

from pathlib import Path

import pytest

from project_atlas.atlas3.contracts import Atlas3Error
from project_atlas.atlas3.memory.privacy import (
    PACKAGE_ID,
    apply_privacy,
    privacy_defaults,
    scan_or_raise,
)


def test_defaults_minimize_transcript() -> None:
    defaults = privacy_defaults()
    assert defaults["package"] == PACKAGE_ID
    assert defaults["raw_full_transcript_retention"] == "MINIMIZED"
    assert defaults["secret_persistence"] is False
    assert defaults["automatic_canonical_promotion"] is False
    assert defaults["default_network_access"] is False


def test_secret_shaped_content_fails_closed() -> None:
    with pytest.raises(Atlas3Error) as exc:
        apply_privacy("aws_secret_access_key=AKIAAAAAAAAAAAAAAAAA")
    assert exc.value.code == "SECRET_CONTENT"
    with pytest.raises(Atlas3Error) as exc:
        scan_or_raise("token AKIAAAAAAAAAAAAAAAAA")
    assert exc.value.code == "SECRET_CONTENT"


def test_unknown_privacy_class_fails_closed() -> None:
    with pytest.raises(Atlas3Error) as exc:
        apply_privacy("hello", privacy_class="publish")
    assert exc.value.code == "UNKNOWN_PRIVACY_CLASS"


def test_exclude_fails_closed() -> None:
    with pytest.raises(Atlas3Error) as exc:
        apply_privacy("hello", privacy_class="exclude")
    assert exc.value.code == "PRIVACY_EXCLUDE"


def test_redact_does_not_persist_raw() -> None:
    assert apply_privacy("hello", privacy_class="redact") == "[REDACTED]"


def test_module_does_not_touch_2x_bridges() -> None:
    root = Path(__file__).resolve().parents[2]
    source = (root / "src/project_atlas/atlas3/memory/privacy.py").read_text(encoding="utf-8")
    for name in (
        "from project_atlas.chatgpt_bridge",
        "from project_atlas.knowledge_compiler",
        "write_text(",
    ):
        assert name not in source
