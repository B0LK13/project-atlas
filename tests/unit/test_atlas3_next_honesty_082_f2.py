"""AT3-082-F2 — stale next-action must not compose as derived."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from project_atlas.atlas3.contracts import Atlas3Error
from project_atlas.atlas3.next_honesty import compile_next_action_honesty


def _vault(tmp_path: Path) -> Path:
    vault = tmp_path / "vault"
    (vault / "projects" / "harbor-api").mkdir(parents=True)
    return vault


def test_stale_derived_next_fails_closed(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    pulse = vault / "generated" / "ops" / "atlas3" / "pulse" / "harbor-api.json"
    pulse.parent.mkdir(parents=True)
    pulse.write_text(
        json.dumps(
            {
                "questions": {
                    "what_should_i_look_at_next": {
                        "status": "derived",
                        "freshness": "STALE",
                        "value": "stale next action",
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(Atlas3Error) as exc:
        compile_next_action_honesty(vault, "harbor-api")
    assert exc.value.code == "STALE_AS_CURRENT"


def test_fresh_derived_next_still_composes(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    pulse = vault / "generated" / "ops" / "atlas3" / "pulse" / "harbor-api.json"
    pulse.parent.mkdir(parents=True)
    pulse.write_text(
        json.dumps(
            {
                "questions": {
                    "what_should_i_look_at_next": {
                        "status": "derived",
                        "value": "look at Pulse demo",
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    report = compile_next_action_honesty(vault, "harbor-api")
    assert report["status"] == "derived"
    assert report["next"] == "look at Pulse demo"
    assert report["stale_as_current"] is False
