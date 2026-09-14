"""AS-SUPERVISOR-016 install-content gate: a running installation must ship the
1.0.0 compatibility anchor resolvable by default (no repo checkout present).
Guards the packaging defect class found in REPAIR-RECORD-016 (D1)."""
from __future__ import annotations

import pytest

from project_atlas.compat_anchor import CompatAnchorError, load_compatibility_anchor


def test_packaged_compatibility_anchor_loads_by_default():
    # No explicit path: must resolve inside the installed distribution.
    anchor = load_compatibility_anchor()
    assert anchor is not None


def test_anchor_missing_raises_specific_error(tmp_path, monkeypatch):
    from project_atlas import compat_anchor

    monkeypatch.setattr(compat_anchor, "default_anchor_path", lambda: tmp_path / "nope.json")
    with pytest.raises(CompatAnchorError, match="compatibility-anchor-missing"):
        load_compatibility_anchor()
