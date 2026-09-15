"""AS-2.1-OPS-RECEIPT-ADAPTER — honest UNKNOWN inventory tests."""

from __future__ import annotations

import json
import threading
from pathlib import Path
from urllib.request import Request, urlopen

import pytest

from project_atlas.api_server import serve_api, session_credentials
from project_atlas.obs_live import build_live_observability_receipt
from project_atlas.ops_receipts import (
    LEGACY_PACKAGE_ID,
    PACKAGE_ID,
    inventory_ops_receipts,
)


def test_package_id_and_legacy_alias() -> None:
    assert PACKAGE_ID == "AS-2.1-OPS-RECEIPT-ADAPTER"
    assert LEGACY_PACKAGE_ID == "AS-2.1-OBS-RECEIPTS-001"


def test_ops_receipts_honest_empty_unknown(tmp_path: Path) -> None:
    vault = tmp_path / "v"
    vault.mkdir()
    inv = inventory_ops_receipts(vault)
    assert inv["package_id"] == PACKAGE_ID
    assert inv["legacy_package_id"] == LEGACY_PACKAGE_ID
    assert inv["available"] is False
    assert inv["receipt_source"] == "unavailable"
    assert inv["ops_root"] == "absent"
    assert inv["receipt_rows"] == 0
    assert inv["receipts"] == []
    assert inv["completion_claimed"] is False
    assert inv["rollup"] == "unknown"
    assert inv["health"] == "unknown"
    assert inv["unknown_equals_healthy"] is False
    assert inv["authentic_pilot"] is False
    assert inv["release_certified"] is False
    assert inv["authority"] is False
    assert inv["ui_canonical"] is False
    assert inv["truncated"] is False
    assert inv["kinds"]["obs"] == "absent"
    assert inv["kinds"]["pilot"] == "absent"
    assert "UNKNOWN!=HEALTHY" in inv["truth_boundary"]


def test_ops_receipts_presence_never_upgrades_rollup(tmp_path: Path) -> None:
    vault = tmp_path / "v"
    vault.mkdir()
    build_live_observability_receipt(vault, receipt_id="r1")
    # Plant a receipt that *claims* healthy — must not promote.
    fake = vault / "generated" / "ops" / "scheduler"
    fake.mkdir(parents=True, exist_ok=True)
    (fake / "claimed-healthy.json").write_text(
        json.dumps(
            {
                "package_id": "AS-FAKE-HEALTHY",
                "rollup": "healthy",
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )
    inv = inventory_ops_receipts(vault)
    assert inv["available"] is True
    assert inv["ops_root"] == "present"
    assert inv["receipt_rows"] >= 2
    assert inv["rollup"] == "unknown"
    assert inv["health"] == "unknown"
    assert inv["unknown_equals_healthy"] is False
    assert inv["completion_claimed"] is False
    claimed = next(r for r in inv["receipts"] if r["name"] == "claimed-healthy.json")
    assert claimed["health"] == "unknown"
    assert claimed.get("embedded_rollup") == "healthy"
    assert claimed.get("embedded_rollup_promoted") is False
    assert inv["kinds"]["obs"] == "present"
    assert inv["kinds"]["scheduler"] == "present"
    assert inv["kinds"]["pilot"] == "absent"


def test_ops_receipts_malformed_json_stays_unknown(tmp_path: Path) -> None:
    vault = tmp_path / "v"
    vault.mkdir()
    bad_dir = vault / "generated" / "ops" / "obs"
    bad_dir.mkdir(parents=True)
    (bad_dir / "broken.json").write_text("{not-json", encoding="utf-8")
    inv = inventory_ops_receipts(vault)
    assert inv["available"] is True
    assert inv["rollup"] == "unknown"
    assert inv["health"] == "unknown"
    row = inv["receipts"][0]
    assert row["parse"] == "unknown"
    assert row["health"] == "unknown"


def test_ops_receipts_unscanned_kinds_honest(tmp_path: Path) -> None:
    vault = tmp_path / "v"
    vault.mkdir()
    extra = vault / "generated" / "ops" / "future-plane"
    extra.mkdir(parents=True)
    (extra / "x.json").write_text("{}\n", encoding="utf-8")
    inv = inventory_ops_receipts(vault)
    assert "future-plane" in inv["unscanned_kinds"]
    assert inv["rollup"] == "unknown"
    # Unscanned content must not silently count as inventoried receipts.
    assert all(r["kind"] != "future-plane" for r in inv["receipts"])


def test_ops_receipts_limit_truncation(tmp_path: Path) -> None:
    vault = tmp_path / "v"
    vault.mkdir()
    obs = vault / "generated" / "ops" / "obs"
    obs.mkdir(parents=True)
    for i in range(5):
        (obs / f"r{i}.json").write_text("{}\n", encoding="utf-8")
    inv = inventory_ops_receipts(vault, limit=2)
    assert inv["receipt_rows"] == 2
    assert inv["truncated"] is True
    assert inv["limit"] == 2
    assert inv["rollup"] == "unknown"


def test_ops_receipts_limit_out_of_range(tmp_path: Path) -> None:
    vault = tmp_path / "v"
    vault.mkdir()
    with pytest.raises(ValueError, match="ops-receipt-limit-out-of-range"):
        inventory_ops_receipts(vault, limit=0)
    with pytest.raises(ValueError, match="ops-receipt-limit-out-of-range"):
        inventory_ops_receipts(vault, limit=501)


def test_api_ops_receipts_route_honest_unknown(tmp_path: Path) -> None:
    vault = tmp_path / "v"
    vault.mkdir()
    server = serve_api(vault, host="127.0.0.1", port=0)
    host, port = server.server_address[:2]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        auth = session_credentials(server).auth_headers()
        with urlopen(Request(f"http://{host}:{port}/v1/meta", headers=auth), timeout=2) as resp:
            meta = json.loads(resp.read().decode("utf-8"))
        assert meta["ops_receipts"] is True
        with urlopen(
            Request(f"http://{host}:{port}/v1/ops/receipts", headers=auth), timeout=2
        ) as resp:
            inv = json.loads(resp.read().decode("utf-8"))
        assert inv["package_id"] == PACKAGE_ID
        assert inv["completion_claimed"] is False
        assert inv["rollup"] == "unknown"
        assert inv["health"] == "unknown"
        assert inv["unknown_equals_healthy"] is False
        assert inv["authentic_pilot"] is False
        assert inv["release_certified"] is False
    finally:
        server.shutdown()
