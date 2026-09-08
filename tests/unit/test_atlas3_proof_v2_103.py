"""AT3-103 — proof v2: same-object, digest-verified evidence; v1 byte-identical."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from atlas_contracts.attestation import seal_evidence_attestation
from atlas_contracts.execution_identity import seal_execution_identity
from project_atlas.atlas3.contracts import Atlas3Error
from project_atlas.atlas3.proof import PROOF_STAGES, evaluate_proof, evaluate_proof_v2
from project_atlas.cli import EXIT_ERROR, EXIT_OK, main

HEAD = "a" * 40
TREE = "b" * 40

# Golden proof v1 file digests captured on origin/main 9972d164 BEFORE this
# package touched proof.py. Proof v1 must stay byte-identical for v1 inputs.
V1_GOLDEN = {
    "EMPTY": "8721cb7617fb9a366427b6f001476241c8656545968900e4968d3cc1822c98e3",
    "FULL": "2336e79982d4af274fe598848125f6df7927e6b3a588e6c1f36b132f9de58c1f",
    "PARTIAL": "1a50f7a9501793676414299d134726d824ee964c22adfbcb7ba71d5d89e15905",
}

STAGE_EVIDENCE = {
    "TASK": "TASK_RECORD",
    "IMPLEMENTATION": "IMPLEMENTATION_RECORD",
    "TESTS": "TEST_RESULT",
    "CI": "CI_RESULT",
    "INDEPENDENT_VERIFICATION": "VERIFICATION_RESULT",
    "ADV": "ADVERSARIAL_RESULT",
    "INTEGRATION": "INTEGRATION_RESULT",
    "POST_MERGE": "POST_MERGE_RESULT",
}


def _vault(tmp_path: Path) -> Path:
    vault = tmp_path / "vault"
    (vault / "projects" / "harbor-api").mkdir(parents=True, exist_ok=True)
    (vault / "projects" / "other-project").mkdir(parents=True, exist_ok=True)
    return vault


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
        "environment": {"status": "OBSERVED", "os": "linux", "arch": "x86_64", "python": "3.12.14"},
        "toolchain": {"status": "OBSERVED", "tools": [{"name": "pytest", "version": "8.3.2"}]},
        "agent": {"status": "UNKNOWN"},
        "context": {"status": "UNKNOWN"},
        "capabilities": {"status": "UNKNOWN"},
    }
    payload.update(over)
    return payload


def attestation_body(identity_digest: str, stage: str, **over: Any) -> dict[str, Any]:
    independent = stage in {"INDEPENDENT_VERIFICATION", "ADV"}
    payload: dict[str, Any] = {
        "project_id": "harbor-api",
        "execution_identity_digest": identity_digest,
        "stage": stage,
        "evidence_type": STAGE_EVIDENCE[stage],
        "producer": {
            "kind": "human" if independent else "tool",
            "name": "verifier-b" if independent else "pytest",
            "version": "1",
            "independent_of_implementer": independent,
        },
        "object": {"head": HEAD, "tree": TREE},
        "result": {"status": "PASS", "exit_code": 0, "summary": {"passed": 1}},
        "dependencies": ["DEP_HEAD", "DEP_TREE"],
    }
    payload.update(over)
    return payload


def full_chain(identity_digest: str) -> list[dict[str, Any]]:
    return [
        seal_evidence_attestation(attestation_body(identity_digest, stage)).to_record()
        for stage in PROOF_STAGES
    ]


def _proof_dir(vault: Path, task: str) -> Path:
    return vault / "generated" / "ops" / "atlas3" / "proof" / task


# ---------------------------------------------------------------- v1 unchanged


def test_proof_v1_output_bytes_are_unchanged(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    evaluate_proof(
        vault, "AT3-103-GOLDEN-EMPTY", project_id="harbor-api", model_claims_complete=True
    )
    evaluate_proof(
        vault,
        "AT3-103-GOLDEN-FULL",
        project_id="harbor-api",
        evidence={name: {"evidence_ref": f"ref-{name}"} for name in PROOF_STAGES},
    )
    evaluate_proof(
        vault,
        "AT3-103-GOLDEN-PARTIAL",
        project_id="harbor-api",
        evidence={"TESTS": {"evidence_ref": "t"}, "CI": {"evidence_ref": ""}, "ADV": "x"},
        model_claims_complete=True,
    )
    base = vault / "generated" / "ops" / "atlas3" / "proof"
    for name, expected in V1_GOLDEN.items():
        data = (base / f"AT3-103-GOLDEN-{name}.json").read_bytes()
        assert hashlib.sha256(data).hexdigest() == expected, name


def test_proof_v1_still_accepts_presence_only_evidence_and_says_so(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    report = evaluate_proof(
        vault,
        "AT3-103-V1",
        project_id="harbor-api",
        evidence={name: {"evidence_ref": "x"} for name in PROOF_STAGES},
    )
    assert report["schema"] == "atlas3.agent-proof.v1"
    assert report["chain_status"] == "PROVEN"
    assert "proof_version" not in report


# ---------------------------------------------------------------- v2 positive


def test_full_typed_chain_on_one_object_is_proven(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    ident = seal_execution_identity(identity_body())
    report = evaluate_proof_v2(
        vault,
        "AT3-103-V2",
        project_id="harbor-api",
        identity=ident.to_record(),
        attestations=full_chain(ident.identity_digest),
    )
    assert report["schema"] == "atlas3.agent-proof.v2"
    assert report["proof_version"] == 2
    assert report["chain_status"] == "PROVEN"
    assert report["present_count"] == 8 and report["failed_count"] == 0
    assert report["object"] == {"head": HEAD, "tree": TREE}
    assert report["identity_digest"] == ident.identity_digest
    assert report["bindings"]["environment_bound"] is True
    assert report["model_claim_is_proof"] is False
    assert report["attestation_is_owner_authority"] is False
    assert report["merge_authorization"] == "NOT_GRANTED"
    assert report["live_observation_wired"] is False
    written = _proof_dir(vault, "AT3-103-V2") / f"{ident.identity_digest[:16]}.json"
    assert written.is_file()
    assert json.loads(written.read_text(encoding="utf-8")) == report
    assert written.read_text(encoding="utf-8").isascii()


def test_v2_writes_per_object_and_never_overwrites_another_object(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    one = seal_execution_identity(identity_body())
    evaluate_proof_v2(
        vault,
        "T",
        project_id="harbor-api",
        identity=one,
        attestations=full_chain(one.identity_digest),
    )
    moved = identity_body()
    moved["source"]["candidate_head"] = "c" * 40
    moved["source"]["candidate_tree"] = "d" * 40
    two = seal_execution_identity(moved)
    atts = [
        seal_evidence_attestation(
            attestation_body(
                two.identity_digest, stage, object={"head": "c" * 40, "tree": "d" * 40}
            )
        ).to_record()
        for stage in PROOF_STAGES[:3]
    ]
    partial = evaluate_proof_v2(
        vault, "T", project_id="harbor-api", identity=two, attestations=atts
    )
    assert partial["chain_status"] == "PARTIAL"
    files = sorted(p.name for p in _proof_dir(vault, "T").iterdir())
    assert files == sorted([f"{one.identity_digest[:16]}.json", f"{two.identity_digest[:16]}.json"])


def test_unknown_environment_is_reported_not_fabricated(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    ident = seal_execution_identity(identity_body(environment={"status": "UNKNOWN"}))
    report = evaluate_proof_v2(
        vault,
        "U",
        project_id="harbor-api",
        identity=ident,
        attestations=full_chain(ident.identity_digest),
    )
    assert report["chain_status"] == "PROVEN"
    assert report["bindings"]["environment_bound"] is False
    assert report["bindings"]["object_bound"] is True


def test_partial_and_failed_and_model_claim_semantics(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    ident = seal_execution_identity(identity_body())
    chain = full_chain(ident.identity_digest)
    partial = evaluate_proof_v2(
        vault, "P", project_id="harbor-api", identity=ident, attestations=chain[:5]
    )
    assert partial["chain_status"] == "PARTIAL"
    assert partial["stages"]["ADV"]["status"] == "UNKNOWN"
    claimed = evaluate_proof_v2(
        vault,
        "P",
        project_id="harbor-api",
        identity=ident,
        attestations=chain[:5],
        model_claims_complete=True,
    )
    assert claimed["chain_status"] == "UNPROVEN_MODEL_CLAIM"
    failing = seal_evidence_attestation(
        attestation_body(ident.identity_digest, "TESTS", result={"status": "FAIL", "exit_code": 1})
    ).to_record()
    failed = evaluate_proof_v2(
        vault, "F", project_id="harbor-api", identity=ident, attestations=[*chain, failing]
    )
    assert failed["chain_status"] == "FAILED"
    assert failed["stages"]["TESTS"]["status"] == "FAILED"
    empty = evaluate_proof_v2(vault, "E", project_id="harbor-api", identity=ident, attestations=[])
    assert empty["chain_status"] == "UNKNOWN"


# ---------------------------------------------------------------- v2 negatives


def _refused(tmp_path: Path, code: str, **kwargs: Any) -> None:
    vault = _vault(tmp_path)
    with pytest.raises(Atlas3Error) as excinfo:
        evaluate_proof_v2(vault, "NEG", project_id=kwargs.pop("project_id", "harbor-api"), **kwargs)
    assert excinfo.value.code == code, str(excinfo.value)
    assert not _proof_dir(vault, "NEG").exists(), "nothing may be persisted on refusal"


def test_identity_for_another_project_is_refused(tmp_path: Path) -> None:
    ident = seal_execution_identity(identity_body(project_id="other-project"))
    _refused(tmp_path, "IDENTITY_PROJECT_MISMATCH", identity=ident, attestations=[])


def test_identity_without_candidate_object_is_refused(tmp_path: Path) -> None:
    src = identity_body()["source"]
    src["candidate_head"] = None
    src["candidate_tree"] = None
    ident = seal_execution_identity(identity_body(source=src))
    _refused(tmp_path, "CANDIDATE_OBJECT_REQUIRED", identity=ident, attestations=[])


def test_tampered_identity_is_refused(tmp_path: Path) -> None:
    record = seal_execution_identity(identity_body()).to_record()
    record["source"]["candidate_tree"] = "e" * 40
    _refused(tmp_path, "IDENTITY_DIGEST_MISMATCH", identity=record, attestations=[])


def test_identity_with_authority_field_is_refused(tmp_path: Path) -> None:
    record = seal_execution_identity(identity_body()).to_record()
    record["merge_authorization"] = "GRANTED"
    _refused(tmp_path, "EXECUTION_IDENTITY_MALFORMED", identity=record, attestations=[])


def test_attestation_for_another_object_is_refused(tmp_path: Path) -> None:
    ident = seal_execution_identity(identity_body())
    other_head = seal_evidence_attestation(
        attestation_body(ident.identity_digest, "TESTS", object={"head": "c" * 40, "tree": TREE})
    ).to_record()
    _refused(tmp_path, "PROOF_OBJECT_MISMATCH", identity=ident, attestations=[other_head])
    other_tree = seal_evidence_attestation(
        attestation_body(ident.identity_digest, "TESTS", object={"head": HEAD, "tree": "d" * 40})
    ).to_record()
    _refused(tmp_path, "PROOF_OBJECT_MISMATCH", identity=ident, attestations=[other_tree])


def test_attestation_for_another_identity_is_refused(tmp_path: Path) -> None:
    ident = seal_execution_identity(identity_body())
    foreign = seal_evidence_attestation(attestation_body("9" * 64, "TESTS")).to_record()
    _refused(tmp_path, "ATTESTATION_IDENTITY_MISMATCH", identity=ident, attestations=[foreign])


def test_attestation_for_another_project_is_refused(tmp_path: Path) -> None:
    ident = seal_execution_identity(identity_body())
    foreign = seal_evidence_attestation(
        attestation_body(ident.identity_digest, "TESTS", project_id="other-project")
    ).to_record()
    _refused(tmp_path, "ATTESTATION_PROJECT_MISMATCH", identity=ident, attestations=[foreign])


def test_mixed_object_chain_is_refused_even_when_all_stages_present(tmp_path: Path) -> None:
    ident = seal_execution_identity(identity_body())
    chain = full_chain(ident.identity_digest)
    chain[6] = seal_evidence_attestation(
        attestation_body(
            ident.identity_digest, "INTEGRATION", object={"head": "c" * 40, "tree": TREE}
        )
    ).to_record()
    _refused(tmp_path, "PROOF_OBJECT_MISMATCH", identity=ident, attestations=chain)


def test_tampered_attestation_is_refused(tmp_path: Path) -> None:
    ident = seal_execution_identity(identity_body())
    record = seal_evidence_attestation(
        attestation_body(ident.identity_digest, "TESTS", result={"status": "FAIL"})
    ).to_record()
    record["result"]["status"] = "PASS"
    _refused(tmp_path, "ATTESTATION_HASH_MISMATCH", identity=ident, attestations=[record])


def test_malformed_attestation_is_refused(tmp_path: Path) -> None:
    ident = seal_execution_identity(identity_body())
    record = seal_evidence_attestation(attestation_body(ident.identity_digest, "TESTS")).to_record()
    del record["producer"]
    _refused(tmp_path, "ATTESTATION_MALFORMED", identity=ident, attestations=[record])
    _refused(tmp_path, "ATTESTATION_MALFORMED", identity=ident, attestations=["not-a-dict"])


def test_attestation_with_authority_summary_is_refused(tmp_path: Path) -> None:
    ident = seal_execution_identity(identity_body())
    record = seal_evidence_attestation(attestation_body(ident.identity_digest, "TESTS")).to_record()
    record["result"]["summary"] = {"merge_authorization": 1}
    _refused(tmp_path, "AUTHORITY_FIELD_FORBIDDEN", identity=ident, attestations=[record])


def test_model_producer_attestation_is_refused(tmp_path: Path) -> None:
    ident = seal_execution_identity(identity_body())
    record = seal_evidence_attestation(attestation_body(ident.identity_digest, "TESTS")).to_record()
    record["producer"] = {
        "kind": "model",
        "name": "claude",
        "version": "1",
        "independent_of_implementer": False,
    }
    _refused(tmp_path, "MODEL_PRODUCER_NOT_EVIDENCE", identity=ident, attestations=[record])


def test_iv_attestation_without_declared_independence_is_refused(tmp_path: Path) -> None:
    ident = seal_execution_identity(identity_body())
    record = seal_evidence_attestation(
        attestation_body(ident.identity_digest, "INDEPENDENT_VERIFICATION")
    ).to_record()
    record["producer"]["independent_of_implementer"] = False
    _refused(tmp_path, "INDEPENDENCE_NOT_DECLARED", identity=ident, attestations=[record])


def test_duplicate_attestation_is_refused(tmp_path: Path) -> None:
    ident = seal_execution_identity(identity_body())
    record = seal_evidence_attestation(attestation_body(ident.identity_digest, "TESTS")).to_record()
    _refused(tmp_path, "ATTESTATION_DUPLICATE", identity=ident, attestations=[record, record])


def test_secret_shaped_identity_content_is_refused(tmp_path: Path) -> None:
    ident = seal_execution_identity(
        identity_body(agent={"status": "OBSERVED", "agent_id": "AKIAIOSFODNN7EXAMPLE"})
    )
    _refused(tmp_path, "PROOF_SECRET_FORBIDDEN", identity=ident, attestations=[])


def test_unsafe_task_id_is_refused(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    ident = seal_execution_identity(identity_body())
    with pytest.raises(Atlas3Error) as excinfo:
        evaluate_proof_v2(vault, "../x", project_id="harbor-api", identity=ident, attestations=[])
    assert excinfo.value.code == "UNSAFE_TASK_ID"


# ---------------------------------------------------------------- CLI


def test_cli_proof_v2_from_files(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    vault = _vault(tmp_path)
    ident = seal_execution_identity(identity_body())
    identity_path = tmp_path / "identity.json"
    identity_path.write_text(json.dumps(ident.to_record()), encoding="utf-8")
    atts_path = tmp_path / "atts.json"
    atts_path.write_text(json.dumps(full_chain(ident.identity_digest)), encoding="utf-8")
    code = main(
        [
            "proof",
            "AT3-103-CLI",
            "--vault",
            str(vault),
            "--project",
            "harbor-api",
            "--identity",
            str(identity_path),
            "--attestations",
            str(atts_path),
            "--json",
        ]
    )
    out = capsys.readouterr().out
    assert code == EXIT_OK
    payload = json.loads(out)
    assert payload["proof_version"] == 2 and payload["chain_status"] == "PROVEN"
    assert out.isascii()


def test_cli_proof_v2_requires_both_inputs(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    vault = _vault(tmp_path)
    identity_path = tmp_path / "identity.json"
    identity_path.write_text("{}", encoding="utf-8")
    code = main(
        [
            "proof",
            "AT3-103-CLI",
            "--vault",
            str(vault),
            "--project",
            "harbor-api",
            "--identity",
            str(identity_path),
        ]
    )
    assert code == EXIT_ERROR
    assert json.loads(capsys.readouterr().out)["error"] == "PROOF_V2_INPUTS_INCOMPLETE"


def test_cli_proof_v1_path_is_unchanged(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    vault = _vault(tmp_path)
    code = main(
        ["proof", "AT3-103-CLI-V1", "--vault", str(vault), "--project", "harbor-api", "--json"]
    )
    assert code == EXIT_OK
    payload = json.loads(capsys.readouterr().out)
    assert payload["schema"] == "atlas3.agent-proof.v1"
    assert "proof_version" not in payload


def test_cli_rejects_unreadable_or_wrong_shape_inputs(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    vault = _vault(tmp_path)
    identity_path = tmp_path / "identity.json"
    identity_path.write_text("[]", encoding="utf-8")
    atts_path = tmp_path / "atts.json"
    atts_path.write_text("{}", encoding="utf-8")
    code = main(
        [
            "proof",
            "X",
            "--vault",
            str(vault),
            "--project",
            "harbor-api",
            "--identity",
            str(identity_path),
            "--attestations",
            str(atts_path),
        ]
    )
    assert code == EXIT_ERROR
    assert json.loads(capsys.readouterr().out)["error"] == "PROOF_INPUT_INVALID"
