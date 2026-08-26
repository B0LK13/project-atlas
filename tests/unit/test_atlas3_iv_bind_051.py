"""AT3-051 — isolated independent-verification binding."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pytest

from project_atlas.atlas3.cli import dispatch_atlas3, register_atlas3_parsers
from project_atlas.atlas3.contracts import Atlas3Error
from project_atlas.atlas3.iv_bind import PACKAGE_ID, bind_independent_verification

HEAD = "d692cb886c67244316b354b7ae1eaf264d0304b0"
TREE = "c6d8435e3eb39f71e14ecfe1afe4e82ace451810"


def test_bind_pass_does_not_grant_merge() -> None:
    report = bind_independent_verification(
        candidate_head=HEAD,
        candidate_tree=TREE,
        observed_head=HEAD,
        observed_tree=TREE,
        iv_result="PASS",
        verifier_id="iv-linux-051",
        package_id="AT3-021",
    )
    assert report["package_id"] == PACKAGE_ID
    assert report["bound"] is True
    assert report["certified_for_merge"] is False
    assert report["merge_authorization"] == "NOT_GRANTED"
    assert report["implementer_is_verifier"] is False


def test_target_moved_fails_closed() -> None:
    moved = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    with pytest.raises(Atlas3Error) as exc:
        bind_independent_verification(
            candidate_head=HEAD,
            candidate_tree=TREE,
            observed_head=moved,
            observed_tree=TREE,
            iv_result="PASS",
            verifier_id="iv-linux-051",
            package_id="AT3-021",
        )
    assert exc.value.code == "TARGET_MOVED"


def test_self_verification_fails_closed() -> None:
    with pytest.raises(Atlas3Error) as exc:
        bind_independent_verification(
            candidate_head=HEAD,
            candidate_tree=TREE,
            observed_head=HEAD,
            observed_tree=TREE,
            iv_result="PASS",
            verifier_id="implementer",
            package_id="AT3-021",
        )
    assert exc.value.code == "IMPLEMENTER_IS_VERIFIER"


def test_failed_iv_fails_closed() -> None:
    with pytest.raises(Atlas3Error) as exc:
        bind_independent_verification(
            candidate_head=HEAD,
            candidate_tree=TREE,
            observed_head=HEAD,
            observed_tree=TREE,
            iv_result="FAIL",
            verifier_id="iv-linux-051",
            package_id="AT3-021",
        )
    assert exc.value.code == "IV_FAILED"


def test_invalid_sha_fails_closed() -> None:
    with pytest.raises(Atlas3Error) as exc:
        bind_independent_verification(
            candidate_head="not-a-sha",
            candidate_tree=TREE,
            observed_head="not-a-sha",
            observed_tree=TREE,
            iv_result="PASS",
            verifier_id="iv-linux-051",
            package_id="AT3-021",
        )
    assert exc.value.code == "IV_OBJECT_INVALID"


def test_cli_iv_bind(capsys: pytest.CaptureFixture[str]) -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command")
    register_atlas3_parsers(sub)
    args = parser.parse_args(
        [
            "iv-bind",
            "--package",
            "AT3-021",
            "--candidate-head",
            HEAD,
            "--candidate-tree",
            TREE,
            "--observed-head",
            HEAD,
            "--observed-tree",
            TREE,
            "--iv-result",
            "PASS",
            "--verifier",
            "iv-linux-051",
        ]
    )
    assert dispatch_atlas3(args) == 0
    rendered = capsys.readouterr().out
    payload = json.loads(rendered)
    assert payload["bound"] is True
    assert payload["certified_for_merge"] is False
    assert all(ord(char) < 128 for char in rendered)


def test_cli_help_is_ascii(capsys: pytest.CaptureFixture[str]) -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command")
    register_atlas3_parsers(sub)
    with pytest.raises(SystemExit) as info:
        parser.parse_args(["iv-bind", "--help"])
    assert info.value.code == 0
    help_text = capsys.readouterr().out
    assert "does not grant merge" in help_text
    assert all(ord(char) < 128 for char in help_text)


def test_module_does_not_write() -> None:
    root = Path(__file__).resolve().parents[2]
    source = (root / "src/project_atlas/atlas3/iv_bind.py").read_text(encoding="utf-8")
    for name in (
        "write_json_atomic",
        "write_text(",
        "chatgpt_bridge",
        "from project_atlas.ingestion",
    ):
        assert name not in source
