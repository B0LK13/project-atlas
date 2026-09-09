"""Receipt storage under the Atlas 3 ops namespace (ULT-01b-1).

Layout: ``generated/ops/atlas3/observation/v1/<project>/<identity_digest16>.json``
— a sibling of proof v2, using the same shared locator rules: every path
component is ``lstat``-checked on the unresolved path (symlinks and junctions
refused), containment is re-checked after resolution, and a locator that
already holds a different full ``identity_digest`` is never overwritten.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Final

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


def receipt_locator(project_id: str, identity_digest: str) -> Path:
    return OBSERVATION_RELATIVE / project_id / f"{identity_digest[:16]}.json"


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
        )
    except Atlas3Error as exc:
        raise ObservationError(exc.code, str(exc)) from exc


def load_stored_receipt(
    vault: Path | str, project_id: str, identity_digest: str
) -> ObservationReceipt | None:
    """Strictly load a stored receipt by locator; ``None`` if absent, error if malformed."""
    root = require_vault(vault)
    pid = require_project(root, project_id)
    path = root / receipt_locator(pid, identity_digest)
    raw: dict[str, Any] | None = read_json(path)
    if raw is None:
        return None
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
