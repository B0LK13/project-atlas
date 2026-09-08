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
import re
import tempfile
from pathlib import Path
from typing import Any, Callable

from .events import validator_for

if os.name == "nt":
    import msvcrt
else:
    import fcntl

EVIDENCE_SCHEMA = "atlas_evidence_v1.schema.json"
STORE_SCHEMA = "ATLAS_EVIDENCE_STORE_V1"
RECORD_SCHEMA = "ATLAS_EVIDENCE_V1"

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

NEGATIVE_CONTROL_VALUES = ("PASS", "FAIL", "NONE")

_HEX40 = re.compile(r"[0-9a-f]{40}")

EquivalenceProof = Callable[[dict, str | None, str | None], bool] | dict | None


def _lock_exclusive(handle: Any) -> None:
    if os.name == "nt":
        handle.seek(0)
        msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
    else:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)


def _unlock(handle: Any) -> None:
    if os.name == "nt":
        handle.seek(0)
        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
    else:
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


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
    if record.get("schema") is not None and record.get("schema") != RECORD_SCHEMA:
        reasons.append(f"SCHEMA_MISMATCH:{record['schema']}")
    scope = str(record.get("scope", "")).upper()
    if record.get("scope") is not None and scope not in ("CANDIDATE_WIDE", "SUBSYSTEM"):
        reasons.append(f"UNKNOWN_SCOPE:{record['scope']}")
    negative_control = record.get("negative_control")
    if negative_control is not None and \
            str(negative_control).upper() not in NEGATIVE_CONTROL_VALUES:
        reasons.append(f"UNKNOWN_NEGATIVE_CONTROL:{negative_control}")
    for field in ("head", "tree"):
        value = record.get(field)
        if value is not None and value != "" and not _HEX40.fullmatch(str(value)):
            reasons.append(f"MALFORMED_{field.upper()}:{value}")
    pr = record.get("pr")
    if pr is not None and not isinstance(pr, int):
        reasons.append(f"PR_NOT_INTEGER:{pr}")
    return reasons


def _proof_rejection_reason(proof: EquivalenceProof, record: dict,
                            current_head: str | None,
                            current_tree: str | None) -> str | None:
    """Return None if the proof attests THIS record's transition, else a reason.

    A dict proof must be bound to the candidate transition it claims to
    bridge: it has to name the record's covered contract and pin both the
    record's stored head (old_head) and the current candidate head
    (new_head). An unbound or mismatched proof proves nothing.
    """
    if proof is None:
        return "SUBSYSTEM_REUSE_REQUIRES_EQUIVALENCE_PROOF"
    if callable(proof):
        try:
            if proof(record, current_head, current_tree):
                return None
        except Exception:
            pass  # a crashing proof proves nothing
        return "EQUIVALENCE_PROOF_REJECTED"
    if isinstance(proof, dict):
        bound = (
            str(proof.get("result", "")).upper() in PROOF_RESULTS
            and proof.get("covered_contract") is not None
            and proof.get("covered_contract") == record.get("covered_contract")
            and proof.get("old_head") is not None
            and proof.get("new_head") is not None
            and proof.get("old_head") == record.get("head")
            and proof.get("new_head") == current_head
        )
        return None if bound else "EQUIVALENCE_PROOF_NOT_BOUND"
    return "SUBSYSTEM_REUSE_REQUIRES_EQUIVALENCE_PROOF"


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
        rejection = _proof_rejection_reason(equivalence_proof, record,
                                            current_head, current_tree)
        if rejection is None:
            return REUSABLE_SUBSYSTEM, sorted(reasons + ["EQUIVALENCE_PROOF_ACCEPTED"])
        reasons.append(rejection)
    return PREDECESSOR_SUPPORTING, sorted(reasons)


class EvidenceStore:
    """Small append-only evidence store; one JSON file, atomic rewrite.

    Ingestion is idempotent on evidence_id: the first record wins, re-ingesting
    the same evidence_id changes nothing. Concurrent ingestion processes are
    serialized with an exclusive lock file alongside evidence.json so the
    read-modify-write cannot lose records. Records are written in a
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
        self.path.parent.mkdir(parents=True, exist_ok=True)
        lock_path = self.path.with_name(self.path.name + ".lock")
        with open(lock_path, "a+b") as lock_handle:
            if lock_path.stat().st_size == 0:
                lock_handle.write(b"\0")  # msvcrt.locking needs a byte to lock
                lock_handle.flush()
            # The exclusive flock bounds the whole read-modify-write
            # (load + append + replace) so concurrent evidence-ingest
            # processes cannot interleave and lose records; os.replace in
            # save() stays as the torn-write guard for the rewrite itself.
            _lock_exclusive(lock_handle)
            try:
                records = self.load()
                evidence_id = record.get("evidence_id")
                if any(r.get("evidence_id") == evidence_id for r in records):
                    return False, records  # idempotent: first record wins
                records.append(normalize(record))
                self.save(records)
                return True, records
            finally:
                _unlock(lock_handle)

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
