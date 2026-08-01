"""Version and identifier rules for the cross-track contracts."""

from __future__ import annotations

import re

CONTRACT_SCHEMA_VERSION = 1
ID_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9._-]*$"
EVENT_ID_PATTERN = r"^AE-[A-Za-z0-9._:-]+$"
HASH_PATTERN = r"^[0-9a-f]{64}$"
HASH_RE = re.compile(HASH_PATTERN)
