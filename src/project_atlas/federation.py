"""AS-2.0-FED-001 — operator-declared federation join inventory.

Consume-only multi-vault membership. No directory crawl as consent, no
cross-vault promote, no implicit merge. Bound to the 1.0 compatibility anchor.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from project_atlas.compat_anchor import (
    SNAPSHOT_ID,
    CompatibilityAnchor,
    require_compatibility_anchor,
)
from project_atlas.schema import SchemaValidationError, validate_record

PACKAGE_ID = "AS-2.0-FED-001"
_ID_RE = re.compile(r"^[a-z][a-z0-9-]{0,63}$")


class FederationError(ValueError):
    """Fail-closed federation error."""


@dataclass(frozen=True, slots=True)
class FederationMember:
    member_id: str
    vault_root: str
    role: Literal["primary", "member"]
    project_id: str | None = None

    def as_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "member_id": self.member_id,
            "vault_root": self.vault_root,
            "role": self.role,
        }
        if self.project_id:
            payload["project_id"] = self.project_id
        return payload


def _validate_id(token: str, *, label: str) -> str:
    value = token.strip()
    if not _ID_RE.fullmatch(value):
        raise FederationError(f"federation-{label}-invalid")
    return value


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    tmp.replace(path)


def build_join_inventory(
    *,
    federation_id: str,
    members: list[FederationMember],
    output_vault: Path,
    anchor: CompatibilityAnchor | None = None,
) -> dict[str, Any]:
    """Build a deterministic federation join inventory from explicit members."""
    _ = anchor or require_compatibility_anchor()
    fed_id = _validate_id(federation_id, label="id")
    if not members:
        raise FederationError("federation-members-empty")

    seen_ids: set[str] = set()
    seen_roots: set[str] = set()
    primaries = 0
    normalized: list[FederationMember] = []
    for member in members:
        mid = _validate_id(member.member_id, label="member-id")
        root = str(Path(member.vault_root).expanduser())
        if mid in seen_ids:
            raise FederationError(f"federation-member-id-duplicate:{mid}")
        if root in seen_roots:
            raise FederationError(f"federation-vault-root-duplicate:{root}")
        seen_ids.add(mid)
        seen_roots.add(root)
        if member.role == "primary":
            primaries += 1
        project_id = None
        if member.project_id:
            project_id = member.project_id.strip()
            if not project_id:
                raise FederationError("federation-project-id-empty")
        normalized.append(
            FederationMember(
                member_id=mid,
                vault_root=root,
                role=member.role,
                project_id=project_id,
            )
        )

    status: Literal["joined", "refused"] = "joined"
    refusal: str | None = None
    if primaries != 1:
        status = "refused"
        refusal = "federation-primary-count-invalid"

    # Fail closed on missing vault roots (no invent).
    if status == "joined":
        for member in normalized:
            if not Path(member.vault_root).is_dir():
                status = "refused"
                refusal = f"federation-vault-missing:{member.member_id}"
                break

    payload: dict[str, Any] = {
        "schema_version": 1,
        "package_id": PACKAGE_ID,
        "compat_snapshot_id": SNAPSHOT_ID,
        "federation_id": fed_id,
        "members": [item.as_dict() for item in sorted(normalized, key=lambda m: m.member_id)],
        "status": status,
        "authority": {
            "level": "derived",
            "note": "Federation inventory is consume-only; no cross-vault promote",
        },
        "truth_boundary": "FEDERATION JOIN ≠ CROSS-VAULT AUTHORITY",
        "generated": {"by": "project-atlas"},
    }
    if refusal:
        payload["refusal_reason"] = refusal

    try:
        validate_record(payload, "federation-join-inventory")
    except SchemaValidationError as exc:
        raise FederationError(f"federation-schema:{exc}") from exc

    out = (
        output_vault.resolve()
        / "generated"
        / "federation"
        / f"{fed_id}-join-inventory.json"
    )
    _atomic_write_json(out, payload)
    return payload
