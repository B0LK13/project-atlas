"""Machine-readable managed-agent session state."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, cast

# Conservative local fallback matching project_atlas.secrets high-confidence
# patterns. Control-plane suite must fail closed even if Core is not importable.
_FALLBACK_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]{20,}"),
    re.compile(
        r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"
        r"[\s\S]*?"
        r"-----END (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"
    ),
)


def _has_secret(text: str) -> bool:
    """True when decoded text matches a secret-shaped pattern (NFR-004)."""
    try:
        from project_atlas.secrets import scan_text
    except ImportError:
        return any(pattern.search(text) for pattern in _FALLBACK_PATTERNS)
    return bool(scan_text(text))


def _scan_decoded_or_raise(payload: Any) -> None:
    """Fail closed on secret-shaped strings after JSON/YAML decode.

    AS-SEC-SCAN-CTRL-SESSION-JSON-ESC-001: session writers must rescan
    decoded scalars. ``scan_text`` on raw ``\\u0041KI…`` bytes is empty;
    ``json.loads`` reveals ``AKI…`` which must not be written to
    ``.atlas/sessions/``.
    """
    if isinstance(payload, str):
        if _has_secret(payload):
            raise ValueError("secret-shaped session state")
        return
    if isinstance(payload, dict):
        for value in payload.values():
            _scan_decoded_or_raise(value)
        return
    if isinstance(payload, list):
        for value in payload:
            _scan_decoded_or_raise(value)


def path(root: Path, session_id: str) -> Path:
    return root / ".atlas" / "sessions" / f"{session_id}.json"


def save(root: Path, state: dict[str, Any]) -> Path:
    _scan_decoded_or_raise(state)
    target = path(root, str(state["session"]["session_id"]))
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return target


def load(root: Path, session_id: str) -> dict[str, Any]:
    target = path(root, session_id)
    if not target.is_file():
        raise ValueError(f"session not found: {session_id}")
    return cast(dict[str, Any], json.loads(target.read_text(encoding="utf-8")))
