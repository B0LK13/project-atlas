"""AT3-CLI-F1 — memory CLI consume path must not treat corrupt reconcile as absent.

`read_json` returns None for both a missing file and a present-but-corrupt
file. `atlas memory status` then reported `reconcile_present: false` with
exit 0, and honesty/search compiled an empty healthy projection.

Missing still stays missing. Existing corruption fails closed as
`RECONCILE_CORRUPT`. A string `reconciliation` block no longer leaks
`AttributeError`.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from project_atlas.atlas3.cli import load_reconcile_artifact, load_reconcile_items
from project_atlas.atlas3.contracts import Atlas3Error
from project_atlas.cli import EXIT_ERROR, EXIT_OK, main


def _vault(tmp_path: Path) -> Path:
    vault = tmp_path / "vault"
    (vault / "projects" / "harbor-api").mkdir(parents=True)
    return vault


def _mem(vault: Path, *parts: str) -> list[str]:
    return ["memory", *parts, "--vault", str(vault), "--project", "harbor-api"]


def _write_reconcile(vault: Path, payload: object) -> Path:
    path = vault / "generated" / "ops" / "atlas3" / "memory" / "harbor-api" / "reconcile.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(payload, str):
        path.write_text(payload, encoding="utf-8")
    else:
        path.write_text(json.dumps(payload) + "\n", encoding="utf-8")
    return path


def test_missing_reconcile_is_absent_not_corrupt(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    assert load_reconcile_artifact(vault, "harbor-api") is None
    assert load_reconcile_items(vault, "harbor-api") == []
    assert main(_mem(vault, "status")) == EXIT_OK
    assert main(_mem(vault, "honesty")) == EXIT_OK


def test_corrupt_json_fails_closed_instead_of_reporting_absent(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    vault = _vault(tmp_path)
    _write_reconcile(vault, "{not-json\n")
    with pytest.raises(Atlas3Error) as exc:
        load_reconcile_artifact(vault, "harbor-api")
    assert exc.value.code == "RECONCILE_CORRUPT"
    assert main(_mem(vault, "status")) == EXIT_ERROR
    payload = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert payload["ok"] is False
    assert payload["error"] == "RECONCILE_CORRUPT"
    assert main(_mem(vault, "honesty")) == EXIT_ERROR


def test_non_object_root_fails_closed(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    _write_reconcile(vault, [1, 2])
    with pytest.raises(Atlas3Error) as exc:
        load_reconcile_artifact(vault, "harbor-api")
    assert exc.value.code == "RECONCILE_CORRUPT"
    assert main(_mem(vault, "status")) == EXIT_ERROR


def test_string_reconciliation_fails_closed_not_attribute_error(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    _write_reconcile(vault, {"reconciliation": "nope"})
    with pytest.raises(Atlas3Error) as exc:
        load_reconcile_items(vault, "harbor-api")
    assert exc.value.code == "RECONCILE_CORRUPT"
    assert main(_mem(vault, "honesty")) == EXIT_ERROR


def test_non_list_items_fails_closed(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    _write_reconcile(vault, {"reconciliation": {"items": "nope"}})
    with pytest.raises(Atlas3Error) as exc:
        load_reconcile_items(vault, "harbor-api")
    assert exc.value.code == "RECONCILE_CORRUPT"


def test_valid_reconcile_still_present(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    vault = _vault(tmp_path)
    _write_reconcile(
        vault,
        {
            "reconciliation": {
                "items": [
                    {
                        "project_id": "harbor-api",
                        "provider": "chatgpt",
                        "text": "PostgreSQL 16 is deployed",
                    }
                ]
            }
        },
    )
    recon = load_reconcile_artifact(vault, "harbor-api")
    assert recon is not None
    items = load_reconcile_items(vault, "harbor-api")
    assert len(items) == 1
    assert main(_mem(vault, "status")) == EXIT_OK
    payload = json.loads(capsys.readouterr().out)
    assert payload["reconcile_present"] is True
    assert main(_mem(vault, "honesty")) == EXIT_OK
