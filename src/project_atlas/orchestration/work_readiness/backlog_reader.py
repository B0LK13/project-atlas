"""Bounded backlog seed readers. No repository-wide scans."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

# Checkbox task lines: - [ ] **AS-XXX-001** \u2014 title  or  - [ ] AS-XXX-001 title
_TASK_LINE = re.compile(
    r"^[-*]\s+\[(?P<checked>[ xX])\]\s+"
    r"(?:\*\*)?(?P<id>[A-Z]{1,12}-[A-Z0-9][A-Z0-9._-]{2,80})(?:\*\*)?"
    r"(?:\s*[\u2014\u2013:-]\s*|\s+)(?P<title>.+)?$"
)


def read_backlog_seeds(
    path: Path,
    *,
    max_bytes: int = 512_000,
    max_items: int = 200,
) -> tuple[list[dict[str, Any]], dict[str, str]]:
    """Read open checkbox items from a backlog markdown file (bounded).

    Returns (seeds, source_revisions). Does not mutate the backlog.
    """
    if not path.is_file():
        return [], {"backlog": "UNREACHABLE"}
    data = path.read_bytes()[:max_bytes]
    text = data.decode("utf-8", errors="replace")
    # Cheap revision token without hashing the whole repo.
    revision = f"size={len(data)};head16={data[:16].hex()}"
    seeds: list[dict[str, Any]] = []
    for line in text.splitlines():
        match = _TASK_LINE.match(line.strip())
        if not match:
            continue
        if match.group("checked").lower() == "x":
            continue
        task_id = match.group("id")
        title = (match.group("title") or task_id).strip()
        if len(title) > 2000:
            title = title[:1997] + "..."
        seeds.append(
            {
                "task_id": task_id,
                "source_ref": f"{path.name}:{task_id}",
                "source_revision": revision,
                "objective": title,
                "expected_result": "",
                "priority": None,
            }
        )
        if len(seeds) >= max_items:
            break
    return seeds, {"backlog": revision, "backlog_path": str(path)}
