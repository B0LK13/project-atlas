"""Contain yaml.safe_load constructor KeyError in event-package receipts.

The Event Ledger / event-package boundary treats ``receipt.yaml`` as
evidence substrate. PyYAML ``!!bool nope`` raises a bare ``KeyError``,
not ``yaml.YAMLError``. On live main ``b87b4a22`` that escaped
``_load_receipt`` instead of ``PackageValidationError``.

This package does not widen acceptance. Does not touch ``ingestion.py``.
Sibling of #819 / #820 / #822 / #823 / #824.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from atlas_contracts.event_package import PackageValidationError, _load_receipt

MALFORMED = "atlas: !!bool nope\n"


def test_load_receipt_constructor_tag_is_package_validation_error(tmp_path: Path) -> None:
    (tmp_path / "receipt.yaml").write_text(MALFORMED, encoding="utf-8")
    with pytest.raises(PackageValidationError, match=r"receipt\.yaml invalid"):
        _load_receipt(tmp_path)


def test_load_receipt_valid_mapping_still_loads(tmp_path: Path) -> None:
    (tmp_path / "receipt.yaml").write_text(
        "receipt_id: rec-1\nstatus: valid\nevent_id: evt-1\n",
        encoding="utf-8",
    )
    receipt = _load_receipt(tmp_path)
    assert receipt.receipt_id == "rec-1"
    assert receipt.status == "valid"
    assert receipt.event_id == "evt-1"
