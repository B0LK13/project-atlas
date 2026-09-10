"""Point-in-time JSON snapshot loading for Studio continuity paths.

INPUT_BYTE_HASH identifies the exact bytes parsed.
PARSE_FROM_SAME_BYTES = required (no second disk read between hash and parse).
MISSING / CORRUPT / NOT_OBJECT are explicit — never silent success.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


MISSING = "MISSING"
CORRUPT_JSON = "CORRUPT_JSON"
NOT_OBJECT = "NOT_OBJECT"
EMPTY = "EMPTY"
READ_ERROR = "READ_ERROR"


@dataclass(frozen=True)
class JsonSnapshot:
    """One atomic read → hash → parse cycle."""

    path: str | None
    data: dict[str, Any] | None
    raw_sha256: str | None
    error: str | None
    byte_length: int | None = None

    @property
    def ok(self) -> bool:
        return self.error is None and isinstance(self.data, dict)


def load_json_snapshot(path: Path | str | None) -> JsonSnapshot:
    """Read file bytes once; hash those bytes; parse the same buffer."""
    if path is None:
        return JsonSnapshot(path=None, data=None, raw_sha256=None, error=MISSING)
    p = Path(path)
    if not p.is_file():
        return JsonSnapshot(path=str(p), data=None, raw_sha256=None, error=MISSING)
    try:
        raw = p.read_bytes()
    except OSError:
        return JsonSnapshot(path=str(p), data=None, raw_sha256=None, error=READ_ERROR)
    digest = hashlib.sha256(raw).hexdigest()
    if len(raw) == 0:
        return JsonSnapshot(
            path=str(p),
            data=None,
            raw_sha256=digest,
            error=EMPTY,
            byte_length=0,
        )
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        return JsonSnapshot(
            path=str(p),
            data=None,
            raw_sha256=digest,
            error=CORRUPT_JSON,
            byte_length=len(raw),
        )
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return JsonSnapshot(
            path=str(p),
            data=None,
            raw_sha256=digest,
            error=CORRUPT_JSON,
            byte_length=len(raw),
        )
    if not isinstance(data, dict):
        return JsonSnapshot(
            path=str(p),
            data=None,
            raw_sha256=digest,
            error=NOT_OBJECT,
            byte_length=len(raw),
        )
    return JsonSnapshot(
        path=str(p),
        data=data,
        raw_sha256=digest,
        error=None,
        byte_length=len(raw),
    )


def snapshot_from_object(
    data: dict[str, Any] | None, *, label: str = "injected"
) -> JsonSnapshot:
    """Hash canonical encoding of an already-in-memory object (injected fixtures)."""
    if data is None:
        return JsonSnapshot(path=label, data=None, raw_sha256=None, error=MISSING)
    if not isinstance(data, dict):
        return JsonSnapshot(path=label, data=None, raw_sha256=None, error=NOT_OBJECT)
    raw = json.dumps(data, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return JsonSnapshot(
        path=label,
        data=data,
        raw_sha256=hashlib.sha256(raw).hexdigest(),
        error=None,
        byte_length=len(raw),
    )
