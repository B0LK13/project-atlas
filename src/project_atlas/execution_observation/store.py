"""Receipt storage under the Atlas 3 ops namespace (ULT-01b-1).

Layout: ``generated/ops/atlas3/observation/v1/<project>/<identity_digest16>.json``
— a sibling of proof v2, using the same shared locator rules: every path
component is ``lstat``-checked on the unresolved path (symlinks and junctions
refused), containment is re-checked after resolution, and a locator that
already holds a different full ``identity_digest`` is never overwritten.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Final

from atlas_contracts.identity import safe_relative_component
from atlas_contracts.observation_receipt import ObservationReceipt, load_observation_receipt
from project_atlas.atlas3.contracts import (
    OPS_RELATIVE,
    Atlas3Error,
    read_json,
    require_project,
    require_vault,
    write_locator_json,
)
from project_atlas.execution_observation.runner import ObservationError

OBSERVATION_RELATIVE: Final[Path] = OPS_RELATIVE / "observation" / "v1"


_DIGEST_RE: Final[re.Pattern[str]] = re.compile(r"^[0-9a-f]{64}$")


def _safe_digest(identity_digest: str) -> str:
    if not isinstance(identity_digest, str) or not _DIGEST_RE.fullmatch(identity_digest):
        raise ObservationError("OBSERVATION_DIGEST_INVALID", "identity digest must be 64-hex")
    return identity_digest


def receipt_locator(project_id: str, identity_digest: str) -> Path:
    pid = safe_relative_component(project_id, label="project id")
    digest = _safe_digest(identity_digest)
    return OBSERVATION_RELATIVE / pid / f"{digest[:16]}.json"


def store_observation_receipt(vault: Path | str, receipt: ObservationReceipt) -> Path:
    """Write the receipt content-addressed under the vault; refuse unsafe locators."""
    root = require_vault(vault)
    pid = require_project(root, receipt.project_id)
    locator = receipt_locator(pid, receipt.identity_digest)
    try:
        return write_locator_json(
            root,
            locator,
            receipt.to_record(),
            namespace=OBSERVATION_RELATIVE,
            identity_field="identity_digest",
            identity_value=receipt.identity_digest,
            code_unsafe="OBSERVATION_LOCATOR_UNSAFE",
            code_collision="OBSERVATION_LOCATOR_COLLISION",
            code_escape="OBSERVATION_LOCATOR_ESCAPE",
            content_field="content_hash",
        )
    except Atlas3Error as exc:
        raise ObservationError(exc.code, str(exc)) from exc


def load_stored_receipt(
    vault: Path | str, project_id: str, identity_digest: str
) -> ObservationReceipt | None:
    """Strictly load a stored receipt by locator.

    ``None`` if absent; an error if the file exists but is unreadable or malformed.
    """
    root = require_vault(vault)
    pid = require_project(root, project_id)
    path = root / receipt_locator(pid, identity_digest)
    if not path.exists():
        return None
    raw: dict[str, Any] | None = read_json(path)
    if raw is None:
        raise ObservationError(
            "OBSERVATION_RECEIPT_UNREADABLE", "stored receipt exists but is not readable JSON"
        )
    receipt = load_observation_receipt(raw)
    if receipt.identity_digest != identity_digest:
        raise ObservationError(
            "OBSERVATION_LOCATOR_COLLISION", "stored receipt holds a different identity digest"
        )
    return receipt


__all__ = [
    "OBSERVATION_RELATIVE",
    "load_stored_receipt",
    "receipt_locator",
    "store_observation_receipt",
]
