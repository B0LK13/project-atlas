"""Contain json.loads JSONDecodeError in fail-closed control-plane readers.

Corrupt vault identity, authority grants, session files, and receipts must
raise structured ValueError or collect structured errors. On live main
``b87b4a22`` those four readers leaked ``json.JSONDecodeError``.

Does not authorize grants or sessions. Does not touch Core ``ingestion.py``.
Sibling of CTRL-YAML-CONSTRUCTOR-KEYERROR / #827 (parse fail-closed; JSON).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from agent_control import authority, repository_gate, session, vault_identity

BAD = "{not json"


def test_vault_identity_malformed_json_is_invalid(tmp_path: Path) -> None:
    (tmp_path / ".atlas").mkdir()
    (tmp_path / ".atlas" / "vault.json").write_text(BAD, encoding="utf-8")
    with pytest.raises(ValueError, match="invalid Atlas Vault identity"):
        vault_identity.read(tmp_path)


def test_load_grant_malformed_json_is_malformed(tmp_path: Path) -> None:
    path = tmp_path / "grant.json"
    path.write_text(BAD, encoding="utf-8")
    with pytest.raises(ValueError, match="authority grant is malformed"):
        authority.load_grant(path)


def test_revoke_grant_malformed_json_is_malformed(tmp_path: Path) -> None:
    store = tmp_path / "store"
    (store / "grants").mkdir(parents=True)
    (store / "grants" / "g1.json").write_text(BAD, encoding="utf-8")
    with pytest.raises(ValueError, match="authority grant is malformed"):
        authority.revoke_grant(store=store, grant_id="g1", issuer_key="a" * 32)


def test_session_load_malformed_json_is_unreadable(tmp_path: Path) -> None:
    (tmp_path / ".atlas" / "sessions").mkdir(parents=True)
    (tmp_path / ".atlas" / "sessions" / "s1.json").write_text(BAD, encoding="utf-8")
    with pytest.raises(ValueError, match="session is unreadable"):
        session.load(tmp_path, "s1")


def test_repository_gate_malformed_receipt_is_unreadable(tmp_path: Path) -> None:
    receipt = tmp_path / "receipt.json"
    receipt.write_text(BAD, encoding="utf-8")
    report = repository_gate.validate(
        project_id="fixture",
        changed_files=["docs/a.md"],
        receipt_path=receipt,
    )
    assert report["ok"] is False
    assert "receipt is unreadable" in report["errors"]


@pytest.mark.parametrize(
    "body",
    ("null", "[1]", "true", "1", '"x"'),
)
def test_repository_gate_non_object_receipt_is_malformed(tmp_path: Path, body: str) -> None:
    """JSON null/array/bool/number/string must fail closed without AttributeError.

    #828 IV (3427d76c): ``null`` parsed as None and skipped both error arms,
    so validate returned ok=True. Truthy non-dicts then crashed on .get.
    """
    receipt = tmp_path / "receipt.json"
    receipt.write_text(body, encoding="utf-8")
    report = repository_gate.validate(
        project_id="fixture",
        changed_files=["docs/a.md"],
        receipt_path=receipt,
    )
    assert report["ok"] is False
    assert "receipt is malformed" in report["errors"]
    assert "receipt is unreadable" not in report["errors"]
    assert report["receipt_id"] is None
