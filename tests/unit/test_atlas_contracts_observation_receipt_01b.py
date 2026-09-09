"""ULT-01b-1 — ObservationReceipt v1: content-bound, identity-consistent, timestamp-free."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import jsonschema
import pytest
from pydantic import ValidationError

from atlas_contracts.execution_identity import seal_execution_identity
from atlas_contracts.observation_receipt import (
    DIMENSIONS,
    ObservationReceipt,
    ObservationReceiptError,
    load_observation_receipt,
    seal_observation_receipt,
)

HEAD = "a" * 40
TREE = "b" * 40
SCHEMA_DIR = Path(__file__).parents[2] / "src" / "atlas_contracts" / "schemas"


def identity_body(**over: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "project_id": "harbor-api",
        "source": {
            "kind": "git",
            "repository": "github.com/b0lk13/project-atlas",
            "base_head": "1" * 40,
            "base_tree": "2" * 40,
            "candidate_head": HEAD,
            "candidate_tree": TREE,
        },
        "environment": {"status": "OBSERVED", "os": "Linux", "arch": "x86_64", "python": "3.12.14"},
        "toolchain": {"status": "OBSERVED", "tools": [{"name": "git", "version": "2.53.0"}]},
        "agent": {"status": "UNKNOWN"},
        "context": {"status": "UNKNOWN"},
        "capabilities": {"status": "UNKNOWN"},
    }
    payload.update(over)
    return payload


def receipt_body(identity: Any = None, **over: Any) -> dict[str, Any]:
    ident = identity if identity is not None else seal_execution_identity(identity_body())
    payload: dict[str, Any] = {
        "project_id": "harbor-api",
        "identity": ident.to_record(),
        "identity_digest": ident.identity_digest,
        "observer": {
            "kind": "tool",
            "name": "atlas-execution-observer",
            "version": "2.0.0",
            "version_status": "OBSERVED",
        },
        "observed": {
            "source": {
                "status": "OBSERVED",
                "method": "git",
                "method_refs": ["git rev-parse HEAD^{commit}", "git remote get-url origin"],
                "base_ref": "origin/main",
                "remote_name": "origin",
                "worktree_clean": True,
                "shallow": False,
                "git_version": "2.53.0",
                "git_executable_path_digest": "c" * 64,
            },
            "environment": {
                "status": "OBSERVED",
                "method": "platform+sys",
                "method_refs": ["platform.system", "platform.machine", "sys.version_info"],
                "arch_raw": "x86_64",
            },
            "toolchain": {
                "status": "OBSERVED",
                "method": "importlib.metadata+git",
                "method_refs": ["importlib.metadata.version", "git --version"],
                "declared": ["git", "pytest"],
                "absent": ["pytest"],
            },
            "agent": {"status": "UNKNOWN", "reason": "NOT_OBSERVABLE_IN_THIS_SLICE"},
            "context": {"status": "UNKNOWN", "reason": "NO_CONTEXT_DIGEST_SOURCE"},
            "capabilities": {"status": "UNKNOWN", "reason": "NOT_OBSERVABLE_IN_THIS_SLICE"},
        },
    }
    payload.update(over)
    return payload


def test_seal_then_load_round_trips_and_is_deterministic() -> None:
    one = seal_observation_receipt(receipt_body())
    two = seal_observation_receipt(receipt_body())
    assert one.content_hash == two.content_hash
    assert one.observation_id == f"obs-{one.content_hash[:16]}"
    record = one.to_record()
    assert record["schema"] == "atlas.observation-receipt.v1"
    assert record["observed_is_current"] is False
    assert record["authority"] == "derived"
    assert record["merge_authorization"] == "NOT_GRANTED"
    assert load_observation_receipt(json.loads(json.dumps(record))) == one
    assert set(DIMENSIONS) == set(record["observed"])


def test_receipt_carries_no_timestamp_field_anywhere() -> None:
    text = json.dumps(seal_observation_receipt(receipt_body()).to_record()).lower()
    for token in ("timestamp", "observed_at", "recorded_at", '"at"', '_at"', "created", "time"):
        assert token not in text, token


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("observed", "source", "shallow"), True),
        (("observed", "source", "base_ref"), "origin/other"),
        (("observed", "toolchain", "absent"), []),
        (("observer", "name"), "other-observer"),
        (("identity_digest",), "f" * 64),
    ],
)
def test_tampering_after_seal_is_detected(path: tuple[str, ...], value: Any) -> None:
    record = seal_observation_receipt(receipt_body()).to_record()
    target: Any = record
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    with pytest.raises(ValidationError) as excinfo:
        load_observation_receipt(record)
    text = str(excinfo.value)
    assert "RECEIPT_HASH_MISMATCH" in text or "RECEIPT_IDENTITY_MISMATCH" in text


def test_tampering_the_embedded_identity_is_detected_by_the_identity_itself() -> None:
    record = seal_observation_receipt(receipt_body()).to_record()
    record["identity"]["source"]["candidate_tree"] = "d" * 40
    with pytest.raises(ValidationError, match="IDENTITY_DIGEST_MISMATCH"):
        load_observation_receipt(record)


def test_identity_digest_must_match_embedded_identity() -> None:
    other = seal_execution_identity(identity_body(environment={"status": "UNKNOWN"}))
    body = receipt_body()
    body["identity_digest"] = other.identity_digest
    with pytest.raises(ValidationError, match="RECEIPT_IDENTITY_MISMATCH"):
        seal_observation_receipt(body)


def test_dimension_status_must_agree_with_identity_blocks() -> None:
    ident = seal_execution_identity(identity_body(environment={"status": "UNKNOWN"}))
    body = receipt_body(ident)
    with pytest.raises(ValidationError, match="DIMENSION_STATUS_MISMATCH"):
        seal_observation_receipt(body)
    body["observed"]["environment"] = {
        "status": "UNKNOWN",
        "reason": "ARCH_UNMAPPED",
        "arch_raw": "riscv64",
    }
    sealed = seal_observation_receipt(body)
    assert sealed.observed.environment.status == "UNKNOWN"
    body["observed"]["agent"] = {"status": "OBSERVED", "method": "declared"}
    with pytest.raises(ValidationError, match="DIMENSION_STATUS_MISMATCH"):
        seal_observation_receipt(body)


def test_unknown_requires_reason_and_observed_forbids_it() -> None:
    body = receipt_body()
    body["observed"]["agent"] = {"status": "UNKNOWN"}
    with pytest.raises(ValidationError, match="UNKNOWN_REASON_REQUIRED"):
        seal_observation_receipt(body)
    body = receipt_body()
    body["observed"]["environment"]["reason"] = "SOMETHING"
    with pytest.raises(ValidationError, match="OBSERVED_WITH_REASON"):
        seal_observation_receipt(body)
    body = receipt_body()
    del body["observed"]["environment"]["method"]
    with pytest.raises(ValidationError, match="OBSERVATION_METHOD_REQUIRED"):
        seal_observation_receipt(body)


@pytest.mark.parametrize(
    "ref",
    [
        "git remote get-url https://github.com/x/y",
        "git clone https://token@github.com/x/y",
        "git@github.com:x/y",
        "git remote get-url\n",
        "x" * 129,
        "",
    ],
)
def test_method_refs_cannot_carry_urls_or_userinfo(ref: str) -> None:
    body = receipt_body()
    body["observed"]["source"]["method_refs"] = [ref]
    with pytest.raises(ValidationError):
        seal_observation_receipt(body)


@pytest.mark.parametrize("kind", ["model", "agent", "human", "ci"])
def test_observer_must_be_a_tool(kind: str) -> None:
    body = receipt_body()
    body["observer"]["kind"] = kind
    with pytest.raises(ValidationError):
        seal_observation_receipt(body)


def test_observer_version_status_consistency() -> None:
    body = receipt_body()
    body["observer"].update({"version": "UNKNOWN", "version_status": "OBSERVED"})
    with pytest.raises(ValidationError, match="OBSERVER_VERSION_INCOMPLETE"):
        seal_observation_receipt(body)
    body["observer"].update({"version": "2.0.0", "version_status": "UNKNOWN"})
    with pytest.raises(ValidationError, match="OBSERVER_VERSION_UNKNOWN_WITH_VALUE"):
        seal_observation_receipt(body)
    body["observer"].update({"version": "UNKNOWN", "version_status": "UNKNOWN"})
    seal_observation_receipt(body)


def test_git_dimension_requires_clean_worktree_and_refs_when_observed() -> None:
    body = receipt_body()
    body["observed"]["source"]["worktree_clean"] = False
    with pytest.raises(ValidationError, match="GIT_OBSERVATION_INCOMPLETE"):
        seal_observation_receipt(body)
    body = receipt_body()
    body["observed"]["source"]["remote_name"] = None
    with pytest.raises(ValidationError, match="GIT_OBSERVATION_INCOMPLETE"):
        seal_observation_receipt(body)


def test_toolchain_sets_are_sorted_unique_and_absent_subset_of_declared() -> None:
    body = receipt_body()
    body["observed"]["toolchain"]["declared"] = ["pytest", "git"]
    with pytest.raises(ValidationError, match="TOOL_ORDER"):
        seal_observation_receipt(body)
    body = receipt_body()
    body["observed"]["toolchain"]["absent"] = ["ruff"]
    with pytest.raises(ValidationError, match="TOOL_ABSENT_NOT_DECLARED"):
        seal_observation_receipt(body)


@pytest.mark.parametrize(
    "extra",
    [
        {"merge_authorization": "GRANTED"},
        {"certified_for_merge": True},
        {"observed_is_current": True},
        {"authority": "canonical"},
        {"trust_score": 1},
        {"timestamp": "2026-09-09T00:00:00Z"},
        {"observed_at": "2026-09-09T00:00:00Z"},
    ],
)
def test_authority_current_and_time_claims_are_refused(extra: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        seal_observation_receipt(receipt_body(**extra))


def test_caller_supplied_hash_on_seal_is_refused_and_placeholder_not_loadable() -> None:
    with pytest.raises(ValidationError, match="DIGEST_SUPPLIED_ON_SEAL"):
        seal_observation_receipt(receipt_body(content_hash="0" * 64))
    record = seal_observation_receipt(receipt_body()).to_record()
    record["content_hash"] = "0" * 64
    record["observation_id"] = "obs-" + "0" * 16
    with pytest.raises(ValidationError, match="RECEIPT_HASH_MISMATCH"):
        load_observation_receipt(record)


def test_project_must_match_identity_and_be_safe() -> None:
    body = receipt_body(project_id="other-project")
    with pytest.raises(ValidationError, match="RECEIPT_PROJECT_MISMATCH"):
        seal_observation_receipt(body)
    ident = seal_execution_identity(identity_body(project_id="ok"))
    body = receipt_body(ident, project_id="ok")
    seal_observation_receipt(body)


def test_shipped_schema_is_structural_and_pins_shape() -> None:
    schema = json.loads((SCHEMA_DIR / "observation-receipt.schema.json").read_text("utf-8"))
    identity_schema = json.loads((SCHEMA_DIR / "execution-identity.schema.json").read_text("utf-8"))
    assert "STRUCTURAL" in schema["description"]
    record = seal_observation_receipt(receipt_body()).to_record()
    jsonschema.validate(record, schema)
    jsonschema.validate(record["identity"], identity_schema)
    record["trust_score"] = 1
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(record, schema)
    del record["trust_score"]
    record["observer"]["kind"] = "model"
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(record, schema)


def test_error_type_carries_a_stable_code() -> None:
    exc = ObservationReceiptError("X_CODE", "detail")
    assert exc.code == "X_CODE" and str(exc) == "X_CODE: detail"
    assert set(ObservationReceipt.model_fields) >= {
        "identity",
        "identity_digest",
        "observer",
        "observed",
        "content_hash",
        "observation_id",
    }
