"""AS-SEC-SCAN-OBSIDIAN-CAPTURE-RETRY-JSON-ESC-001 — decoded capture scalars must not persist.

``retry`` reloads ``generated/ops/raw-captures/rcap-*.json`` via
``json.loads`` and ``_persist_record`` rewrites it. A JSON
``\\u0041KI…`` escape does not match ``scan_text`` on raw bytes, but
decode reveals ``AKIAAAAAAAAAAAAAAAAA`` (NFR-004 / AT-014).

Synthetic token only. Distinct from #977 (living-note interpolation),
#988 (conversation-capture review rewrite), and listed P2 session_capture.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from project_atlas.capture_sources import build_capture_request
from project_atlas.obsidian_capture import CAPTURE_DIR, CaptureError, capture, retry
from project_atlas.secrets import scan_text

TOKEN = "AKIAAAAAAAAAAAAAAAAA"
ESC = r"\u0041KIAAAAAAAAAAAAAAAAA"


@pytest.fixture
def vault(tmp_path: Path) -> Path:
    root = tmp_path / "vault"
    (root / "projects" / "harbor-api").mkdir(parents=True)
    (root / "generated").mkdir()
    return root


def test_retry_refuses_json_escaped_title(vault: Path) -> None:
    result = capture(
        vault,
        build_capture_request(content="hello capture", title_hint="safe-title"),
        render=False,
    )
    path = vault / CAPTURE_DIR / f"{result['capture_id']}.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["title"] = "PLACEHOLDER"
    planted = json.dumps(data, indent=2, sort_keys=True).replace("PLACEHOLDER", ESC) + "\n"
    path.write_text(planted, encoding="utf-8")
    assert TOKEN not in planted
    assert scan_text(planted) == []
    assert json.loads(planted)["title"] == TOKEN

    with pytest.raises(CaptureError) as exc:
        retry(vault, result["capture_id"])
    assert exc.value.code == "SECRET_CONTENT"
    after = path.read_text(encoding="utf-8")
    assert TOKEN not in after
    assert scan_text(after) == []


def test_safe_retry_still_persists(vault: Path) -> None:
    result = capture(
        vault,
        build_capture_request(content="hello capture", title_hint="safe-title"),
        render=False,
    )
    resumed = retry(vault, result["capture_id"])
    assert resumed["capture_id"] == result["capture_id"]
    path = vault / CAPTURE_DIR / f"{result['capture_id']}.json"
    written = path.read_text(encoding="utf-8")
    assert TOKEN not in written
    assert scan_text(written) == []
