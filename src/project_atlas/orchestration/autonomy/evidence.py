"""Deterministic reconstructable evidence bundles."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from project_atlas.orchestration.autonomy.models import EvidenceBundle
from project_atlas.orchestration.router import canonical_payload_digest


class EvidenceError(ValueError):
    code = "EVIDENCE_ERROR"


def hash_payload(payload: object) -> str:
    return canonical_payload_digest(payload)


def make_bundle(bundle_kind: str, payload: dict[str, object]) -> EvidenceBundle:
    digest = hash_payload(payload)
    return EvidenceBundle(bundle_kind=bundle_kind, payload_sha256=digest, payload=payload)


def _inside(root: Path, target: Path) -> bool:
    try:
        target.relative_to(root)
    except ValueError:
        return False
    return True


def write_bundle(root: Path, relative_name: str, bundle: EvidenceBundle) -> Path:
    """Atomic write confined to ``root``. No wall-clock fields are emitted."""
    resolved_root = root.resolve()
    if resolved_root.parent == resolved_root or resolved_root == Path.home().resolve():
        raise EvidenceError("evidence root is not a safe writable directory")
    if ".." in Path(relative_name).parts or Path(relative_name).is_absolute():
        raise EvidenceError("evidence relative path is unsafe")
    target = (resolved_root / relative_name).resolve()
    if not _inside(resolved_root, target):
        raise EvidenceError("evidence path escapes root")
    target.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(
        bundle.model_dump(mode="json"),
        sort_keys=True,
        indent=2,
        ensure_ascii=True,
    )
    tmp = target.with_name(f".{target.name}.tmp")
    tmp.write_text(encoded + "\n", encoding="utf-8")
    tmp.replace(target)
    return target


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()
