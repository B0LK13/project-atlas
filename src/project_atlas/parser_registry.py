"""Static parser registry (AS-D-006 / NFR-006 / EXT-001A §7.3).

Maps each closed ``ParserSelection`` / ``parser_id`` to exactly one parse
callable. Lookup of an unknown id fails closed. Bindings are a one-shot
static table — no plugin discovery, no package entry points, and no
runtime module-loader invent (directive §7.3 / §11).
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from project_atlas.classification import ParserSelection

#: Closed §7.3 parser-id surface (must match ``ParserSelection`` exactly).
STATIC_PARSER_IDS: frozenset[str] = frozenset(
    {
        "project-manifest",
        "evidence-yaml",
        "adr",
        "verify-profile",
        "kv-markdown",
        "none",
    }
)

#: Parse callable bound into the registry: ``(project, entry, classification)``.
ParserCallable = Callable[..., Any]

_BOUND: dict[str, ParserCallable] | None = None

__all__ = [
    "STATIC_PARSER_IDS",
    "ParserCallable",
    "ParserSelection",
    "UnknownParserIdError",
    "bind_static_parsers",
    "get_parser",
    "is_registered_parser_id",
    "registered_parser_ids",
]


class UnknownParserIdError(ValueError):
    """Fail-closed: ``parser_id`` is not in the static §7.3 registry."""


def bind_static_parsers(handlers: Mapping[str, ParserCallable]) -> None:
    """Bind the exclusive static parser table (D006-FR-001/002/004/005).

    Requires exactly the closed ``STATIC_PARSER_IDS`` set — no extras, no
    missing members. Re-binding with the same closed set is allowed so
    module reloads / test re-imports stay deterministic; dynamic plugin
    registration is never offered.
    """
    global _BOUND
    ids = frozenset(handlers)
    if ids != STATIC_PARSER_IDS:
        missing = sorted(STATIC_PARSER_IDS - ids)
        extra = sorted(ids - STATIC_PARSER_IDS)
        raise ValueError(
            "static parser bind must cover exactly "
            f"{sorted(STATIC_PARSER_IDS)}; missing={missing} extra={extra}"
        )
    # Deterministic key order (NFR-001); one callable per id (§7.3 exclusivity).
    _BOUND = {parser_id: handlers[parser_id] for parser_id in sorted(handlers)}


def get_parser(parser_id: str) -> ParserCallable:
    """Resolve ``parser_id`` to its exclusive parse callable (fail-closed)."""
    if _BOUND is None:
        raise RuntimeError("AS-D-006: static parsers are not bound")
    handler = _BOUND.get(parser_id)
    if handler is None:
        raise UnknownParserIdError(
            f"unknown parser_id {parser_id!r}; "
            f"registered={sorted(_BOUND)}"
        )
    return handler


def registered_parser_ids() -> frozenset[str]:
    """Return the closed static parser-id set (bound or unbound)."""
    return STATIC_PARSER_IDS


def is_registered_parser_id(parser_id: str) -> bool:
    """True iff ``parser_id`` is a member of the closed §7.3 set."""
    return parser_id in STATIC_PARSER_IDS
