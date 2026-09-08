"""AT3-103 — one canonical JSON serialization and content digest for Atlas contracts.

Identity, not authority: a digest binds a payload to itself. It never grants
merge, owner, or verification authority.

Canonical form (deliberately minimal; NOT a claim of RFC 8785 compliance):

- keys sorted by Unicode code point (``sort_keys=True``);
- separators ``(",", ":")`` — no whitespace;
- ``ensure_ascii=True`` — every non-ASCII code point is escaped as ``\\uXXXX``
  (UTF-16 surrogate pairs above the BMP), so the canonical text is pure ASCII
  and the UTF-8 encoding of it is byte-stable across platforms and locales;
- floats use Python's shortest round-trip ``repr``; ``NaN`` and ``±Infinity``
  are refused (``allow_nan=False``) because they have no interchange form;
- dict keys must be ``str``: ``json.dumps`` would silently coerce ``1`` and
  ``True`` to strings, which makes two different payloads collide, so any
  non-string key is refused up front;
- only JSON-native values are accepted: ``dict``, ``list``/``tuple``, ``str``,
  ``int``, ``float``, ``bool``, ``None``. No ``default=`` hook — an unknown
  type is refused instead of being stringified.

This helper exists because the same idiom is re-implemented in more than ten
modules of this repository with one ``ensure_ascii`` fork between them
(``atlas_contracts.event_package._canonical_hash`` vs the control plane's
``authority._canonical``). New contracts use this one; existing call sites are
unchanged here.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping

SHA256_HEX_LENGTH = 64


class CanonicalizationError(ValueError):
    """The value has no canonical JSON form (fail closed; never coerce)."""


def _assert_json_native(value: object, *, path: str) -> None:
    if value is None or isinstance(value, (str, bool, int, float)):
        return
    if isinstance(value, Mapping):
        for key, item in value.items():
            if not isinstance(key, str):
                raise CanonicalizationError(
                    f"non-string key {key!r} at {path or '$'} (would be silently coerced)"
                )
            _assert_json_native(item, path=f"{path}.{key}" if path else key)
        return
    if isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            _assert_json_native(item, path=f"{path}[{index}]")
        return
    raise CanonicalizationError(f"{type(value).__name__} at {path or '$'} is not JSON-native")


def canonical_json(value: object) -> str:
    """Return the canonical ASCII JSON text for ``value`` or raise."""
    _assert_json_native(value, path="")
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise CanonicalizationError(str(exc)) from exc


def sha256_hex(data: bytes | str) -> str:
    """Lowercase hex SHA-256 of ``data`` (``str`` is encoded as UTF-8)."""
    raw = data.encode("utf-8") if isinstance(data, str) else data
    return hashlib.sha256(raw).hexdigest()


def content_digest(value: object) -> str:
    """SHA-256 over the canonical JSON text of ``value``."""
    return sha256_hex(canonical_json(value))


def short_id(prefix: str, digest: str, *, length: int = 16) -> str:
    """Deterministic short identifier ``<prefix>-<first length hex chars>``."""
    if len(digest) != SHA256_HEX_LENGTH or any(c not in "0123456789abcdef" for c in digest):
        raise CanonicalizationError("short_id requires a lowercase 64-hex SHA-256 digest")
    if not 8 <= length <= SHA256_HEX_LENGTH:
        raise CanonicalizationError("short_id length must be between 8 and 64")
    return f"{prefix}-{digest[:length]}"


__all__ = [
    "SHA256_HEX_LENGTH",
    "CanonicalizationError",
    "canonical_json",
    "content_digest",
    "sha256_hex",
    "short_id",
]
