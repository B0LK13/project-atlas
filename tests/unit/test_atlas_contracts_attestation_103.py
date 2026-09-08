"""AT3-103 — EvidenceAttestation v1: typed, content-addressed, model claim != evidence."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import jsonschema
import pytest
from pydantic import ValidationError

from atlas_contracts.attestation import (
    DEPENDENCY_CLASSES,
    EVIDENCE_STAGES,
    EVIDENCE_TYPES,
    STAGE_EVIDENCE_TYPES,
    AttestationError,
    load_evidence_attestation,
    seal_evidence_attestation,
)
from project_atlas.atlas3.proof import PROOF_STAGES

HEAD = "a" * 40
TREE = "b" * 40
IDENTITY = "3" * 64
SCHEMA_PATH = (
    Path(__file__).parents[2]
    / "src"
    / "atlas_contracts"
    / "schemas"
    / "evidence-attestation.schema.json"
)


def body(**over: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "project_id": "harbor-api",
        "execution_identity_digest": IDENTITY,
        "stage": "TESTS",
        "evidence_type": "TEST_RESULT",
        "producer": {"kind": "tool", "name": "pytest", "version": "8.3.2"},
        "object": {"head": HEAD, "tree": TREE},
        "command_ref": "python -m pytest tests/unit/test_x.py",
        "result": {"status": "PASS", "exit_code": 0, "summary": {"passed": 12, "failed": 0}},
        "dependencies": ["DEP_HEAD", "DEP_TEST_SET", "DEP_TREE"],
    }
    payload.update(over)
    return payload


def test_stage_vocabulary_is_pinned_to_proof_stages() -> None:
    assert EVIDENCE_STAGES == PROOF_STAGES
    assert set(STAGE_EVIDENCE_TYPES) == set(PROOF_STAGES)
    assert frozenset().union(*STAGE_EVIDENCE_TYPES.values()) == EVIDENCE_TYPES
    assert "DEP_HEAD" in DEPENDENCY_CLASSES and "DEP_TREE" in DEPENDENCY_CLASSES


def test_seal_then_load_round_trips_and_is_deterministic() -> None:
    one = seal_evidence_attestation(body())
    two = seal_evidence_attestation(body())
    assert one.content_hash == two.content_hash
    assert one.attestation_id == f"att-{one.content_hash[:16]}"
    record = one.to_record()
    assert record["schema"] == "atlas.evidence-attestation.v1"
    assert record["object"] == {"head": HEAD, "tree": TREE}
    assert load_evidence_attestation(json.loads(json.dumps(record))) == one


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("result", "status"), "FAIL"),
        (("object", "head"), "c" * 40),
        (("producer", "name"), "other"),
        (("execution_identity_digest",), "4" * 64),
        (("stage",), "CI"),
    ],
)
def test_tampering_after_seal_is_detected(path: tuple[str, ...], value: Any) -> None:
    record = seal_evidence_attestation(body()).to_record()
    target: Any = record
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    if path == ("stage",):
        record["evidence_type"] = "CI_RESULT"
    with pytest.raises(ValidationError, match="ATTESTATION_HASH_MISMATCH"):
        load_evidence_attestation(record)


def test_caller_supplied_hash_on_seal_is_refused() -> None:
    with pytest.raises(ValidationError, match="DIGEST_SUPPLIED_ON_SEAL"):
        seal_evidence_attestation(body(content_hash="0" * 64))


def test_model_producer_is_never_evidence() -> None:
    with pytest.raises(ValidationError, match="MODEL_PRODUCER_NOT_EVIDENCE"):
        seal_evidence_attestation(
            body(producer={"kind": "model", "name": "claude", "version": "UNKNOWN"})
        )


@pytest.mark.parametrize(
    ("stage", "evidence_type"),
    [("INDEPENDENT_VERIFICATION", "VERIFICATION_RESULT"), ("ADV", "ADVERSARIAL_RESULT")],
)
def test_independent_stages_require_declared_independence(stage: str, evidence_type: str) -> None:
    with pytest.raises(ValidationError, match="INDEPENDENCE_NOT_DECLARED"):
        seal_evidence_attestation(
            body(
                stage=stage,
                evidence_type=evidence_type,
                producer={"kind": "agent", "name": "verifier-b", "version": "1"},
            )
        )
    sealed = seal_evidence_attestation(
        body(
            stage=stage,
            evidence_type=evidence_type,
            producer={
                "kind": "human",
                "name": "verifier-b",
                "version": "1",
                "independent_of_implementer": True,
            },
        )
    )
    assert sealed.producer.independent_of_implementer is True


def test_evidence_type_must_match_stage() -> None:
    with pytest.raises(ValidationError, match="EVIDENCE_TYPE_STAGE_MISMATCH"):
        seal_evidence_attestation(body(stage="CI", evidence_type="TEST_RESULT"))
    with pytest.raises(ValidationError, match="EVIDENCE_TYPE_STAGE_MISMATCH"):
        seal_evidence_attestation(body(evidence_type="EXPERIMENT_RESULT"))
    with pytest.raises(ValidationError):
        seal_evidence_attestation(body(evidence_type="lowercase"))


@pytest.mark.parametrize(
    ("deps", "code"),
    [
        (["DEP_HEAD", "DEP_TREE", "DEP_MAGIC"], "DEPENDENCY_UNKNOWN"),
        (["DEP_TREE", "DEP_HEAD"], "DEPENDENCY_ORDER"),
        (["DEP_HEAD", "DEP_HEAD", "DEP_TREE"], "DEPENDENCY_ORDER"),
        (["DEP_HEAD"], "OBJECT_DEPENDENCY_REQUIRED"),
        ([], "OBJECT_DEPENDENCY_REQUIRED"),
    ],
)
def test_dependency_classes_are_validated(deps: list[str], code: str) -> None:
    with pytest.raises(ValidationError) as excinfo:
        seal_evidence_attestation(body(dependencies=deps))
    assert code in str(excinfo.value)


@pytest.mark.parametrize(
    "summary",
    [
        {"merge_authorization": 1},
        {"MERGE_AUTHORIZATION": 1},
        {"trust_score": 9},
        {"certified_for_merge": 1},
        {"owner_authority": 1},
    ],
)
def test_authority_shaped_summary_keys_are_refused(summary: dict[str, int]) -> None:
    with pytest.raises(ValidationError, match="SUMMARY_KEY_UNKNOWN"):
        seal_evidence_attestation(body(result={"status": "PASS", "summary": summary}))


@pytest.mark.parametrize(
    "summary",
    [
        {"merge-authorization": 1},
        {"mergeAuthorization": 1},
        {"MERGE_AUTHORIZATION_": 1},
        {"trust__score": 1},
        {"merge_authorization\u200b": 1},
        {"merge_authorizati\u043en": 1},
        {"a b": 1},
        {"a\x01b": 1},
        {"1abc": 1},
    ],
)
def test_lookalike_and_non_identifier_summary_keys_are_refused(summary: dict[str, int]) -> None:
    with pytest.raises(ValidationError, match="SUMMARY_KEY_UNKNOWN"):
        seal_evidence_attestation(body(result={"status": "PASS", "summary": summary}))


def test_summary_vocabulary_is_positive_and_bounded() -> None:
    from atlas_contracts.attestation import SUMMARY_COUNTERS

    assert {"passed", "failed", "errors", "skipped", "findings", "p2"} <= SUMMARY_COUNTERS
    assert not any("merge" in k or "trust" in k or "owner" in k for k in SUMMARY_COUNTERS)
    ok = seal_evidence_attestation(
        body(result={"status": "PASS", "summary": {k: 0 for k in sorted(SUMMARY_COUNTERS)}})
    )
    assert ok.result.summary["passed"] == 0
    with pytest.raises(ValidationError, match="SUMMARY_KEY_UNKNOWN"):
        seal_evidence_attestation(body(result={"status": "PASS", "summary": {"total": 1}}))


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("exit_code", "0"),
        ("exit_code", 1.0),
        ("summary", {"passed": 1.0}),
        ("summary", {"passed": True}),
        ("summary", {"passed": "1"}),
    ],
)
def test_digest_bound_scalars_are_strict_not_coerced(field: str, value: Any) -> None:
    result: dict[str, Any] = {"status": "PASS", "summary": {"passed": 1}}
    result[field] = value
    with pytest.raises(ValidationError):
        seal_evidence_attestation(body(result=result))
    with pytest.raises(ValidationError):
        seal_evidence_attestation(
            body(
                producer={
                    "kind": "tool",
                    "name": "x",
                    "version": "1",
                    "independent_of_implementer": "false",
                }
            )
        )
    with pytest.raises(ValidationError):
        seal_evidence_attestation(
            body(producer={"kind": "tool", "name": "x", "version": "1\u200b"})
        )


@pytest.mark.parametrize("version", ["1 .0", "1\t", "\u00e9", "-1", ".1", "v" * 129, ""])
def test_version_identifier_is_conservative_ascii(version: str) -> None:
    with pytest.raises(ValidationError):
        seal_evidence_attestation(body(producer={"kind": "tool", "name": "x", "version": version}))
    for ok in ("8.3.2", "1.0.0-rc1", "0.6.0+local", "UNKNOWN", "v2"):
        seal_evidence_attestation(body(producer={"kind": "tool", "name": "x", "version": ok}))


def test_summary_values_must_be_counts() -> None:
    with pytest.raises(ValidationError):
        seal_evidence_attestation(body(result={"status": "PASS", "summary": {"passed": -1}}))
    with pytest.raises(ValidationError):
        seal_evidence_attestation(body(result={"status": "PASS", "summary": {"passed": 10**30}}))
    seal_evidence_attestation(body(result={"status": "PASS", "summary": {"passed": 10**9}}))
    with pytest.raises(ValidationError):
        seal_evidence_attestation(body(result={"status": "PASS", "summary": {"passed": "many"}}))
    record = seal_evidence_attestation(body()).to_record()
    record["attestation_id"] = "att-" + "f" * 16
    with pytest.raises(ValidationError, match="ATTESTATION_ID_MISMATCH"):
        load_evidence_attestation(record)


@pytest.mark.parametrize(
    "extra",
    [{"merge_authorization": "GRANTED"}, {"certified_for_merge": True}, {"owner_origin": "x"}],
)
def test_unknown_top_level_fields_are_refused(extra: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        seal_evidence_attestation(body(**extra))


@pytest.mark.parametrize("sha", ["A" * 40, "a" * 39, "z" * 40])
def test_non_canonical_object_shas_are_refused(sha: str) -> None:
    with pytest.raises(ValidationError):
        seal_evidence_attestation(body(object={"head": sha, "tree": TREE}))


def test_unsafe_project_id_is_refused() -> None:
    with pytest.raises(ValidationError, match="UNSAFE_PROJECT_ID"):
        seal_evidence_attestation(body(project_id=".."))


def test_shipped_json_schema_accepts_sealed_record_and_rejects_extra_key() -> None:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    record = seal_evidence_attestation(body()).to_record()
    jsonschema.validate(record, schema)
    record["trust_score"] = 1
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(record, schema)
    record.pop("trust_score")
    record["producer"]["kind"] = "model"
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(record, schema)


def test_error_type_carries_a_stable_code() -> None:
    exc = AttestationError("X_CODE", "detail")
    assert exc.code == "X_CODE" and str(exc) == "X_CODE: detail"
    with pytest.raises(ValidationError) as excinfo:
        seal_evidence_attestation(body(stage="ADV", evidence_type="ADVERSARIAL_RESULT"))
    # The stable code must surface in the pydantic message so callers can map it.
    assert "INDEPENDENCE_NOT_DECLARED" in str(excinfo.value)


@pytest.mark.parametrize("value", [1.0, True, "1", 2, 0])
def test_schema_version_is_strictly_the_integer_one(value: Any) -> None:
    with pytest.raises(ValidationError):
        seal_evidence_attestation(body(schema_version=value))
    seal_evidence_attestation(body(schema_version=1))


def test_json_schema_summary_and_version_constraints_are_declarative() -> None:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    assert "STRUCTURAL" in schema["description"]
    record = seal_evidence_attestation(body()).to_record()
    record["result"]["summary"] = {"merge_authorization": 1}
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(record, schema)
    record["result"]["summary"] = {"passed": 1}
    record["producer"]["version"] = "1 .0"
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(record, schema)
