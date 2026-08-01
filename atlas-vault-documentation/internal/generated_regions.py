"""Human-safe generated regions (AS-WP-003 Phase 7; FR-S009; AS-015).

Generated Atlas pages may embed human-maintained content. Only text
inside matching marker pairs may be regenerated:

    <!-- ATLAS:BEGIN <region-id> schema=1 -->
    ...generated content...
    <!-- ATLAS:END <region-id> -->

Everything outside markers is preserved byte-for-byte. Malformed,
duplicated, nested, mismatched, or unsupported markers fail closed:
no write happens and a structured :class:`RegionError` is raised.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

REGION_ID = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
BEGIN = re.compile(r"^<!-- ATLAS:BEGIN ([a-z0-9][a-z0-9-]{0,63}) schema=(\d+) -->\s*$")
END = re.compile(r"^<!-- ATLAS:END ([a-z0-9][a-z0-9-]{0,63}) -->\s*$")
ANY_MARKER = re.compile(r"<!-- ATLAS:(BEGIN|END)")

SUPPORTED_SCHEMA = 1

CATEGORY_UNCLOSED = "unclosed-region"
CATEGORY_STRAY_END = "stray-end-marker"
CATEGORY_MISMATCH = "mismatched-markers"
CATEGORY_DUPLICATE = "duplicate-region-id"
CATEGORY_NESTED = "nested-region"
CATEGORY_UNSUPPORTED_SCHEMA = "unsupported-schema"
CATEGORY_MISSING_REGION = "missing-region"
CATEGORY_MALFORMED_MARKER = "malformed-marker"


class RegionError(ValueError):
    """Fail-closed generated-region error with a structured category."""

    def __init__(self, category: str, region_id: str | None, message: str) -> None:
        super().__init__(message)
        self.category = category
        self.region_id = region_id


@dataclass(frozen=True)
class Region:
    """One validated generated region with its content span."""

    region_id: str
    schema: int
    begin_line: int  # index of the BEGIN marker line
    end_line: int  # index of the END marker line

    @property
    def content_lines(self) -> slice:
        return slice(self.begin_line + 1, self.end_line)


def parse_regions(text: str) -> list[Region]:
    """Parse and validate all generated regions in ``text``.

    Raises :class:`RegionError` on any malformed marker structure.
    """
    lines = text.split("\n")
    regions: list[Region] = []
    seen: set[str] = set()
    open_id: str | None = None
    open_schema = 0
    open_line = 0

    for index, line in enumerate(lines):
        begin = BEGIN.match(line)
        end = END.match(line)
        if begin:
            if open_id is not None:
                raise RegionError(
                    CATEGORY_NESTED, begin.group(1),
                    f"nested ATLAS:BEGIN {begin.group(1)!r} inside region {open_id!r} "
                    f"(line {index + 1})",
                )
            schema = int(begin.group(2))
            if schema != SUPPORTED_SCHEMA:
                raise RegionError(
                    CATEGORY_UNSUPPORTED_SCHEMA, begin.group(1),
                    f"unsupported region schema {schema} for {begin.group(1)!r}",
                )
            if begin.group(1) in seen:
                raise RegionError(
                    CATEGORY_DUPLICATE, begin.group(1),
                    f"duplicate region id {begin.group(1)!r}",
                )
            open_id, open_schema, open_line = begin.group(1), schema, index
        elif end:
            if open_id is None:
                raise RegionError(
                    CATEGORY_STRAY_END, end.group(1),
                    f"ATLAS:END {end.group(1)!r} without ATLAS:BEGIN (line {index + 1})",
                )
            if end.group(1) != open_id:
                raise RegionError(
                    CATEGORY_MISMATCH, end.group(1),
                    f"ATLAS:END {end.group(1)!r} does not match ATLAS:BEGIN {open_id!r}",
                )
            regions.append(Region(open_id, open_schema, open_line, index))
            seen.add(open_id)
            open_id = None
        elif ANY_MARKER.search(line):
            raise RegionError(
                CATEGORY_MALFORMED_MARKER, None,
                f"malformed ATLAS marker at line {index + 1}: {line.strip()!r}",
            )

    if open_id is not None:
        raise RegionError(
            CATEGORY_UNCLOSED, open_id,
            f"ATLAS:BEGIN {open_id!r} has no ATLAS:END",
        )
    return regions


def region_ids(text: str) -> list[str]:
    return [region.region_id for region in parse_regions(text)]


def render_region(region_id: str, content: str) -> str:
    """Render one complete marker pair around ``content``."""
    if not REGION_ID.fullmatch(region_id):
        raise RegionError(CATEGORY_MALFORMED_MARKER, region_id, f"invalid region id {region_id!r}")
    body = content.rstrip("\n")
    return (
        f"<!-- ATLAS:BEGIN {region_id} schema=1 -->\n"
        f"{body}\n"
        f"<!-- ATLAS:END {region_id} -->"
    )


def update_regions(text: str, updates: dict[str, str]) -> str:
    """Return ``text`` with the named regions' contents replaced.

    Bytes outside the regions are preserved exactly. Unknown region IDs
    in ``updates`` fail closed.
    """
    regions = parse_regions(text)
    by_id = {region.region_id: region for region in regions}
    unknown = sorted(set(updates) - set(by_id))
    if unknown:
        raise RegionError(
            CATEGORY_MISSING_REGION, unknown[0],
            f"region(s) not present in file: {', '.join(unknown)}",
        )
    lines = text.split("\n")
    for region in sorted(regions, key=lambda r: r.begin_line, reverse=True):
        if region.region_id not in updates:
            continue
        content = updates[region.region_id].rstrip("\n")
        lines[region.content_lines] = content.split("\n") if content else [""]
    return "\n".join(lines)
