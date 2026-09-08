"""Conservative evidence cache (D-009).

Avoids rerunning unchanged subsystem evidence while never weakening exact-head
certification. Reuse is a classification over stored records, never a mutation
of gate semantics (D-008 identity invariant stands untouched).

Never-weakening rule: after any head move, candidate-wide exact-head CI,
whole-candidate formal IV, and whole-candidate native certification are NEVER
reusable as certification — they demote to PREDECESSOR_SUPPORTING (history
only). Subsystem evidence may be reused after a head move ONLY with an explicit
equivalence proof for its covered contract; absence of file overlap is not
proof. Unknown/missing record fields or failed negative controls are INVALID
(fail closed); unverifiable live head/tree is UNKNOWN (fail closed).
"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any, Callable

from .events import validator_for

EVIDENCE_SCHEMA = "atlas_evidence_v1.schema.json"
STORE_SCHEMA = "ATLAS_EVIDENCE_STORE_V1"

EXACT_HEAD_ONLY = "EXACT_HEAD_ONLY"
REUSABLE_SUBSYSTEM = "REUSABLE_SUBSYSTEM"
PREDECESSOR_SUPPORTING = "PREDECESSOR_SUPPORTING"
INVALID = "INVALID"
UNKNOWN = "UNKNOWN"

REQUIRED_FIELDS = (
    "evidence_id",
    "producer",
    "pr",
    "head",
    "tree",
    "environment",
    "covered_files",
    "covered_contract",
    "result",
    "negative_control",
    "scope",
    "created_at_utc",
)

PROOF_RESULTS = frozenset({"PROVEN", "PASS", "VERIFIED"})

EquivalenceProof = Callable[[dict, str | None, str | None], bool] | dict | None


def normalize(record: dict) -> dict:
    """Canonical form for storage: covered_files sorted and deduplicated."""
    normalized = dict(record)
    normalized["covered_files"] = sorted({str(f) for f in record.get("covered_files", [])})
    return normalized


def _malformed_reasons(record: Any) -> list[str]:
    if not isinstance(record, dict):
        return ["MALFORMED_RECORD:not-an-object"]
    missing = [
        field for field in REQUIRED_FIELDS
        if record.get(field) is None or record.get(field) == ""
        or (field == "covered_files" and not record.get(field))
    ]
    reasons = [f"MISSING_FIELD:{field}" for field in missing]
    scope = str(record.get("scope", "")).upper()
    if record.get("scope") is not None and scope not in ("CANDIDATE_WIDE", "SUBSYSTEM"):
        reasons.append(f"UNKNOWN_SCOPE:{record['scope']}")
    return reasons


def _proof_accepts(proof: EquivalenceProof, record: dict,
                   current_head: str | None, current_tree: str | None) -> bool:
    """An equivalence proof must attest THIS record's covered contract."""
    if proof is None:
        return False
    if callable(proof):
        try:
            return bool(proof(record, current_head, current_tree))
        except Exception:
            return False  # a crashing proof proves nothing
    if isinstance(proof, dict):
        if str(proof.get("result", "")).upper() not in PROOF_RESULTS:
            return False
        declared = proof.get("covered_contract")
        if declared is not None and declared != record.get("covered_contract"):
            return False
        return True
    return False


def classify(record: dict, current_head: str | None, current_tree: str | None,
             equivalence_proof: EquivalenceProof = None) -> tuple[str, list[str]]:
    """Classify a stored record against the live (head, tree) candidate.

    Returns (reuse_class, sorted reasons). Never certifies from stale heads:
    any mismatch demotes candidate-wide evidence to PREDECESSOR_SUPPORTING and
    demands an explicit equivalence proof for subsystem evidence.
    """
    malformed = _malformed_reasons(record)
    if malformed:
        return INVALID, sorted(malformed)
    if str(record["negative_control"]).upper() == "FAIL":
        return INVALID, ["NEGATIVE_CONTROL_FAILED"]
    if not current_head or not current_tree:
        return UNKNOWN, ["CURRENT_HEAD_TREE_UNKNOWN"]

    if record["head"] == current_head and record["tree"] == current_tree:
        return EXACT_HEAD_ONLY, ["HEAD_AND_TREE_MATCH"]

    reasons = []
    if record["head"] != current_head:
        reasons.append("HEAD_MISMATCH")
    if record["tree"] != current_tree:
        reasons.append("TREE_MISMATCH")

    if str(record["scope"]).upper() == "SUBSYSTEM":
        if _proof_accepts(equivalence_proof, record, current_head, current_tree):
            return REUSABLE_SUBSYSTEM, sorted(reasons + ["EQUIVALENCE_PROOF_ACCEPTED"])
        reasons.append("SUBSYSTEM_REUSE_REQUIRES_EQUIVALENCE_PROOF")
    return PREDECESSOR_SUPPORTING, sorted(reasons)


class EvidenceStore:
    """Small append-only evidence store; one JSON file, atomic rewrite.

    Ingestion is idempotent on evidence_id: the first record wins, re-ingesting
    the same evidence_id changes nothing. Records are written in a
    deterministic order with sorted keys, so equal logical content yields
    byte-identical files.
    """

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)

    def load(self) -> list[dict]:
        if not self.path.exists():
            return []
        data = json.loads(self.path.read_text(encoding="utf-8"))
        if isinstance(data, dict) and isinstance(data.get("records"), list):
            return [r for r in data["records"] if isinstance(r, dict)]
        return []

    def for_pr(self, pr: int) -> list[dict]:
        return sorted(
            (r for r in self.load() if r.get("pr") == pr),
            key=lambda r: (r.get("created_at_utc", ""), r.get("evidence_id", "")),
        )

    def ingest(self, record: dict) -> tuple[bool, list[dict]]:
        """Append one normalized record. Returns (added, all records)."""
        records = self.load()
        evidence_id = record.get("evidence_id")
        if any(r.get("evidence_id") == evidence_id for r in records):
            return False, records  # idempotent: first record wins
        records.append(normalize(record))
        self.save(records)
        return True, records

    def save(self, records: list[dict]) -> None:
        ordered = sorted(
            records,
            key=lambda r: (r.get("pr") or 0, r.get("created_at_utc", ""),
                           r.get("evidence_id", "")),
        )
        payload = json.dumps(
            {"schema": STORE_SCHEMA, "records": ordered}, indent=2, sort_keys=True
        ) + "\n"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=self.path.parent, prefix=".evidence-", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(payload)
            os.replace(tmp, self.path)
        except BaseException:
            if os.path.exists(tmp):
                os.unlink(tmp)
            raise


def validate_record(record: Any) -> list[str]:
    """Schema-validation error summaries for one candidate record ([] = valid)."""
    validator = validator_for(EVIDENCE_SCHEMA)
    return sorted(
        (f"{'/'.join(map(str, e.path)) or '<root>'}: {e.message}"
         for e in validator.iter_errors(record)),
    )
