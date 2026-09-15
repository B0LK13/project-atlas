#!/usr/bin/env python3
"""Compatibility wrapper for managed-session validation."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from atlas_agent import main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(main(["validate", *sys.argv[1:]]))
