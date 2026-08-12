"""Test plumbing for the isolated ChatGPT read-only MCP integration.

The gateway/server modules (``atlas_gateway``, ``server``) live in this
directory, not on the installed package path. Production usage puts this
directory on ``PYTHONPATH`` (see README). For pytest we insert it here so the
test modules import the same modules without relying on an external
``PYTHONPATH`` being set. No production behavior is affected.
"""

from __future__ import annotations

import sys
from pathlib import Path

_INTEGRATION_DIR = str(Path(__file__).resolve().parent)
if _INTEGRATION_DIR not in sys.path:
    sys.path.insert(0, _INTEGRATION_DIR)
