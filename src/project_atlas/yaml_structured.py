"""Safe, bounded structured-YAML loading and yamlpath locators (AS-EXT-001A).

Directive §7.4 (YAML path locators) and §8 (security requirements). Loading
is safe-only: no arbitrary object construction, duplicate-key rejection, and
enforced bounds on file size, nesting depth, node count, alias expansion,
scalar size, and sequence size. Rejected inputs raise structured errors —
they are never silently skipped.

Initial defaults and rationale (measured on the 31-receipt P0 corpus,
`docs/evidence/*.yaml` at base `6d87475`): largest file 51,530 bytes, deepest
nesting 5, largest node count 717, largest scalar 1,519 bytes, largest
sequence 13 items. Defaults carry roughly an order of magnitude of headroom
so legitimate receipts never trip them while bombs and runaway inputs do:

- file size: 1 MiB (~20x corpus max)
- depth: 32 (~6x corpus max). Depth counts node-visit levels — a mapping's
  keys and values each descend one level — so the constant 32 allows ~30-31
  user-visible mapping levels.
- nodes: 4,096 distinct nodes (~6x corpus max). Distinct nodes can never
  exceed expanded references (every distinct node is referenced at least
  once), so this bound is only reachable when it is tighter than the
  reference bound; 4,096 < 8,192 keeps both bounds meaningful.
- node references (alias expansion): 8,192 expanded references (corpus uses
  no aliases). An alias-free document hits the distinct-node bound first; an
  alias-amplified document hits this reference bound first.
- scalar: 64 KiB (~43x corpus max)
- sequence: 1,024 items (~79x corpus max)

Locator rules (§7.4): canonical ``yamlpath:<path>``; Unicode NFC
normalization; deterministic; independent of indentation, formatting, and
mapping order; no values, line numbers, or absolute paths in locators;
reserved characters are JSON-quoted inside brackets; sequence items use
stable keys where available (``path[key=value]``) and numeric indexes are
provisional only (``path[0]``).
"""

from __future__ import annotations

import json
import re
import unicodedata
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

import yaml
from yaml.nodes import MappingNode, Node, ScalarNode, SequenceNode

from project_atlas.domain import LocatorConfidence

#: A locator path element: mapping key, provisional sequence index, or a
#: (stable key, stable value) pair addressing one sequence item.
type PathElement = str | int | tuple[str, str]


@dataclass(frozen=True)
class YamlSecurityLimits:
    """Configurable bounded defaults (§8); enforced, not merely documented."""

    max_file_bytes: int = 1_048_576
    max_depth: int = 32
    max_nodes: int = 4_096
    max_node_references: int = 8_192
    max_scalar_bytes: int = 65_536
    max_sequence_items: int = 1_024


DEFAULT_YAML_LIMITS = YamlSecurityLimits()


class YamlSecurityError(ValueError):
    """Base class for bounded-YAML rejections; ``code`` feeds diagnostics."""

    code = "yaml-security"


class MalformedEncodingError(YamlSecurityError):
    code = "malformed-encoding"


class MalformedYamlError(YamlSecurityError):
    code = "malformed-yaml"


class UnsafeConstructionError(YamlSecurityError):
    code = "unsafe-construction"


class DuplicateKeyError(YamlSecurityError):
    code = "duplicate-yaml-key"

    def __init__(self, key: object) -> None:
        self.key = str(key)
        super().__init__(f"duplicate YAML key: {self.key!r}")


class ResourceLimitError(YamlSecurityError):
    code = "resource-limit-exceeded"

    def __init__(self, limit: str, detail: str) -> None:
        self.limit = limit
        super().__init__(f"YAML resource limit exceeded ({limit}): {detail}")


class _DuplicateGuardLoader(yaml.SafeLoader):
    """SafeLoader that rejects duplicate mapping keys explicitly (§8)."""

    def construct_mapping(self, node: MappingNode, deep: bool = False) -> dict[Any, Any]:
        self.flatten_mapping(node)
        seen: set[Any] = set()
        for key_node, _value_node in node.value:
            key = self.construct_object(key_node, deep=True)
            try:
                duplicate = key in seen
            except TypeError as exc:
                raise MalformedYamlError(f"unhashable YAML key: {key!r}") from exc
            if duplicate:
                raise DuplicateKeyError(key)
            seen.add(key)
        return super().construct_mapping(node, deep=deep)


def _check_scalar(node: ScalarNode, limits: YamlSecurityLimits) -> None:
    encoded = node.value.encode("utf-8", errors="replace")
    if len(encoded) > limits.max_scalar_bytes:
        raise ResourceLimitError(
            "max_scalar_bytes", f"scalar of {len(encoded)} bytes at line {node.start_mark.line + 1}"
        )


def _walk_node_graph(root: Node, limits: YamlSecurityLimits) -> None:
    """Enforce depth, node-count, alias-expansion, scalar and sequence bounds.

    Alias-shared nodes are revisited by design: the reference counter sees the
    expanded size of the document, so alias amplification is bounded. Cycles
    (self-referential anchors) are cut with an active-path set.
    """
    references = 0
    unique: set[int] = set()
    active: set[int] = set()

    def visit(node: Node, depth: int) -> None:
        nonlocal references
        references += 1
        if references > limits.max_node_references:
            raise ResourceLimitError(
                "max_node_references", f"more than {limits.max_node_references} expanded nodes"
            )
        unique.add(id(node))
        if len(unique) > limits.max_nodes:
            raise ResourceLimitError("max_nodes", f"more than {limits.max_nodes} distinct nodes")
        if depth > limits.max_depth:
            raise ResourceLimitError("max_depth", f"nesting deeper than {limits.max_depth}")
        if id(node) in active:
            return  # self-referential anchor: count the reference, stop descent
        if isinstance(node, ScalarNode):
            _check_scalar(node, limits)
            return
        active.add(id(node))
        try:
            if isinstance(node, SequenceNode):
                if len(node.value) > limits.max_sequence_items:
                    raise ResourceLimitError(
                        "max_sequence_items",
                        f"sequence of {len(node.value)} items at line {node.start_mark.line + 1}",
                    )
                for child in node.value:
                    visit(child, depth + 1)
            elif isinstance(node, MappingNode):
                for key_node, value_node in node.value:
                    visit(key_node, depth + 1)
                    visit(value_node, depth + 1)
        finally:
            active.discard(id(node))

    visit(root, 1)


def load_safe_yaml(data: bytes | str, limits: YamlSecurityLimits = DEFAULT_YAML_LIMITS) -> Any:
    """Load YAML under safe construction and enforced resource bounds (§8).

    Raises :class:`MalformedEncodingError`, :class:`MalformedYamlError`,
    :class:`UnsafeConstructionError`, :class:`DuplicateKeyError`, or
    :class:`ResourceLimitError`; never returns silently skipped input.
    """
    if isinstance(data, bytes):
        if len(data) > limits.max_file_bytes:
            raise ResourceLimitError(
                "max_file_bytes", f"input of {len(data)} bytes exceeds {limits.max_file_bytes}"
            )
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise MalformedEncodingError(f"input is not valid UTF-8: {exc}") from exc
    else:
        text = data
        if len(text.encode("utf-8")) > limits.max_file_bytes:
            raise ResourceLimitError(
                "max_file_bytes", f"input exceeds {limits.max_file_bytes} bytes"
            )

    try:
        root = yaml.compose(text, Loader=yaml.SafeLoader)
    except yaml.YAMLError as exc:
        raise MalformedYamlError(f"YAML parse failure: {exc}") from exc
    except RecursionError as exc:
        # Pathological nesting exhausts the parser's C-level recursion before
        # the depth bound can run; surface it through the same structured
        # security-error contract (§8), never as a raw RecursionError.
        raise ResourceLimitError(
            "max_depth", "nesting exceeds the parser recursion bound"
        ) from exc
    if root is None:
        return None
    _walk_node_graph(root, limits)

    try:
        loader = _DuplicateGuardLoader(text)
        try:
            return loader.get_single_data()
        finally:
            loader.dispose()  # type: ignore[no-untyped-call]
    except YamlSecurityError:
        raise
    except yaml.constructor.ConstructorError as exc:
        # SafeLoader refuses non-standard tags (e.g. !!python/object): this is
        # the no-arbitrary-object-construction guarantee, surfaced explicitly.
        raise UnsafeConstructionError(f"unsafe YAML construction refused: {exc}") from exc
    except yaml.YAMLError as exc:
        raise MalformedYamlError(f"YAML parse failure: {exc}") from exc


# --- yamlpath locators (§7.4) ---------------------------------------------

_SAFE_SEGMENT = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_-]*$")

#: Priority order of keys that make a sequence item addressable (§7.4).
STABLE_KEY_CANDIDATES: tuple[str, ...] = ("candidate_id", "id", "name", "key")


def nfc(value: str) -> str:
    """Unicode NFC normalization for locator segments (§7.4/§8)."""
    return unicodedata.normalize("NFC", value)


def _encode_segment(key: str) -> str:
    segment = nfc(key)
    if _SAFE_SEGMENT.match(segment):
        return segment
    # Reserved-character handling: JSON-quoting keeps dots, brackets, spaces,
    # and quotes unambiguous inside the dotted locator.
    return f"[{json.dumps(segment, ensure_ascii=False)}]"


def sequence_item_segment(item: Any, index: int) -> tuple[str, LocatorConfidence]:
    """Address one sequence item: stable key where available, else index.

    Numeric indexes are provisional only (§7.4); the returned confidence
    marks that explicitly.
    """
    if isinstance(item, dict):
        for candidate in STABLE_KEY_CANDIDATES:
            value = item.get(candidate)
            if isinstance(value, str) and value:
                encoded = _encode_segment(value)
                return f"[{candidate}={encoded}]", LocatorConfidence.STABLE
    return f"[{index}]", LocatorConfidence.PROVISIONAL


def yaml_path_locator(path: tuple[PathElement, ...]) -> str:
    """Build a canonical ``yamlpath:`` locator from path elements (§7.4).

    No values, line numbers, or absolute paths appear in the locator; the
    tuple encoding stays compatible with Claim Identity v2 canonicalization.
    """
    parts: list[str] = []
    for element in path:
        if isinstance(element, tuple):
            key, value = element
            parts.append(f"[{_encode_segment(key)}={_encode_segment(value)}]")
        elif isinstance(element, int):
            parts.append(f"[{element}]")
        else:
            parts.append(_encode_segment(element))
    locator = ""
    for part in parts:
        if part.startswith("["):
            locator += part
        else:
            locator += ("." if locator else "") + part
    return f"yamlpath:{locator}"


def iter_leaf_paths(
    tree: Any, path: tuple[PathElement, ...] = ()
) -> Iterator[tuple[tuple[PathElement, ...], Any]]:
    """Yield ``(path, scalar)`` for every leaf in document order.

    Mapping traversal follows parsed document order (locators are independent
    of mapping order because each leaf carries its own full path). Sequence
    items are addressed by stable key where available and by provisional
    numeric index otherwise.
    """
    if isinstance(tree, dict):
        for key, value in tree.items():
            key_text = (
                key
                if isinstance(key, str)
                else json.dumps(key, ensure_ascii=False, sort_keys=True)
            )
            yield from iter_leaf_paths(value, (*path, key_text))
    elif isinstance(tree, list):
        for index, item in enumerate(tree):
            element: PathElement = index
            if isinstance(item, dict):
                for candidate in STABLE_KEY_CANDIDATES:
                    stable = item.get(candidate)
                    if isinstance(stable, str) and stable:
                        element = (candidate, stable)
                        break
            yield from iter_leaf_paths(item, (*path, element))
    else:
        yield path, tree
