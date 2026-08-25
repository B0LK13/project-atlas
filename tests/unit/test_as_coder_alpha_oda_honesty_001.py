"""Honesty/non-escalation for overview/decisions/attention LIVE_API.

A valid or missing authentic-looking estate must not mint owner authority,
claim AUTHENTIC_PILOT, or write Layer B / generated answers.
"""

from __future__ import annotations

import json
from pathlib import Path

from project_atlas.web_api.attention import read_project_attention_hygiene
from project_atlas.web_api.decisions import read_project_decisions
from project_atlas.web_api.overview import read_project_overview

FORBIDDEN = (
    "OWNER_GATE",
    "OWNER_CAPABILITY_GRANTED",
    "AUTHENTIC_PILOT = YES",
    "MERGE_AUTHORIZATION",
)


def _dump(payload: dict[str, object]) -> str:
    return json.dumps(payload, sort_keys=True)


def test_demo_fixture_cannot_masquerade_as_authentic_pilot() -> None:
    fixture = (
        Path(__file__).resolve().parents[1]
        / "fixtures"
        / "demo"
        / "estate"
        / "harbor-api"
    )
    if not fixture.is_dir():
        return
    for reader in (
        read_project_overview,
        read_project_decisions,
        read_project_attention_hygiene,
    ):
        report = reader(fixture, "harbor-api")
        honesty = report.get("honesty") or {}
        assert honesty.get("authentic_pilot") is False
        dumped = _dump(report)
        for token in FORBIDDEN:
            assert token not in dumped
        assert report.get("authority") in {"derived", "derived-lens"}


def test_missing_marker_does_not_widen_authority(tmp_path: Path) -> None:
    vault = tmp_path / "v"
    vault.mkdir()
    for reader in (
        read_project_overview,
        read_project_decisions,
        read_project_attention_hygiene,
    ):
        report = reader(vault, "harbor-api")
        dumped = _dump(report)
        for token in FORBIDDEN:
            assert token not in dumped
        honesty = report.get("honesty") or {}
        assert honesty.get("auto_execution") is False
        assert honesty.get("authentic_pilot") is False
        assert not (vault / "generated" / "answers").exists()
        assert not (vault / "projects").exists() or not any(
            (vault / "projects").rglob("*")
        )


def test_malformed_project_id_does_not_write(tmp_path: Path) -> None:
    vault = tmp_path / "v"
    vault.mkdir()
    before = list(vault.rglob("*"))
    for reader in (
        read_project_overview,
        read_project_decisions,
        read_project_attention_hygiene,
    ):
        try:
            reader(vault, "../escape")
        except ValueError as exc:
            assert getattr(exc, "honesty", "") == "MALFORMED_INPUT"
    after = list(vault.rglob("*"))
    assert after == before
