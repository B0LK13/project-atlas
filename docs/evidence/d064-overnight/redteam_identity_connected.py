#!/usr/bin/env python3
"""D-049 overnight red-team: identity matrix + CONNECTED bind proof.

Attacks ``project_atlas.estate_discovery`` via temp dirs only.
Does not modify ``src/project_atlas/**``.

Frozen tip reference: 9c71cc2c71779678f79037c0c279390355015d63
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import traceback
from pathlib import Path
from typing import Any

from project_atlas.estate_discovery import (
    VaultProjectIdentity,
    discover_estate,
    load_vault_project_identities,
    match_fingerprint,
    prove_connected,
)

OUT_PATH = Path(__file__).resolve().parent / "identity-connected-results.json"

ALPHA_UUID = "11111111-1111-4111-8111-111111111111"
BETA_UUID = "22222222-2222-4222-8222-222222222222"
OTHER_UUID = "33333333-3333-4333-8333-333333333333"
INVALID_UUID = "not-a-valid-uuid-at-all"


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _allocation(vault: Path, project_id: str, project_uuid: str) -> None:
    """Durable allocation receipt under vault/receipts/source-lineage/."""
    path = (
        vault
        / "receipts"
        / "source-lineage"
        / f"project-{project_id}-allocation.json"
    )
    _write(
        path,
        json.dumps(
            {
                "schema_version": 1,
                "receipt_type": "project-identity-allocation",
                "project": project_id,
                "project_uuid": project_uuid,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
    )


def _vault_with_project(
    root: Path, project_id: str, project_uuid: str | None
) -> Path:
    vault = root / "vault"
    (vault / "projects" / project_id).mkdir(parents=True)
    if project_uuid is not None:
        _allocation(vault, project_id, project_uuid)
    return vault


def _marker(project_id: str | None, project_uuid: str | None) -> str:
    lines = ["project:"]
    if project_id is not None:
        lines.append(f"  id: {project_id}")
    else:
        lines.append("  id:")
    if project_uuid is not None:
        lines.append(f"project_uuid: {project_uuid}")
    return "\n".join(lines) + "\n"


def _bind(project_root: Path, vault: Path, project_id: str) -> None:
    _write(
        project_root / ".atlas" / "connect.json",
        json.dumps(
            {
                "schema_version": 1,
                "schema": "atlas.connect.bind.v1",
                "project_root": str(project_root.resolve()),
                "vault": str(vault.resolve()),
                "project_id": project_id,
                "project_ids": [project_id],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
    )


def _evidence_kinds(rows: list[Any]) -> set[str]:
    kinds: set[str] = set()
    for row in rows:
        kind = getattr(row, "kind", None)
        if kind is None and isinstance(row, dict):
            kind = row.get("kind")
        if isinstance(kind, str):
            kinds.add(kind)
    return kinds


class Scoreboard:
    def __init__(self) -> None:
        self.SILENT_IDENTITY_MERGES = 0
        self.FALSE_EXACT_MATCHES = 0
        self.FALSE_CONNECTED_MATCHES = 0
        self.PROJECT_UUID_COALESCING = 0
        self.CROSS_PROJECT_LEAKS = 0
        self.CONNECTED_WITHOUT_DURABLE_BIND_PROOF = 0
        self.cases: list[dict[str, Any]] = []
        self.HIGH_FINDINGS: list[str] = []

    def add_high(self, msg: str) -> None:
        self.HIGH_FINDINGS.append(msg)

    def record(self, name: str, passed: bool, detail: str) -> None:
        self.cases.append({"name": name, "pass": passed, "detail": detail})

    def hard_counters(self) -> dict[str, int]:
        return {
            "SILENT_IDENTITY_MERGES": self.SILENT_IDENTITY_MERGES,
            "FALSE_EXACT_MATCHES": self.FALSE_EXACT_MATCHES,
            "FALSE_CONNECTED_MATCHES": self.FALSE_CONNECTED_MATCHES,
            "PROJECT_UUID_COALESCING": self.PROJECT_UUID_COALESCING,
            "CROSS_PROJECT_LEAKS": self.CROSS_PROJECT_LEAKS,
            "CONNECTED_WITHOUT_DURABLE_BIND_PROOF": (
                self.CONNECTED_WITHOUT_DURABLE_BIND_PROOF
            ),
        }

    def summary(self) -> dict[str, Any]:
        out = self.hard_counters()
        out["cases"] = self.cases
        out["HIGH_FINDINGS"] = list(self.HIGH_FINDINGS)
        return out


def case_01_same_id_same_uuid_exact_not_connected(sb: Scoreboard, tmp: Path) -> None:
    name = "01_same_id_same_uuid_exact_not_connected_without_bind"
    vault_ids = [VaultProjectIdentity("alpha", ALPHA_UUID)]
    state, evidence, conflicts, mid, muuid = match_fingerprint(
        {
            "atlas_project_id": "alpha",
            "atlas_project_uuid": ALPHA_UUID,
            "marker_status": "ok",
            "uuid_status": "ok",
        },
        vault_ids,
    )
    connected, why = prove_connected(
        tmp / "elsewhere-alpha", "alpha", state, vault_ids
    )

    # End-to-end: EXACT match without connect.json must not be CONNECTED.
    estate = tmp / "estate"
    alpha = estate / "alpha"
    _write(alpha / ".atlas-project.yaml", _marker("alpha", ALPHA_UUID))
    _write(alpha / "README.md", "# alpha\n")
    (alpha / ".git").mkdir(parents=True)
    vault = _vault_with_project(tmp, "alpha", ALPHA_UUID)
    report = discover_estate(estate, vault=vault, include_knowledge=False)
    projects = report["candidates"]["projects"]
    row = next(p for p in projects if Path(p["path"]).name == "alpha")

    ok = (
        state == "EXACT"
        and mid == "alpha"
        and muuid == ALPHA_UUID
        and connected is False
        and row["match_state"] == "EXACT"
        and row["category"] != "CONNECTED"
        and row["lifecycle"] != "CONNECTED"
        and not row.get("why_connected")
    )
    detail = (
        f"match={state} mid={mid} prove_connected={connected} why={why!r}; "
        f"discover category={row['category']} lifecycle={row['lifecycle']} "
        f"match_state={row['match_state']}"
    )
    if connected or row["category"] == "CONNECTED" or row["lifecycle"] == "CONNECTED":
        sb.FALSE_CONNECTED_MATCHES += 1
        sb.CONNECTED_WITHOUT_DURABLE_BIND_PROOF += 1
        sb.add_high(
            f"{name}: CONNECTED without durable bind proof "
            f"(prove={connected}, category={row['category']})"
        )
    if state != "EXACT" and state not in {"CONFLICTING"}:
        pass  # false negative — record in detail only
    if state != "EXACT":
        sb.add_high(f"{name}: expected EXACT, got {state} conflicts={conflicts}")
        ok = False
    sb.record(name, ok, detail)


def case_02_same_id_different_uuid(sb: Scoreboard, tmp: Path) -> None:
    name = "02_same_id_different_uuid_conflicting"
    vault_ids = [VaultProjectIdentity("alpha", ALPHA_UUID)]
    state, _, conflicts, mid, _ = match_fingerprint(
        {
            "atlas_project_id": "alpha",
            "atlas_project_uuid": OTHER_UUID,
            "marker_status": "ok",
            "uuid_status": "ok",
        },
        vault_ids,
    )
    kinds = _evidence_kinds(conflicts)
    estate = tmp / "estate"
    alpha = estate / "alpha"
    _write(alpha / ".atlas-project.yaml", _marker("alpha", OTHER_UUID))
    _write(alpha / "README.md", "# alpha\n")
    (alpha / ".git").mkdir(parents=True)
    vault = _vault_with_project(tmp, "alpha", ALPHA_UUID)
    report = discover_estate(estate, vault=vault, include_knowledge=False)
    row = report["candidates"]["projects"][0]

    ok = (
        state == "CONFLICTING"
        and "same_id_different_uuid" in kinds
        and mid is None
        and row["match_state"] == "CONFLICTING"
        and row["category"] != "CONNECTED"
    )
    detail = (
        f"match={state} kinds={sorted(kinds)} discover={row['match_state']} "
        f"category={row['category']} matched_uuid={row.get('matched_project_uuid')}"
    )
    if state == "EXACT" or row["match_state"] == "EXACT":
        sb.FALSE_EXACT_MATCHES += 1
        sb.SILENT_IDENTITY_MERGES += 1
        sb.PROJECT_UUID_COALESCING += 1
        sb.add_high(f"{name}: same id/different uuid silently EXACT")
        ok = False
    if state != "CONFLICTING":
        sb.add_high(f"{name}: expected CONFLICTING, got {state}")
        ok = False
    sb.record(name, ok, detail)


def case_03_different_id_same_uuid(sb: Scoreboard, tmp: Path) -> None:
    name = "03_different_id_same_uuid_conflicting"
    vault_ids = [
        VaultProjectIdentity("alpha", ALPHA_UUID),
        VaultProjectIdentity("beta", BETA_UUID),
    ]
    state, _, conflicts, mid, _ = match_fingerprint(
        {
            "atlas_project_id": "beta",
            "atlas_project_uuid": ALPHA_UUID,
            "marker_status": "ok",
            "uuid_status": "ok",
        },
        vault_ids,
    )
    kinds = _evidence_kinds(conflicts)

    estate = tmp / "estate"
    impostor = estate / "impostor"
    _write(impostor / ".atlas-project.yaml", _marker("impostor", ALPHA_UUID))
    _write(impostor / "README.md", "# impostor\n")
    (impostor / ".git").mkdir(parents=True)
    vault = _vault_with_project(tmp, "alpha", ALPHA_UUID)
    report = discover_estate(estate, vault=vault, include_knowledge=False)
    row = report["candidates"]["projects"][0]

    ok = (
        state == "CONFLICTING"
        and "different_id_same_uuid" in kinds
        and mid is None
        and row["match_state"] == "CONFLICTING"
    )
    detail = (
        f"match={state} kinds={sorted(kinds)} discover={row['match_state']} "
        f"matched_id={row.get('matched_project_id')}"
    )
    if state == "EXACT" or row["match_state"] == "EXACT":
        sb.FALSE_EXACT_MATCHES += 1
        sb.CROSS_PROJECT_LEAKS += 1
        sb.PROJECT_UUID_COALESCING += 1
        sb.SILENT_IDENTITY_MERGES += 1
        sb.add_high(f"{name}: different id/same uuid silently EXACT / coalesced")
        ok = False
    if state != "CONFLICTING":
        sb.add_high(f"{name}: expected CONFLICTING, got {state}")
        ok = False
    sb.record(name, ok, detail)


def case_04_missing_uuid_matching_id(sb: Scoreboard, tmp: Path) -> None:
    name = "04_missing_uuid_matching_id_exact_uuid_absent"
    vault_ids = [VaultProjectIdentity("alpha", ALPHA_UUID)]
    state, evidence, _, mid, _ = match_fingerprint(
        {
            "atlas_project_id": "alpha",
            "atlas_project_uuid": None,
            "marker_status": "ok",
            "uuid_status": "absent",
        },
        vault_ids,
    )
    kinds = _evidence_kinds(evidence)
    connected, _ = prove_connected(tmp / "no-bind", "alpha", state, vault_ids)

    estate = tmp / "estate"
    alpha = estate / "alpha"
    _write(alpha / ".atlas-project.yaml", "project:\n  id: alpha\n")
    _write(alpha / "README.md", "# alpha\n")
    (alpha / ".git").mkdir(parents=True)
    vault = _vault_with_project(tmp, "alpha", ALPHA_UUID)
    report = discover_estate(estate, vault=vault, include_knowledge=False)
    row = report["candidates"]["projects"][0]
    disc_kinds = _evidence_kinds(row.get("match_evidence") or [])

    ok = (
        state == "EXACT"
        and "uuid_absent" in kinds
        and mid == "alpha"
        and connected is False
        and row["match_state"] == "EXACT"
        and "uuid_absent" in disc_kinds
        and row["category"] != "CONNECTED"
    )
    detail = (
        f"match={state} evidence={sorted(kinds)} prove_connected={connected}; "
        f"discover evidence={sorted(disc_kinds)} category={row['category']}"
    )
    if connected or row["category"] == "CONNECTED":
        sb.FALSE_CONNECTED_MATCHES += 1
        sb.CONNECTED_WITHOUT_DURABLE_BIND_PROOF += 1
        sb.add_high(f"{name}: CONNECTED without bind on uuid-absent EXACT")
        ok = False
    if state != "EXACT" or "uuid_absent" not in kinds:
        sb.add_high(
            f"{name}: expected EXACT with uuid_absent, got {state} "
            f"evidence={sorted(kinds)}"
        )
        ok = False
    sb.record(name, ok, detail)


def case_05_invalid_uuid(sb: Scoreboard, tmp: Path) -> None:
    name = "05_invalid_uuid_conflicting_not_silent_absent"
    vault_ids = [VaultProjectIdentity("alpha", ALPHA_UUID)]
    state, _, conflicts, _, _ = match_fingerprint(
        {
            "atlas_project_id": "alpha",
            "atlas_project_uuid": None,
            "marker_status": "ok",
            "uuid_status": "invalid",
        },
        vault_ids,
    )
    kinds = _evidence_kinds(conflicts)

    estate = tmp / "estate"
    alpha = estate / "alpha"
    _write(alpha / ".atlas-project.yaml", _marker("alpha", INVALID_UUID))
    _write(alpha / "README.md", "# alpha\n")
    (alpha / ".git").mkdir(parents=True)
    vault = _vault_with_project(tmp, "alpha", ALPHA_UUID)
    report = discover_estate(estate, vault=vault, include_knowledge=False)
    row = report["candidates"]["projects"][0]
    fp = row.get("fingerprint") or {}

    ok = (
        state == "CONFLICTING"
        and "invalid_project_uuid" in kinds
        and row["match_state"] == "CONFLICTING"
        and fp.get("uuid_status") == "invalid"
        and row["match_state"] != "EXACT"
    )
    detail = (
        f"match={state} kinds={sorted(kinds)} discover={row['match_state']} "
        f"uuid_status={fp.get('uuid_status')}"
    )
    if state == "EXACT" or row["match_state"] == "EXACT":
        sb.FALSE_EXACT_MATCHES += 1
        sb.SILENT_IDENTITY_MERGES += 1
        sb.add_high(f"{name}: invalid uuid treated as absent → EXACT")
        ok = False
    if fp.get("uuid_status") == "absent":
        sb.SILENT_IDENTITY_MERGES += 1
        sb.add_high(f"{name}: invalid uuid silently coerced to absent")
        ok = False
    if state != "CONFLICTING":
        sb.add_high(f"{name}: expected CONFLICTING, got {state}")
        ok = False
    sb.record(name, ok, detail)


def case_06_copied_marker_never_connected(sb: Scoreboard, tmp: Path) -> None:
    name = "06_copied_marker_unrelated_root_never_connected"
    estate = tmp / "estate"
    owner = estate / "owner"
    copy = estate / "unrelated-copy"
    for root in (owner, copy):
        _write(root / ".atlas-project.yaml", _marker("alpha", ALPHA_UUID))
        _write(root / "README.md", "# x\n")
        (root / ".git").mkdir(parents=True)
    vault = _vault_with_project(tmp, "alpha", ALPHA_UUID)
    # Bind only owner — not the copy.
    _bind(owner, vault, "alpha")

    report = discover_estate(estate, vault=vault, include_knowledge=False)
    by_name = {Path(p["path"]).name: p for p in report["candidates"]["projects"]}
    copy_row = by_name["unrelated-copy"]
    owner_row = by_name["owner"]

    copy_connected = (
        copy_row["category"] == "CONNECTED"
        or copy_row["lifecycle"] == "CONNECTED"
        or bool(copy_row.get("why_connected"))
    )
    # prove_connected on copy path with EXACT vault identity lacking bind_root
    # for that path should fail.
    identities = load_vault_project_identities(vault, authorized_root=estate)
    prove_ok, prove_why = prove_connected(
        copy.resolve(),
        "alpha",
        "EXACT",
        identities,
        vault=vault,
    )

    ok = (
        not copy_connected
        and prove_ok is False
        and owner_row["category"] == "CONNECTED"
        and bool(owner_row.get("why_connected"))
    )
    detail = (
        f"copy category={copy_row['category']} lifecycle={copy_row['lifecycle']} "
        f"match={copy_row['match_state']} prove={prove_ok} why={prove_why!r}; "
        f"owner category={owner_row['category']} why_connected={owner_row.get('why_connected')}"
    )
    if copy_connected or prove_ok:
        sb.FALSE_CONNECTED_MATCHES += 1
        sb.CONNECTED_WITHOUT_DURABLE_BIND_PROOF += 1
        sb.CROSS_PROJECT_LEAKS += 1
        sb.add_high(
            f"{name}: copied marker CONNECTED without bind for that root "
            f"(category={copy_row['category']}, prove={prove_ok})"
        )
        ok = False
    sb.record(name, ok, detail)


def case_07_live_bind_connected(sb: Scoreboard, tmp: Path) -> None:
    name = "07_live_connect_json_bind_connected_with_why"
    estate = tmp / "estate"
    alpha = estate / "alpha"
    _write(alpha / ".atlas-project.yaml", _marker("alpha", ALPHA_UUID))
    _write(alpha / "README.md", "# alpha\n")
    (alpha / ".git").mkdir(parents=True)
    vault = _vault_with_project(tmp, "alpha", ALPHA_UUID)
    _bind(alpha, vault, "alpha")

    report = discover_estate(estate, vault=vault, include_knowledge=False)
    row = report["candidates"]["projects"][0]
    why = row.get("why_connected") or []
    identities = load_vault_project_identities(vault, authorized_root=estate)
    prove_ok, prove_why = prove_connected(
        alpha.resolve(),
        row.get("matched_project_id") or "alpha",
        row["match_state"],
        identities,
        vault=vault,
    )

    ok = (
        row["category"] == "CONNECTED"
        and row["lifecycle"] == "CONNECTED"
        and bool(why)
        and prove_ok is True
        and bool(prove_why)
        and any("bind" in w.casefold() or "ownership" in w.casefold() for w in why)
    )
    detail = (
        f"category={row['category']} lifecycle={row['lifecycle']} "
        f"match={row['match_state']} why_connected={why} "
        f"prove={prove_ok} prove_why={prove_why}"
    )
    if not ok:
        # False negative of CONNECTED is not a hard counter elevation by itself,
        # but it is a case failure for the red-team matrix.
        sb.add_high(
            f"{name}: expected CONNECTED with why_connected bind proof; "
            f"got category={row['category']} why={why}"
        )
    sb.record(name, ok, detail)


def case_08_same_basename_distinct_candidate_ids(sb: Scoreboard, tmp: Path) -> None:
    name = "08_same_basename_different_roots_distinct_candidate_ids"
    estate = tmp / "estate"
    one = estate / "shared-name"
    two = estate / "other" / "shared-name"
    for root in (one, two):
        _write(root / "README.md", "# x\n")
        _write(root / "package.json", '{"name":"shared-name"}\n')
        (root / "src").mkdir(parents=True)
        (root / ".git").mkdir(parents=True)
    vault = tmp / "vault"
    (vault / "projects" / "shared-name").mkdir(parents=True)

    report = discover_estate(estate, vault=vault, include_knowledge=False)
    projects = [
        p
        for p in report["candidates"]["projects"]
        if Path(p["path"]).name == "shared-name"
    ]
    ids = {p["candidate_id"] for p in projects}
    uuids = {p.get("matched_project_uuid") for p in projects}

    ok = len(projects) >= 2 and len(ids) >= 2
    detail = f"n={len(projects)} candidate_ids={sorted(ids)} matched_uuids={uuids}"
    if len(ids) < 2 and len(projects) >= 2:
        sb.SILENT_IDENTITY_MERGES += 1
        sb.PROJECT_UUID_COALESCING += 1
        sb.add_high(f"{name}: same basename coalesced to one candidate_id: {ids}")
        ok = False
    if not ok:
        sb.add_high(f"{name}: expected ≥2 distinct candidate_ids, got {detail}")
    sb.record(name, ok, detail)


def case_09_package_name_only_not_exact(sb: Scoreboard, tmp: Path) -> None:
    name = "09_same_package_name_only_not_exact"
    state, evidence, _, mid, _ = match_fingerprint(
        {
            "package_name": "svc-app",
            "marker_status": "absent",
            "uuid_status": "absent",
        },
        [VaultProjectIdentity("svc-app", None)],
    )
    # Also end-to-end: package name alone with vault project id alignment.
    estate = tmp / "estate"
    cand = estate / "somewhere"
    _write(cand / "README.md", "# x\n")
    _write(cand / "package.json", '{"name":"svc-app"}\n')
    (cand / "src").mkdir(parents=True)
    vault = tmp / "vault"
    (vault / "projects" / "svc-app").mkdir(parents=True)
    # No bind — package name may yield LIKELY/STRONG via id alignment, never EXACT.
    report = discover_estate(estate, vault=vault, include_knowledge=False)
    row = report["candidates"]["projects"][0] if report["candidates"]["projects"] else {}

    ok = state != "EXACT" and row.get("match_state") != "EXACT"
    detail = (
        f"fp_match={state} mid={mid} evidence={[e.kind for e in evidence]}; "
        f"discover_match={row.get('match_state')}"
    )
    if state == "EXACT" or row.get("match_state") == "EXACT":
        sb.FALSE_EXACT_MATCHES += 1
        sb.SILENT_IDENTITY_MERGES += 1
        sb.add_high(f"{name}: package name only produced EXACT")
        ok = False
    sb.record(name, ok, detail)


def case_10_directory_name_only_likely(sb: Scoreboard, tmp: Path) -> None:
    name = "10_directory_name_only_likely_not_exact"
    state, evidence, _, mid, _ = match_fingerprint(
        {
            "directory_name": "svc-app",
            "marker_status": "absent",
            "uuid_status": "absent",
        },
        [VaultProjectIdentity("svc-app", None)],
    )
    estate = tmp / "estate"
    cand = estate / "svc-app"
    _write(cand / "README.md", "# x\n")
    (cand / ".git").mkdir(parents=True)
    vault = tmp / "vault"
    (vault / "projects" / "svc-app").mkdir(parents=True)
    report = discover_estate(estate, vault=vault, include_knowledge=False)
    row = next(
        p for p in report["candidates"]["projects"] if Path(p["path"]).name == "svc-app"
    )

    ok = state == "LIKELY" and state != "EXACT" and row["match_state"] != "EXACT"
    detail = (
        f"fp_match={state} mid={mid} evidence={[e.kind for e in evidence]}; "
        f"discover_match={row['match_state']} category={row['category']}"
    )
    if state == "EXACT" or row["match_state"] == "EXACT":
        sb.FALSE_EXACT_MATCHES += 1
        sb.SILENT_IDENTITY_MERGES += 1
        sb.add_high(f"{name}: directory name only produced EXACT")
        ok = False
    if state not in {"LIKELY", "AMBIGUOUS", "UNMATCHED", "STRONG_EVIDENCE"}:
        sb.add_high(f"{name}: unexpected match_state {state}")
        ok = False
    if state != "LIKELY":
        # Spec: directory name only → LIKELY not EXACT
        ok = False
        sb.add_high(f"{name}: expected LIKELY, got {state}")
    sb.record(name, ok, detail)


def case_11_git_remote_vs_marker_conflict(sb: Scoreboard, tmp: Path) -> None:
    name = "11_git_remote_vs_marker_id_conflict"
    vault_ids = [
        VaultProjectIdentity(
            "alpha",
            ALPHA_UUID,
            git_remote="https://example.com/alpha.git",
            bind_root="/tmp/alpha",
            bind_proven=True,
        ),
        VaultProjectIdentity("beta", BETA_UUID),
    ]
    state, _, conflicts, _, _ = match_fingerprint(
        {
            "atlas_project_id": "beta",
            "atlas_project_uuid": None,
            "marker_status": "ok",
            "uuid_status": "absent",
            "git_remote": "https://example.com/alpha.git",
        },
        vault_ids,
    )
    kinds = _evidence_kinds(conflicts)

    # End-to-end with live bind carrying alpha remote + beta marker.
    estate = tmp / "estate"
    bound = estate / "bound-alpha"
    _write(bound / "README.md", "# alpha bind root\n")
    _write(bound / "pyproject.toml", '[project]\nname = "alpha-app"\n')
    (bound / "src").mkdir(parents=True)
    (bound / ".git").mkdir()
    _write(
        bound / ".git" / "config",
        '[remote "origin"]\n\turl = https://example.com/alpha.git\n',
    )
    beta = estate / "beta-claim"
    _write(beta / ".atlas-project.yaml", "project:\n  id: beta\n")
    _write(beta / "README.md", "# beta\n")
    (beta / ".git").mkdir(parents=True)
    _write(
        beta / ".git" / "config",
        '[remote "origin"]\n\turl = https://example.com/alpha.git\n',
    )
    vault = tmp / "vault"
    (vault / "projects" / "alpha").mkdir(parents=True)
    (vault / "projects" / "beta").mkdir(parents=True)
    _allocation(vault, "alpha", ALPHA_UUID)
    _allocation(vault, "beta", BETA_UUID)
    _bind(bound, vault, "alpha")

    report = discover_estate(estate, vault=vault, include_knowledge=False)
    beta_rows = [
        p for p in report["candidates"]["projects"] if Path(p["path"]).name == "beta-claim"
    ]
    beta_row = beta_rows[0] if beta_rows else {}

    ok = (
        state == "CONFLICTING"
        and "git_remote_vs_marker_id" in kinds
        and beta_row.get("match_state") == "CONFLICTING"
    )
    detail = (
        f"fp_match={state} kinds={sorted(kinds)}; "
        f"discover_beta={beta_row.get('match_state')} "
        f"conflicts={beta_row.get('conflicting_evidence')}"
    )
    if state in {"EXACT", "STRONG_EVIDENCE", "LIKELY"}:
        sb.FALSE_EXACT_MATCHES += 1 if state == "EXACT" else 0
        sb.CROSS_PROJECT_LEAKS += 1
        sb.SILENT_IDENTITY_MERGES += 1
        sb.add_high(f"{name}: git remote vs marker id not CONFLICTING ({state})")
        ok = False
    if state != "CONFLICTING":
        sb.add_high(f"{name}: expected CONFLICTING, got {state}")
        ok = False
    if beta_row and beta_row.get("match_state") != "CONFLICTING":
        sb.CROSS_PROJECT_LEAKS += 1
        sb.add_high(
            f"{name}: discover beta-claim match_state="
            f"{beta_row.get('match_state')} (expected CONFLICTING)"
        )
        ok = False
    sb.record(name, ok, detail)


def case_12_malformed_marker(sb: Scoreboard, tmp: Path) -> None:
    name = "12_malformed_marker_conflicting"
    vault_ids = [VaultProjectIdentity("alpha", ALPHA_UUID)]
    state, _, conflicts, _, _ = match_fingerprint(
        {
            "atlas_project_id": None,
            "directory_name": "alpha",
            "marker_status": "invalid",
            "uuid_status": "absent",
        },
        vault_ids,
    )
    kinds = _evidence_kinds(conflicts)

    estate = tmp / "estate"
    alpha = estate / "alpha"
    # Must be a real YAML parse failure (not a dict that merely lacks project.id).
    _write(alpha / ".atlas-project.yaml", "{{invalid\n")
    _write(alpha / "README.md", "# alpha\n")
    (alpha / ".git").mkdir(parents=True)
    vault = _vault_with_project(tmp, "alpha", ALPHA_UUID)
    report = discover_estate(estate, vault=vault, include_knowledge=False)
    row = report["candidates"]["projects"][0]
    fp = row.get("fingerprint") or {}

    ok = (
        state == "CONFLICTING"
        and any(k.startswith("marker_") for k in kinds)
        and row["match_state"] == "CONFLICTING"
        and fp.get("marker_status") == "invalid"
        and row["match_state"] != "EXACT"
    )
    detail = (
        f"fp_match={state} kinds={sorted(kinds)}; discover={row['match_state']} "
        f"marker_status={fp.get('marker_status')} required_review="
        f"{row.get('required_review')}"
    )
    if state == "EXACT" or row["match_state"] == "EXACT":
        sb.FALSE_EXACT_MATCHES += 1
        sb.SILENT_IDENTITY_MERGES += 1
        sb.add_high(f"{name}: malformed marker produced EXACT via weaker evidence")
        ok = False
    elif row["match_state"] in {"LIKELY", "STRONG_EVIDENCE", "AMBIGUOUS"}:
        # Malformed marker must not fall through to heuristic match.
        sb.SILENT_IDENTITY_MERGES += 1
        sb.add_high(
            f"{name}: malformed marker bypassed to {row['match_state']} "
            f"(marker_status={fp.get('marker_status')})"
        )
        ok = False
    if state != "CONFLICTING":
        sb.add_high(f"{name}: expected CONFLICTING, got {state}")
        ok = False
    if row["match_state"] != "CONFLICTING":
        sb.add_high(
            f"{name}: discover expected CONFLICTING, got {row['match_state']} "
            f"marker_status={fp.get('marker_status')}"
        )
        ok = False
    sb.record(name, ok, detail)


def case_13_unreadable_marker(sb: Scoreboard, tmp: Path) -> None:
    name = "13_unreadable_marker_conflicting_or_required_review"
    estate = tmp / "estate"
    alpha = estate / "alpha"
    marker = alpha / ".atlas-project.yaml"
    _write(marker, _marker("alpha", ALPHA_UUID))
    _write(alpha / "README.md", "# alpha\n")
    (alpha / ".git").mkdir(parents=True)
    vault = _vault_with_project(tmp, "alpha", ALPHA_UUID)

    chmod_ok = False
    try:
        os.chmod(marker, 0o000)
        chmod_ok = True
    except OSError as exc:
        sb.record(
            name,
            False,
            f"chmod 000 failed ({exc}); cannot exercise unreadable path",
        )
        sb.add_high(f"{name}: chmod 000 not possible: {exc}")
        return

    try:
        # Direct fingerprint path via match when marker_status=unreadable.
        state, _, conflicts, _, _ = match_fingerprint(
            {
                "atlas_project_id": None,
                "directory_name": "alpha",
                "marker_status": "unreadable",
                "uuid_status": "absent",
            },
            [VaultProjectIdentity("alpha", ALPHA_UUID)],
        )
        kinds = _evidence_kinds(conflicts)
        report = discover_estate(estate, vault=vault, include_knowledge=False)
        row = report["candidates"]["projects"][0]
        fp = row.get("fingerprint") or {}
        accept = row["match_state"] == "CONFLICTING" or bool(row.get("required_review"))
        ok = (
            state == "CONFLICTING"
            and any(k.startswith("marker_") for k in kinds)
            and accept
            and row["match_state"] != "EXACT"
            and fp.get("marker_status") in {"unreadable", "invalid"}
        )
        detail = (
            f"chmod_ok={chmod_ok} fp_match={state} kinds={sorted(kinds)}; "
            f"discover={row['match_state']} marker_status={fp.get('marker_status')} "
            f"required_review={row.get('required_review')} "
            f"required_action={row.get('required_action')}"
        )
        if row["match_state"] == "EXACT" or state == "EXACT":
            sb.FALSE_EXACT_MATCHES += 1
            sb.SILENT_IDENTITY_MERGES += 1
            sb.add_high(f"{name}: unreadable marker produced EXACT")
            ok = False
        if not accept:
            sb.add_high(
                f"{name}: expected CONFLICTING or required_review, got "
                f"match_state={row['match_state']} "
                f"required_review={row.get('required_review')}"
            )
            ok = False
        sb.record(name, ok, detail)
    finally:
        try:
            os.chmod(marker, 0o644)
        except OSError:
            pass


CASES = [
    case_01_same_id_same_uuid_exact_not_connected,
    case_02_same_id_different_uuid,
    case_03_different_id_same_uuid,
    case_04_missing_uuid_matching_id,
    case_05_invalid_uuid,
    case_06_copied_marker_never_connected,
    case_07_live_bind_connected,
    case_08_same_basename_distinct_candidate_ids,
    case_09_package_name_only_not_exact,
    case_10_directory_name_only_likely,
    case_11_git_remote_vs_marker_conflict,
    case_12_malformed_marker,
    case_13_unreadable_marker,
]


def main() -> int:
    sb = Scoreboard()
    for case_fn in CASES:
        with tempfile.TemporaryDirectory(prefix="d064-rt-id-") as td:
            try:
                case_fn(sb, Path(td))
            except Exception as exc:  # noqa: BLE001 — red-team harness
                sb.record(
                    case_fn.__name__,
                    False,
                    f"EXCEPTION: {exc}\n{traceback.format_exc()}",
                )
                sb.add_high(f"{case_fn.__name__}: exception {exc}")

    summary = sb.summary()
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, indent=2, sort_keys=True))

    hard = sb.hard_counters()
    if any(v > 0 for v in hard.values()) or sb.HIGH_FINDINGS:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
