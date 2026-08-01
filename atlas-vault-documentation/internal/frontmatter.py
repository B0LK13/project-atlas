"""Frontmatter handling for router-managed pages.

Router-owned pages regenerate their managed frontmatter keys
deterministically on every projection update. Keys the router does not
manage (human additions) are preserved and sorted after the managed
keys. Values are emitted as JSON-quoted scalars, matching the capture
and normalization conventions.
"""

from __future__ import annotations

import json

from internal import provenance


def parse_flat(text: str) -> tuple[dict[str, str], str]:
    """Split a document into (flat frontmatter scalars, body).

    Nested keys and list items are skipped (they are not managed).
    """
    frontmatter, body = provenance.split_document(text)
    flat: dict[str, str] = {}
    for line in frontmatter.splitlines():
        if not line or line.startswith((" ", "-")) or ":" not in line:
            continue
        key, _, value = line.partition(":")
        flat[key.strip()] = value.strip().strip('"')
    return flat, body


def render(managed: list[tuple[str, str]], preserved: dict[str, str] | None = None) -> str:
    """Render frontmatter: managed keys in order, then preserved extras."""
    lines = ["---"]
    emitted = set()
    for key, value in managed:
        lines.append(f"{key}: {json.dumps(value, ensure_ascii=False)}")
        emitted.add(key)
    for key in sorted((preserved or {})):
        if key not in emitted:
            lines.append(f"{key}: {json.dumps((preserved or {})[key], ensure_ascii=False)}")
    lines.append("---")
    return "\n".join(lines)


def replace_frontmatter(text: str, managed: list[tuple[str, str]]) -> str:
    """Replace managed keys in ``text``'s frontmatter, preserving the rest."""
    flat, body = parse_flat(text)
    managed_keys = {key for key, _ in managed}
    preserved = {key: value for key, value in flat.items() if key not in managed_keys}
    return render(managed, preserved) + "\n" + body
