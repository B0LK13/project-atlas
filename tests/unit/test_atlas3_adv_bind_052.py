"""AT3-052 — isolated ADV binding."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pytest

from project_atlas.atlas3.adv_bind import PACKAGE_ID, bind_adversarial_result
from project_atlas.atlas3.cli import dispatch_atlas3, register_atlas3_parsers
from project_atlas.atlas3.contracts import Atlas3Error

HEAD = "029dd8673ad351f6c39ea377bdbb113c9196295f"
TREE = "911b329ce7263843973473278f2897acf95d2a4d"


def test_bind_pass_does_not_grant_merge_or_security() -> None:
    report = bind_adversarial_result(
        candidate_head=HEAD,
        candidate_tree=TREE,
        observed_head=HEAD,
        observed_tree=TREE,
        adv_result="PASS",
        adv_id="adv-linux-052",
        package_id="AT3-051",
    )
    assert report["package_id"] == PACKAGE_ID
    assert report["bound"] is True
    assert report["certified_for_merge"] is False
    assert report["security_certification"] is False
    assert report["external_security_revalidation_required"] is True
    assert report["merge_authorization"] == "NOT_GRANTED"


def test_target_moved_fails_closed() -> None:
    moved = "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
    with pytest.raises(Atlas3Error) as exc:
        bind_adversarial_result(
            candidate_head=HEAD,
            candidate_tree=TREE,
            observed_head=moved,
            observed_tree=TREE,
            adv_result="PASS",
            adv_id="adv-linux-052",
            package_id="AT3-051",
        )
    assert exc.value.code == "TARGET_MOVED"


def test_self_adv_fails_closed() -> None:
    with pytest.raises(Atlas3Error) as exc:
        bind_adversarial_result(
            candidate_head=HEAD,
            candidate_tree=TREE,
            observed_head=HEAD,
            observed_tree=TREE,
            adv_result="PASS",
            adv_id="implementer",
            package_id="AT3-051",
        )
    assert exc.value.code == "IMPLEMENTER_IS_ADV"


def test_failed_adv_fails_closed() -> None:
    with pytest.raises(Atlas3Error) as exc:
        bind_adversarial_result(
            candidate_head=HEAD,
            candidate_tree=TREE,
            observed_head=HEAD,
            observed_tree=TREE,
            adv_result="FAIL",
            adv_id="adv-linux-052",
            package_id="AT3-051",
        )
    assert exc.value.code == "ADV_FAILED"


def test_cli_adv_bind(capsys: pytest.CaptureFixture[str]) -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command")
    register_atlas3_parsers(sub)
    args = parser.parse_args(
        [
            "adv-bind",
            "--package",
            "AT3-051",
            "--candidate-head",
            HEAD,
            "--candidate-tree",
            TREE,
            "--observed-head",
            HEAD,
            "--observed-tree",
            TREE,
            "--adv-result",
            "PASS",
            "--adv-id",
            "adv-linux-052",
        ]
    )
    assert dispatch_atlas3(args) == 0
    rendered = capsys.readouterr().out
    payload = json.loads(rendered)
    assert payload["bound"] is True
    assert payload["security_certification"] is False
    assert all(ord(char) < 128 for char in rendered)


def test_cli_help_is_ascii(capsys: pytest.CaptureFixture[str]) -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command")
    register_atlas3_parsers(sub)
    with pytest.raises(SystemExit) as info:
        parser.parse_args(["adv-bind", "--help"])
    assert info.value.code == 0
    help_text = capsys.readouterr().out
    assert "does not grant merge" in help_text
    assert all(ord(char) < 128 for char in help_text)


def test_module_does_not_write() -> None:
    root = Path(__file__).resolve().parents[2]
    source = (root / "src/project_atlas/atlas3/adv_bind.py").read_text(encoding="utf-8")
    for name in (
        "write_json_atomic",
        "write_text(",
        "chatgpt_bridge",
        "from project_atlas.ingestion",
    ):
        assert name not in source
