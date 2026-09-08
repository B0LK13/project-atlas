"""AT3-103 — ExecutionIdentity v1: content-addressed, fail-closed, UNKNOWN-honest."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import jsonschema
import pytest
from pydantic import ValidationError

from atlas_contracts.execution_identity import (
    ExecutionIdentity,
    ExecutionIdentityError,
    load_execution_identity,
    seal_execution_identity,
)

HEAD = "a" * 40
TREE = "b" * 40
BASE_HEAD = "1" * 40
BASE_TREE = "2" * 40
SCHEMA_PATH = (
    Path(__file__).parents[2]
    / "src"
    / "atlas_contracts"
    / "schemas"
    / "execution-identity.schema.json"
)


def body(**over: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "project_id": "harbor-api",
        "source": {
            "kind": "git",
            "repository": "github.com/b0lk13/project-atlas",
            "base_head": BASE_HEAD,
            "base_tree": BASE_TREE,
            "candidate_head": HEAD,
            "candidate_tree": TREE,
        },
        "environment": {"status": "OBSERVED", "os": "linux", "arch": "x86_64", "python": "3.12.14"},
        "toolchain": {
            "status": "OBSERVED",
            "tools": [{"name": "pytest", "version": "8.3.2"}, {"name": "ruff", "version": "0.6.0"}],
        },
        "agent": {"status": "UNKNOWN"},
        "context": {"status": "UNKNOWN"},
        "capabilities": {"status": "UNKNOWN"},
    }
    payload.update(over)
    return payload


def _code(exc: BaseException) -> str:
    return str(exc)


def test_seal_then_load_round_trips_and_is_deterministic() -> None:
    one = seal_execution_identity(body())
    two = seal_execution_identity(body())
    assert one.identity_digest == two.identity_digest
    assert one.run_id == f"run-{one.identity_digest[:16]}"
    record = one.to_record()
    assert record["schema"] == "atlas.execution-identity.v1"
    loaded = load_execution_identity(json.loads(json.dumps(record)))
    assert loaded == one
    assert loaded.candidate_object() == (HEAD, TREE)
    assert loaded.bindings() == {
        "object_bound": True,
        "environment_bound": True,
        "toolchain_bound": True,
        "agent_bound": False,
        "context_bound": False,
        "capabilities_bound": False,
    }


def test_environment_fields_are_optional_by_status_not_by_value() -> None:
    unknown = seal_execution_identity(body(environment={"status": "UNKNOWN"}))
    observed = seal_execution_identity(body())
    assert unknown.identity_digest != observed.identity_digest
    assert unknown.bindings()["environment_bound"] is False
    assert unknown.to_record()["environment"] == {
        "status": "UNKNOWN",
        "os": None,
        "arch": None,
        "python": None,
    }


@pytest.mark.parametrize(
    ("field", "value", "code"),
    [
        ("project_id", "other", "IDENTITY_DIGEST_MISMATCH"),
        ("environment", {"status": "UNKNOWN"}, "IDENTITY_DIGEST_MISMATCH"),
    ],
)
def test_tampering_after_seal_is_detected(field: str, value: Any, code: str) -> None:
    record = seal_execution_identity(body()).to_record()
    record[field] = value
    with pytest.raises(ValidationError) as excinfo:
        load_execution_identity(record)
    assert code in _code(excinfo.value)


def test_tampering_the_candidate_object_invalidates_the_identity() -> None:
    record = seal_execution_identity(body()).to_record()
    record["source"]["candidate_tree"] = "c" * 40
    with pytest.raises(ValidationError, match="IDENTITY_DIGEST_MISMATCH"):
        load_execution_identity(record)


def test_run_id_must_derive_from_digest() -> None:
    record = seal_execution_identity(body()).to_record()
    record["run_id"] = "run-" + "f" * 16
    with pytest.raises(ValidationError, match="RUN_ID_MISMATCH"):
        load_execution_identity(record)


def test_caller_supplied_digest_on_seal_is_refused() -> None:
    with pytest.raises(ValidationError, match="DIGEST_SUPPLIED_ON_SEAL"):
        seal_execution_identity(body(identity_digest="0" * 64))


@pytest.mark.parametrize(
    "sha",
    ["A" * 40, "a" * 39, "a" * 41, "g" * 40, " " + "a" * 39, "0x" + "a" * 38],
)
def test_non_canonical_shas_are_refused(sha: str) -> None:
    src = body()["source"]
    src["candidate_head"] = sha
    with pytest.raises(ValidationError):
        seal_execution_identity(body(source=src))


def test_candidate_object_must_be_complete() -> None:
    src = body()["source"]
    src["candidate_tree"] = None
    with pytest.raises(ValidationError, match="CANDIDATE_OBJECT_INCOMPLETE"):
        seal_execution_identity(body(source=src))
    src["candidate_head"] = None
    absent = seal_execution_identity(body(source=src))
    assert absent.candidate_object() is None
    assert absent.bindings()["object_bound"] is False


@pytest.mark.parametrize(
    ("block", "value", "code"),
    [
        ("environment", {"status": "UNKNOWN", "os": "linux"}, "UNKNOWN_WITH_VALUES"),
        (
            "environment",
            {"status": "OBSERVED", "os": "linux"},
            "ENVIRONMENT_OBSERVATION_INCOMPLETE",
        ),
        (
            "toolchain",
            {"status": "UNKNOWN", "tools": [{"name": "x", "version": "1"}]},
            "UNKNOWN_WITH_VALUES",
        ),
        ("toolchain", {"status": "OBSERVED", "tools": []}, "TOOLCHAIN_OBSERVATION_INCOMPLETE"),
        (
            "toolchain",
            {
                "status": "OBSERVED",
                "tools": [{"name": "b", "version": "1"}, {"name": "a", "version": "1"}],
            },
            "TOOL_ORDER",
        ),
        (
            "toolchain",
            {
                "status": "OBSERVED",
                "tools": [{"name": "a", "version": "1"}, {"name": "a", "version": "2"}],
            },
            "TOOL_DUPLICATE",
        ),
        ("agent", {"status": "OBSERVED"}, "AGENT_OBSERVATION_INCOMPLETE"),
        ("agent", {"status": "UNKNOWN", "agent_id": "x"}, "UNKNOWN_WITH_VALUES"),
        ("context", {"status": "OBSERVED"}, "CONTEXT_OBSERVATION_INCOMPLETE"),
        ("context", {"status": "UNKNOWN", "context_digest": "0" * 64}, "UNKNOWN_WITH_VALUES"),
        ("capabilities", {"status": "OBSERVED"}, "CAPABILITIES_OBSERVATION_INCOMPLETE"),
        ("capabilities", {"status": "UNKNOWN", "grant_ref": "g"}, "UNKNOWN_WITH_VALUES"),
    ],
)
def test_unknown_and_observed_are_mutually_consistent(block: str, value: Any, code: str) -> None:
    with pytest.raises(ValidationError) as excinfo:
        seal_execution_identity(body(**{block: value}))
    assert code in _code(excinfo.value)


@pytest.mark.parametrize(
    "extra",
    [
        {"merge_authorization": "GRANTED"},
        {"execution_authorized": True},
        {"owner_authority": True},
        {"trust_score": 0.9},
        {"model": {"provider": "x", "model": "y"}},
        {"environment_digest": "0" * 64},
    ],
)
def test_unknown_fields_including_authority_claims_are_refused(extra: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        seal_execution_identity(body(**extra))


@pytest.mark.parametrize("project_id", ["", ".", "..", "a/b", "a\\b", "C:x", "con", "x "])
def test_unsafe_project_ids_are_refused(project_id: str) -> None:
    with pytest.raises(ValidationError):
        seal_execution_identity(body(project_id=project_id))


@pytest.mark.parametrize("value", [1.0, True, "1", 2])
def test_schema_version_is_strictly_the_integer_one(value: Any) -> None:
    with pytest.raises(ValidationError):
        seal_execution_identity(body(schema_version=value))


def test_placeholder_digest_is_not_accepted_on_strict_load() -> None:
    record = seal_execution_identity(body()).to_record()
    record["identity_digest"] = "0" * 64
    record["run_id"] = "run-" + "0" * 16
    with pytest.raises(ValidationError, match="IDENTITY_DIGEST_MISMATCH"):
        load_execution_identity(record)


def test_shipped_json_schema_accepts_sealed_record_and_rejects_extra_key() -> None:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    record = seal_execution_identity(body()).to_record()
    jsonschema.validate(record, schema)
    record["merge_authorization"] = "GRANTED"
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(record, schema)


def test_error_type_carries_a_stable_code() -> None:
    exc = ExecutionIdentityError("SOME_CODE", "detail")
    assert exc.code == "SOME_CODE"
    assert str(exc).startswith("SOME_CODE: ")
    assert set(ExecutionIdentity.model_fields) == {
        "schema_id",
        "schema_version",
        "project_id",
        "source",
        "environment",
        "toolchain",
        "agent",
        "context",
        "capabilities",
        "identity_digest",
        "run_id",
    }


@pytest.mark.parametrize(
    ("block", "value"),
    [
        ("environment", {"status": "OBSERVED", "os": "lin ux", "arch": "x", "python": "3"}),
        ("environment", {"status": "OBSERVED", "os": "linux\u200b", "arch": "x", "python": "3"}),
        ("toolchain", {"status": "OBSERVED", "tools": [{"name": "a", "version": "1\t"}]}),
        ("toolchain", {"status": "OBSERVED", "tools": [{"name": "a", "version": "\u00e9"}]}),
    ],
)
def test_digest_bound_tokens_must_be_printable_ascii(block: str, value: Any) -> None:
    with pytest.raises(ValidationError):
        seal_execution_identity(body(**{block: value}))
