"""AS-INCR-COMPILE-001 tip-safe compiler cache / invalidation helpers.

Deterministic invalidation keys, stale-artifact detection, and FR-013
unchanged-hash byte-identical no-op over settled MODEL / compiler outputs.

Cache hit / skip ≠ authority winner ≠ temporal tip ≠ trust score.
Does not reopen MODEL-001A/B/C composition. Does not dual-own GRAPH
incremental quarantine / projections / graph-incremental-state, XPROJ-003
duplicate-candidates, XPROJ-004 indexes/conflicts, or AS-RET-001.

Do not confuse EXT-001A ``compilation.py`` (per-source outcome SM) or
``graph-incremental-state`` with this package.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
import re
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Literal

from project_atlas.schema import SchemaValidationError, validate_record
from project_atlas.secrets import scan_text

PACKAGE_ID = "AS-INCR-COMPILE-001"
SCHEMA_KIND = "compile-cache-receipt"
SCHEMA_VERSION = 1
RECEIPT_KIND = "compile_cache_receipt"
GENERATED_BY = "atlas-incr-compile-001"

#: Contracted vault emit root — disjoint from GRAPH / XPROJ product trees.
CACHE_ROOT = Path("generated") / "compile-cache"

CacheDisposition = Literal["hit", "miss", "stale", "recompile", "ambiguous"]
NoopDisposition = Literal["noop", "recompile", "abort"]

_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_SAFE_SCOPE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_SAFE_REDACTED_NOTE = "cache note redacted (secret-shaped content)"

_FORBIDDEN_RECEIPT_KEYS: frozenset[str] = frozenset(
    {
        "trust",
        "trust_score",
        "confidence",
        "confidence_score",
        "subjective_trust",
        "authority_disposition",
        "authority_winner",
        "temporal_tip",
        "claim_id",
        "value",
        "graph_id",
        "graph_subject",
        "resolved_entity_id",
        "global_entity_id",
    }
)

_FORBIDDEN_RELATIVE_PREFIXES: tuple[str, ...] = (
    "generated/graph/",
    "generated/xproj/",
    "generated/indexes/",
    "indexes/",
    "graph-incremental-state",
)


class CompileCacheError(ValueError):
    """Fail-closed cache / invalidation rejection."""

    def __init__(self, message: str, *, code: str = "ambiguous_invalidation") -> None:
        self.code = code
        self.message = message
        super().__init__(f"{self.code}: {message}")

    def to_dict(self) -> dict[str, Any]:
        """Structured rejection envelope (never a success hit)."""
        return {
            "schema_version": SCHEMA_VERSION,
            "package": PACKAGE_ID,
            "status": self.code,
            "message": self.message,
        }


def _digest(payload: str | bytes) -> str:
    if isinstance(payload, str):
        payload = payload.encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _canonical_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _reject_forbidden_keys(payload: Mapping[str, Any], *, path: str) -> None:
    for key in payload:
        if key in _FORBIDDEN_RECEIPT_KEYS or str(key).startswith("graph_"):
            raise CompileCacheError(
                f"forbidden field {key!r} at {path} "
                "(cache ≠ authority/trust/graph; IC-FR-008/009)",
                code="forbidden_field",
            )


def _normalize_fingerprints(
    fingerprints: Mapping[str, str],
    *,
    path: str = "input_fingerprints",
) -> dict[str, str]:
    if not isinstance(fingerprints, Mapping) or not fingerprints:
        raise CompileCacheError(
            f"{path} must be a non-empty mapping of name → sha256",
            code="ambiguous_invalidation",
        )
    out: dict[str, str] = {}
    for raw_name, raw_digest in fingerprints.items():
        if not isinstance(raw_name, str) or not raw_name.strip():
            raise CompileCacheError(
                f"{path} keys must be non-empty strings",
                code="ambiguous_invalidation",
            )
        name = raw_name.strip()
        if not isinstance(raw_digest, str) or not _HEX64.fullmatch(raw_digest.lower()):
            raise CompileCacheError(
                f"{path}[{name!r}] must be a lowercase 64-hex sha256 digest",
                code="ambiguous_invalidation",
            )
        out[name] = raw_digest.lower()
    return {k: out[k] for k in sorted(out)}


def _normalize_scope_id(scope_id: str) -> str:
    if not isinstance(scope_id, str) or not _SAFE_SCOPE.fullmatch(scope_id):
        raise CompileCacheError(
            "scope_id must match ^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$",
            code="ambiguous_invalidation",
        )
    return scope_id


def _normalize_artifact_paths(paths: Sequence[str] | None) -> list[str]:
    if not paths:
        return []
    out: list[str] = []
    for raw in paths:
        if not isinstance(raw, str) or not raw.strip():
            raise CompileCacheError(
                "artifact_paths entries must be non-empty strings",
                code="ambiguous_invalidation",
            )
        rel = raw.strip().replace("\\", "/")
        if rel.startswith("/") or ".." in rel.split("/"):
            raise CompileCacheError(
                f"artifact path {raw!r} is unsafe",
                code="path_policy_violation",
            )
        lower = rel.lower()
        for prefix in _FORBIDDEN_RELATIVE_PREFIXES:
            if lower == prefix.rstrip("/") or lower.startswith(prefix):
                raise CompileCacheError(
                    f"artifact path {rel!r} dual-owns forbidden surface "
                    f"(prefix {prefix!r}; IC-FR-014/015/016)",
                    code="path_policy_violation",
                )
        out.append(rel)
    return sorted(set(out))


def _redact_notes(notes: Sequence[str] | None) -> list[str]:
    if not notes:
        return []
    out: list[str] = []
    for note in notes:
        if not isinstance(note, str):
            raise CompileCacheError("notes entries must be strings", code="ambiguous_invalidation")
        if scan_text(note):
            out.append(_SAFE_REDACTED_NOTE)
        else:
            out.append(note)
    return out


def compute_invalidation_key(
    *,
    scope_id: str,
    input_fingerprints: Mapping[str, str],
    artifact_paths: Sequence[str] | None = None,
) -> str:
    """Deterministic invalidation key (IC-FR-002/003; NFR-001 — no wall-clock)."""
    scope = _normalize_scope_id(scope_id)
    fingerprints = _normalize_fingerprints(input_fingerprints)
    artifacts = _normalize_artifact_paths(artifact_paths)
    material = {
        "package": PACKAGE_ID,
        "schema_version": SCHEMA_VERSION,
        "scope_id": scope,
        "input_fingerprints": fingerprints,
        "artifact_paths": artifacts,
    }
    return _digest(_canonical_json(material))


def combined_fingerprint(input_fingerprints: Mapping[str, str]) -> str:
    """SHA-256 over the sorted fingerprint map alone (FR-013 combined-hash)."""
    fingerprints = _normalize_fingerprints(input_fingerprints)
    return _digest(_canonical_json(fingerprints))


def decide_cache_action(
    *,
    recomputed_key: str,
    recorded_key: str | None,
    artifact_present: bool,
) -> CacheDisposition:
    """Decide hit / miss / stale / ambiguous (IC-FR-006/010).

    Never reports success-skip when keys are missing or mismatched.
    """
    if not isinstance(recomputed_key, str) or not _HEX64.fullmatch(recomputed_key.lower()):
        return "ambiguous"
    recomputed = recomputed_key.lower()
    if recorded_key is None:
        return "miss" if not artifact_present else "stale"
    if not isinstance(recorded_key, str) or not _HEX64.fullmatch(recorded_key.lower()):
        return "ambiguous"
    recorded = recorded_key.lower()
    if recorded != recomputed:
        return "stale"
    if not artifact_present:
        # Key matches prior receipt but artifact missing → must recompile.
        return "recompile"
    return "hit"


def evaluate_compile_refresh(
    *,
    scope_id: str,
    input_fingerprints: Mapping[str, str],
    artifact_paths: Sequence[str] | None = None,
    recorded_key: str | None = None,
    previous_output: bytes | None = None,
    candidate_output: bytes | None = None,
) -> dict[str, Any]:
    """Evaluate tip-safe refresh for one compile scope (IC-FR-004/005/006).

    Returns a decision envelope. On ``noop``, ``output_bytes`` is the prior
    artifact (byte-identical). On ``recompile``, ``impacted_artifacts`` lists
    the contracted impact set. Ambiguous cases raise :class:`CompileCacheError`.
    """
    scope = _normalize_scope_id(scope_id)
    fingerprints = _normalize_fingerprints(input_fingerprints)
    artifacts = _normalize_artifact_paths(artifact_paths)
    recomputed = compute_invalidation_key(
        scope_id=scope,
        input_fingerprints=fingerprints,
        artifact_paths=artifacts,
    )
    combined = combined_fingerprint(fingerprints)
    artifact_present = previous_output is not None
    disposition = decide_cache_action(
        recomputed_key=recomputed,
        recorded_key=recorded_key,
        artifact_present=artifact_present,
    )
    if disposition == "ambiguous":
        raise CompileCacheError(
            "ambiguous invalidation — refuse silent skip (IC-FR-010)",
            code="ambiguous_invalidation",
        )
    if disposition == "hit":
        assert previous_output is not None
        if candidate_output is not None and candidate_output != previous_output:
            # FR-013 / IC-ADV-002: unchanged key must not rewrite bytes.
            raise CompileCacheError(
                "unchanged invalidation key but candidate output differs from "
                "previous artifact — refuse non-identical rewrite (IC-FR-004)",
                code="fr013_byte_mismatch",
            )
        return {
            "schema_version": SCHEMA_VERSION,
            "package": PACKAGE_ID,
            "scope_id": scope,
            "disposition": "hit",
            "noop_disposition": "noop",
            "invalidation_key": recomputed,
            "combined_fingerprint": combined,
            "impacted_artifacts": [],
            "output_bytes": previous_output,
            "notes": [
                "AS-INCR-COMPILE-001: unchanged fingerprint → byte-identical no-op (FR-013).",
                "Cache hit ≠ authority winner / trust score.",
            ],
        }
    # miss / stale / recompile → deterministic recompile of impacted set
    return {
        "schema_version": SCHEMA_VERSION,
        "package": PACKAGE_ID,
        "scope_id": scope,
        "disposition": disposition,
        "noop_disposition": "recompile",
        "invalidation_key": recomputed,
        "combined_fingerprint": combined,
        "impacted_artifacts": list(artifacts) if artifacts else [scope],
        "output_bytes": candidate_output,
        "notes": [
            f"AS-INCR-COMPILE-001: disposition={disposition}; recompile impacted set.",
            "Cache metadata must not elevate authority or invent trust scores.",
        ],
    }


def apply_byte_identical_noop(
    *,
    previous_output: bytes,
    candidate_output: bytes | None = None,
) -> bytes:
    """FR-013 helper: return prior bytes; reject divergent candidates."""
    if candidate_output is not None and candidate_output != previous_output:
        raise CompileCacheError(
            "FR-013 no-op refused: candidate bytes differ from previous artifact",
            code="fr013_byte_mismatch",
        )
    return previous_output


def build_cache_receipt(
    *,
    scope_id: str,
    input_fingerprints: Mapping[str, str],
    disposition: CacheDisposition,
    artifact_paths: Sequence[str] | None = None,
    invalidation_key: str | None = None,
    notes: Sequence[str] | None = None,
) -> dict[str, Any]:
    """Build a schema-valid compile-cache receipt (IC-FR-001/011)."""
    if disposition == "ambiguous":
        raise CompileCacheError(
            "cannot emit success receipt for ambiguous invalidation",
            code="ambiguous_invalidation",
        )
    scope = _normalize_scope_id(scope_id)
    fingerprints = _normalize_fingerprints(input_fingerprints)
    artifacts = _normalize_artifact_paths(artifact_paths)
    key = invalidation_key or compute_invalidation_key(
        scope_id=scope,
        input_fingerprints=fingerprints,
        artifact_paths=artifacts,
    )
    if not _HEX64.fullmatch(key.lower()):
        raise CompileCacheError(
            "invalidation_key must be a 64-hex sha256 digest",
            code="ambiguous_invalidation",
        )
    receipt: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "package": PACKAGE_ID,
        "receipt_kind": RECEIPT_KIND,
        "generated": {"by": GENERATED_BY},
        "scope_id": scope,
        "invalidation_key": key.lower(),
        "combined_fingerprint": combined_fingerprint(fingerprints),
        "input_fingerprints": fingerprints,
        "artifact_paths": artifacts,
        "disposition": disposition,
        "noop_disposition": "noop" if disposition == "hit" else "recompile",
        "impacted_artifacts": [] if disposition == "hit" else (artifacts or [scope]),
        "notes": _redact_notes(notes),
    }
    _reject_forbidden_keys(receipt, path="receipt")
    try:
        validate_record(receipt, SCHEMA_KIND)
    except SchemaValidationError as exc:
        raise CompileCacheError(
            f"receipt failed schema validation: {exc}",
            code="schema_invalid",
        ) from exc
    return receipt


def receipt_to_json(receipt: Mapping[str, Any]) -> str:
    """Deterministic JSON serialization (IC-FR-011 / NFR-001)."""
    _reject_forbidden_keys(receipt, path="receipt")
    return json.dumps(dict(receipt), sort_keys=True, ensure_ascii=False, indent=2) + "\n"


def receipt_relative_path(scope_id: str) -> Path:
    """Return contracted relative receipt path under ``generated/compile-cache/``."""
    scope = _normalize_scope_id(scope_id)
    return CACHE_ROOT / f"{scope}.json"


def assert_cache_path_allowed(relative_path: str | Path) -> Path:
    """Fail closed if a write path would dual-own GRAPH/XPROJ/RET surfaces."""
    rel = Path(str(relative_path).replace("\\", "/"))
    posix = rel.as_posix().lstrip("./")
    lower = posix.lower()
    for prefix in _FORBIDDEN_RELATIVE_PREFIXES:
        if lower == prefix.rstrip("/") or lower.startswith(prefix):
            raise CompileCacheError(
                f"path {posix!r} is forbidden for AS-INCR-COMPILE-001 "
                f"(dual-own prefix {prefix!r})",
                code="path_policy_violation",
            )
    if not lower.startswith("generated/compile-cache/"):
        raise CompileCacheError(
            f"path {posix!r} must live under generated/compile-cache/ (IC-FR-013)",
            code="path_policy_violation",
        )
    if ".." in rel.parts:
        raise CompileCacheError(
            f"path {posix!r} contains '..'",
            code="path_policy_violation",
        )
    return Path(posix)


def write_cache_receipt(vault: Path, receipt: Mapping[str, Any]) -> Path:
    """Atomically write a schema-valid receipt under ``generated/compile-cache/``."""
    scope = str(receipt.get("scope_id", ""))
    rel = assert_cache_path_allowed(receipt_relative_path(scope))
    target = vault.resolve() / rel
    if not target.resolve().is_relative_to(vault.resolve()):
        raise CompileCacheError(
            "receipt path escapes vault root",
            code="path_policy_violation",
        )
    payload = receipt_to_json(receipt)
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(target.suffix + ".tmp")
    try:
        tmp.write_text(payload, encoding="utf-8", newline="\n")
        os.replace(tmp, target)
    finally:
        if tmp.exists():
            with contextlib.suppress(OSError):
                tmp.unlink()
    return target


def read_cache_receipt(vault: Path, scope_id: str) -> dict[str, Any] | None:
    """Load a prior receipt if present; return None when absent."""
    rel = assert_cache_path_allowed(receipt_relative_path(scope_id))
    path = vault.resolve() / rel
    if not path.is_file():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise CompileCacheError(
            f"malformed cache receipt at {rel.as_posix()}: {exc}",
            code="ambiguous_invalidation",
        ) from exc
    if not isinstance(raw, dict):
        raise CompileCacheError(
            "cache receipt root must be an object",
            code="ambiguous_invalidation",
        )
    _reject_forbidden_keys(raw, path="receipt")
    try:
        validate_record(raw, SCHEMA_KIND)
    except SchemaValidationError as exc:
        raise CompileCacheError(
            f"on-disk receipt failed schema validation: {exc}",
            code="ambiguous_invalidation",
        ) from exc
    return raw
