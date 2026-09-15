"""Vault-relative link helpers (AS-WP-003; FR-S010 path rules).

All links between Atlas pages are vault-relative POSIX paths computed
deterministically with :func:`posixpath.relpath` — never free-form
strings and never absolute paths in stored pages.
"""

from __future__ import annotations

import posixpath
import re
from pathlib import Path

MARKDOWN_LINK = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")


def relative_link(target_rel: str, from_file_rel: str) -> str:
    """POSIX relative link from one vault file to another."""
    from_dir = posixpath.dirname(from_file_rel)
    return posixpath.relpath(target_rel, from_dir)


def markdown_link(label: str, target_rel: str, from_file_rel: str) -> str:
    return f"[{label}]({relative_link(target_rel, from_file_rel)})"


def extract_links(text: str) -> list[str]:
    """All Markdown link targets in ``text`` (external URLs excluded)."""
    return [
        target
        for target in MARKDOWN_LINK.findall(text)
        if not target.startswith(("http://", "https://", "mailto:", "#"))
    ]


def resolve_link(link: str, from_file_rel: str) -> str:
    """Resolve a relative link to a vault-relative POSIX path."""
    return posixpath.normpath(posixpath.join(posixpath.dirname(from_file_rel), link))


def link_exists(link: str, from_file_rel: str, vault_root: Path) -> bool:
    resolved = resolve_link(link, from_file_rel)
    if resolved.startswith("../") or resolved.startswith("/"):
        return False
    return (vault_root / resolved).is_file()
