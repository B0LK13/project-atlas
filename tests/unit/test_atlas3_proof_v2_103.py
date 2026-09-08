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
    return vault / "generated" / "ops" / "atlas3" / "proof" / "v2" / task


V1_GOLDEN_EXTENDED = {
    "NUMERIC-REF": (
        {"TESTS": {"evidence_ref": 42}},
        False,
        "e73ac795a14dc36e6fb52335e4afb60c8c7dac5deba729961135d5173b1a671f",
    ),
    "LIST-REF": (
        {"CI": {"evidence_ref": ["a", "b"]}},
        True,
        "a46d674a78de992833e756338a12ad667dde742c0c7df640facc8e0f1612d876",
    ),
    "NONE-REF": (
        {"ADV": {"evidence_ref": None}, "TASK": {"evidence_ref": "t"}},
        False,
        "ee7a90fe4fe9c08ef89f5e16d2d31e9e67ca974dd6986d652d375f9f99403ca5",
    ),
    "UNICODE-REF": (
        {n: {"evidence_ref": "Zo\u00eb \u2014 \u6771\u4eac"} for n in PROOF_STAGES},
        True,
        "26e5c408c7857e179243e2b72e5ae8abe599a235b8c163bbf7320f25bed28fc0",
    ),
    "UNKNOWN-STAGE-KEY": (
        {"NOT_A_STAGE": {"evidence_ref": "x"}, "merge_authorization": "GRANTED"},
        True,
        "9327e977f280cf3e2fb80417b8d354c7e8f143f6f588ca101fa35cd97c9c8bce",
    ),
    "EXTRA-FIELDS": (
        {n: {"evidence_ref": "r", "extra": {"nested": [1, 2]}} for n in PROOF_STAGES},
        False,
        "715900ccefafe420af0f775654c6058f1d730be00107a44d3ca59b457ff1efbf",
    ),
    "WHITESPACE-REF": (
        {"TESTS": {"evidence_ref": "  "}, "CI": {"evidence_ref": "\t"}},
        True,
        "adc10740cbe944261caf0a6247017b8cd2c975545a7b197126ba0192c84993cc",
    ),
    "EMPTY-DICT": (
        {},
        False,
        "49a1b35bedcb642e9bf9055f6f9f359add018c9a18f0afbdc29a214532b458f0",
    ),
}


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


@pytest.mark.parametrize("name", sorted(V1_GOLDEN_EXTENDED))
def test_proof_v1_extended_golden_matrix_is_unchanged(tmp_path: Path, name: str) -> None:
    """Digests regenerated from `git show 9972d164:src/project_atlas/atlas3/proof.py`."""
    vault = _vault(tmp_path)
    evidence, claim, expected = V1_GOLDEN_EXTENDED[name]
    evaluate_proof(
        vault,
        f"AT3-103-GOLDEN-{name}",
        project_id="harbor-api",
        evidence=evidence,
        model_claims_complete=claim,
    )
    path = vault / "generated" / "ops" / "atlas3" / "proof" / f"AT3-103-GOLDEN-{name}.json"
    assert hashlib.sha256(path.read_bytes()).hexdigest() == expected


def test_v1_and_v2_namespaces_do_not_collide(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    ident = seal_execution_identity(identity_body())
    evaluate_proof(vault, "X", project_id="harbor-api")
    evaluate_proof(vault, "v2", project_id="harbor-api")
    report = evaluate_proof_v2(
        vault,
        "X",
        project_id="harbor-api",
        identity=ident,
        attestations=full_chain(ident.identity_digest),
    )
    assert report["chain_status"] == "PROVEN"
    assert (vault / "generated" / "ops" / "atlas3" / "proof" / "X.json").is_file()
    assert (vault / "generated" / "ops" / "atlas3" / "proof" / "v2.json").is_file()
    assert (_proof_dir(vault, "X") / f"{ident.identity_digest[:16]}.json").is_file()
    evaluate_proof(vault, "X", project_id="harbor-api")  # v1 again, still fine
    again = evaluate_proof_v2(
        vault,
        "X",
        project_id="harbor-api",
        identity=ident,
        attestations=full_chain(ident.identity_digest),
    )
    assert again == report


def test_locator_collision_with_a_different_digest_fails_closed(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    ident = seal_execution_identity(identity_body())
    target = _proof_dir(vault, "L") / f"{ident.identity_digest[:16]}.json"
    target.parent.mkdir(parents=True)
    # Same 16-char locator prefix, different full digest: the full digest is
    # the identity, the prefix is only a locator.
    prefix_collision = ident.identity_digest[:16] + (
        "0" if ident.identity_digest[16] != "0" else "1"
    )
    prefix_collision += ident.identity_digest[17:]
    assert prefix_collision != ident.identity_digest
    target.write_text(json.dumps({"identity_digest": prefix_collision}), encoding="utf-8")
    before = target.read_bytes()
    with pytest.raises(Atlas3Error) as excinfo:
        evaluate_proof_v2(vault, "L", project_id="harbor-api", identity=ident, attestations=[])
    assert excinfo.value.code == "PROOF_LOCATOR_COLLISION"
    assert target.read_bytes() == before
    assert not target.with_suffix(".json.tmp").exists()
    target.write_text("not json", encoding="utf-8")
    with pytest.raises(Atlas3Error) as excinfo:
        evaluate_proof_v2(vault, "L", project_id="harbor-api", identity=ident, attestations=[])
    assert excinfo.value.code == "PROOF_LOCATOR_COLLISION"


def _symlink(link: Path, target: Path) -> None:
    try:
        link.symlink_to(target, target_is_directory=target.is_dir())
    except (OSError, NotImplementedError):
        pytest.skip("symlinks unavailable")


def test_symlinked_locator_task_dir_or_namespace_is_refused_not_followed(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    ident = seal_execution_identity(identity_body())
    chain = full_chain(ident.identity_digest)
    evaluate_proof_v2(vault, "T1", project_id="harbor-api", identity=ident, attestations=chain)
    t1 = _proof_dir(vault, "T1") / f"{ident.identity_digest[:16]}.json"
    t1_bytes = t1.read_bytes()

    # (d) locator symlink -> sibling task's report (same identity)
    _proof_dir(vault, "T2").mkdir(parents=True)
    _symlink(_proof_dir(vault, "T2") / t1.name, t1)
    with pytest.raises(Atlas3Error) as excinfo:
        evaluate_proof_v2(vault, "T2", project_id="harbor-api", identity=ident, attestations=chain)
    assert excinfo.value.code == "PROOF_LOCATOR_UNSAFE"
    assert t1.read_bytes() == t1_bytes

    # (h) task directory symlink -> sibling task directory
    _symlink(_proof_dir(vault, "T6"), _proof_dir(vault, "T1"))
    with pytest.raises(Atlas3Error) as excinfo:
        evaluate_proof_v2(vault, "T6", project_id="harbor-api", identity=ident, attestations=chain)
    assert excinfo.value.code == "PROOF_LOCATOR_UNSAFE"
    assert t1.read_bytes() == t1_bytes

    # (f) dangling locator symlink inside the root
    _proof_dir(vault, "T4").mkdir(parents=True)
    _symlink(_proof_dir(vault, "T4") / t1.name, _proof_dir(vault, "ELSEWHERE") / "x.json")
    with pytest.raises(Atlas3Error) as excinfo:
        evaluate_proof_v2(vault, "T4", project_id="harbor-api", identity=ident, attestations=chain)
    assert excinfo.value.code == "PROOF_LOCATOR_UNSAFE"
    assert not _proof_dir(vault, "ELSEWHERE").exists()

    # task path exists as a regular file
    _proof_dir(vault, "T7").parent.mkdir(parents=True, exist_ok=True)
    _proof_dir(vault, "T7").write_text("x", encoding="utf-8")
    with pytest.raises(Atlas3Error) as excinfo:
        evaluate_proof_v2(vault, "T7", project_id="harbor-api", identity=ident, attestations=chain)
    assert excinfo.value.code == "PROOF_LOCATOR_UNSAFE"


def test_symlinked_v2_namespace_pointing_outside_the_vault_is_refused(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    ident = seal_execution_identity(identity_body())
    outside = tmp_path / "outside"
    outside.mkdir()
    ns = vault / "generated" / "ops" / "atlas3" / "proof" / "v2"
    ns.parent.mkdir(parents=True)
    _symlink(ns, outside)
    with pytest.raises(Atlas3Error) as excinfo:
        evaluate_proof_v2(vault, "J", project_id="harbor-api", identity=ident, attestations=[])
    assert excinfo.value.code == "PROOF_LOCATOR_UNSAFE"
    assert list(outside.iterdir()) == []


def test_containment_recheck_is_load_bearing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Defence in depth: even if the task-id guard were bypassed, the resolved
    locator must sit under the proof root."""
    from project_atlas.atlas3 import proof as proof_module

    vault = _vault(tmp_path)
    ident = seal_execution_identity(identity_body())
    monkeypatch.setattr(proof_module, "_safe_task_id", lambda _tid: "../../escape")
    with pytest.raises(Atlas3Error) as excinfo:
        evaluate_proof_v2(
            vault, "ignored", project_id="harbor-api", identity=ident, attestations=[]
        )
    assert excinfo.value.code == "UNSAFE_TASK_ID"
    assert not (vault / "generated" / "ops" / "atlas3" / "escape").exists()
    assert not (vault / "generated" / "ops" / "escape").exists()


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
    _refused(tmp_path, "SUMMARY_KEY_UNKNOWN", identity=ident, attestations=[record])


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


@pytest.mark.parametrize(
    "task_id",
    [
        "../x",
        "a/b",
        "a\\b",
        "D:evil",
        "a:b",
        "CON",
        "PRN",
        "con.txt",
        "x.",
        "x ",
        " x",
        "a\tb",
        "a\x00b",
        "a\x01b",
        "\u202eabc",
        "\u00e9",
        "x" * 129,
        "",
        ".",
        "..",
        "a b",
        "a\x7fb",
        "a<b",
        "a|b",
        'a"b',
        "a?b",
        "a*b",
        "-x",
        ".hidden",
        "AKIAIOSFODNN7EXAMPLE:x",
    ],
)
def test_unsafe_task_ids_are_refused_before_any_write(tmp_path: Path, task_id: str) -> None:
    vault = _vault(tmp_path)
    ident = seal_execution_identity(identity_body())
    with pytest.raises(Atlas3Error) as excinfo:
        evaluate_proof_v2(vault, task_id, project_id="harbor-api", identity=ident, attestations=[])
    assert excinfo.value.code == "UNSAFE_TASK_ID"
    assert "AKIA" not in str(excinfo.value)
    assert not (vault / "generated").exists()


@pytest.mark.parametrize("task_id", [42, None, b"x", ["x"]])
def test_non_string_task_ids_are_refused(tmp_path: Path, task_id: Any) -> None:
    vault = _vault(tmp_path)
    ident = seal_execution_identity(identity_body())
    with pytest.raises(Atlas3Error) as excinfo:
        evaluate_proof_v2(vault, task_id, project_id="harbor-api", identity=ident, attestations=[])
    assert excinfo.value.code == "UNSAFE_TASK_ID"


def test_accepted_task_ids_are_a_bounded_ascii_identifier(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    ident = seal_execution_identity(identity_body())
    for tid in ("X", "AT3-103", "a.b.c", "v2", "x" * 128, "T_1"):
        evaluate_proof_v2(vault, tid, project_id="harbor-api", identity=ident, attestations=[])
        assert (_proof_dir(vault, tid) / f"{ident.identity_digest[:16]}.json").is_file()


@pytest.mark.parametrize("attestations", [None, "x", b"x", {"attestations": []}, 3])
def test_attestations_must_be_a_sequence(tmp_path: Path, attestations: Any) -> None:
    vault = _vault(tmp_path)
    ident = seal_execution_identity(identity_body())
    with pytest.raises(Atlas3Error) as excinfo:
        evaluate_proof_v2(
            vault, "SEQ", project_id="harbor-api", identity=ident, attestations=attestations
        )
    assert excinfo.value.code == "ATTESTATIONS_INVALID"
    assert not (vault / "generated").exists()


def test_seal_mode_draft_instance_cannot_carry_placeholder_digest(tmp_path: Path) -> None:
    """ADV S2: an instance is re-validated from its record, never trusted."""
    from atlas_contracts.attestation import EvidenceAttestation
    from atlas_contracts.execution_identity import ExecutionIdentity

    vault = _vault(tmp_path)
    draft = ExecutionIdentity.model_validate(
        identity_body(), context={"atlas_contracts.seal": True}
    )
    assert draft.identity_digest == "0" * 64
    with pytest.raises(Atlas3Error) as excinfo:
        evaluate_proof_v2(vault, "S2", project_id="harbor-api", identity=draft, attestations=[])
    assert excinfo.value.code == "IDENTITY_DIGEST_MISMATCH"
    ident = seal_execution_identity(identity_body())
    sealed = seal_evidence_attestation(
        attestation_body(ident.identity_digest, "TESTS", result={"status": "FAIL"})
    )
    flipped = sealed.model_copy(
        update={"result": sealed.result.model_copy(update={"status": "PASS"})}
    )
    with pytest.raises(Atlas3Error) as excinfo:
        evaluate_proof_v2(
            vault, "S2", project_id="harbor-api", identity=ident, attestations=[flipped]
        )
    assert excinfo.value.code == "ATTESTATION_HASH_MISMATCH"
    constructed = EvidenceAttestation.model_construct(**sealed.model_dump())
    constructed = constructed.model_copy(update={"content_hash": "f" * 64})
    with pytest.raises(Atlas3Error):
        evaluate_proof_v2(
            vault, "S2", project_id="harbor-api", identity=ident, attestations=[constructed]
        )
    assert not _proof_dir(vault, "S2").exists()


def _constructed_attestation(ident_digest: str, stage: str, **over: Any) -> Any:
    """Build an attestation instance that never passed validation."""
    from atlas_contracts.attestation import (
        AttestationResult,
        EvidenceAttestation,
        ObjectBinding,
        Producer,
    )

    base = attestation_body(ident_digest, stage)
    producer = dict(base["producer"])
    producer.update(over.pop("producer", {}))
    result = dict(base["result"])
    result.update(over.pop("result", {}))
    return EvidenceAttestation.model_construct(
        schema_id="atlas.evidence-attestation.v1",
        schema_version=1,
        project_id="harbor-api",
        execution_identity_digest=ident_digest,
        stage=stage,
        evidence_type=base["evidence_type"],
        producer=Producer.model_construct(**producer),
        object_binding=ObjectBinding.model_construct(head=HEAD, tree=TREE),
        command_ref=None,
        result=AttestationResult.model_construct(**result),
        dependencies=("DEP_HEAD", "DEP_TREE"),
        content_hash="0" * 64,
        attestation_id="att-" + "0" * 16,
    )


@pytest.mark.parametrize(
    ("stage", "over", "codes"),
    [
        ("TESTS", {}, {"ATTESTATION_HASH_MISMATCH"}),
        (
            "TESTS",
            {"producer": {"kind": "model", "name": "claude"}},
            {"MODEL_PRODUCER_NOT_EVIDENCE", "ATTESTATION_MALFORMED"},
        ),
        (
            "INDEPENDENT_VERIFICATION",
            {"producer": {"independent_of_implementer": False}},
            {"INDEPENDENCE_NOT_DECLARED", "ATTESTATION_MALFORMED"},
        ),
        (
            "ADV",
            {"producer": {"independent_of_implementer": False}},
            {"INDEPENDENCE_NOT_DECLARED", "ATTESTATION_MALFORMED"},
        ),
        (
            "TESTS",
            {"result": {"summary": {"merge_authorization": 1}}},
            {"SUMMARY_KEY_UNKNOWN", "ATTESTATION_MALFORMED"},
        ),
    ],
)
def test_model_construct_instances_are_revalidated_and_refused(
    tmp_path: Path, stage: str, over: dict[str, Any], codes: set[str]
) -> None:
    vault = _vault(tmp_path)
    ident = seal_execution_identity(identity_body())
    instance = _constructed_attestation(ident.identity_digest, stage, **over)
    with pytest.raises(Atlas3Error) as excinfo:
        evaluate_proof_v2(
            vault, "MC", project_id="harbor-api", identity=ident, attestations=[instance]
        )
    assert excinfo.value.code in codes, str(excinfo.value)
    assert not (vault / "generated").exists()


def test_seal_mode_draft_attestation_instance_is_refused(tmp_path: Path) -> None:
    from atlas_contracts.attestation import EvidenceAttestation

    vault = _vault(tmp_path)
    ident = seal_execution_identity(identity_body())
    draft = EvidenceAttestation.model_validate(
        attestation_body(ident.identity_digest, "TESTS"), context={"atlas_contracts.seal": True}
    )
    assert draft.content_hash == "0" * 64
    with pytest.raises(Atlas3Error) as excinfo:
        evaluate_proof_v2(
            vault, "SD", project_id="harbor-api", identity=ident, attestations=[draft]
        )
    assert excinfo.value.code == "ATTESTATION_HASH_MISMATCH"
    sealed = seal_evidence_attestation(attestation_body(ident.identity_digest, "TESTS"))
    moved = sealed.model_copy(
        update={"object_binding": sealed.object_binding.model_copy(update={"tree": "d" * 40})}
    )
    with pytest.raises(Atlas3Error) as excinfo:
        evaluate_proof_v2(
            vault, "SD", project_id="harbor-api", identity=ident, attestations=[moved]
        )
    assert excinfo.value.code == "ATTESTATION_HASH_MISMATCH"
    assert not (vault / "generated").exists()


@pytest.mark.parametrize(
    "command_ref",
    [
        "curl -H 'Authorization: Bearer AKIAIOSFODNN7EXAMPLE'",
        "curl -H 'Authorization: Bearer\tAKIAIOSFODNN7EXAMPLE'",
        "curl -H 'Authorization: Bearer\nAKIAIOSFODNN7EXAMPLE'",
        "run --api_key=AKIAIOSFODNN7EXAMPLE",
        "run --api_key = AKIAIOSFODNN7EXAMPLE",
        'run api_key="AKIAIOSFODNN7EXAMPLE"',
        "run api_key='AKIAIOSFODNN7EXAMPLE'",
        "run api_key=\nAKIAIOSFODNN7EXAMPLE",
        "password = AKIAIOSFODNN7EXAMPLE",
        "password\t=\tAKIAIOSFODNN7EXAMPLE",
    ],
)
def test_secret_shaped_command_refs_are_refused_in_every_adjacency_form(
    tmp_path: Path, command_ref: str
) -> None:
    ident = seal_execution_identity(identity_body())
    record = seal_evidence_attestation(
        attestation_body(ident.identity_digest, "TESTS", command_ref=command_ref)
    ).to_record()
    _refused(tmp_path, "PROOF_SECRET_FORBIDDEN", identity=ident, attestations=[record])


def test_benign_values_are_not_falsely_refused_and_secret_names_are_not_echoed(
    tmp_path: Path,
) -> None:
    vault = _vault(tmp_path)
    ident = seal_execution_identity(identity_body())
    benign = seal_evidence_attestation(
        attestation_body(
            ident.identity_digest,
            "TESTS",
            command_ref="python -m pytest tests/unit --junitxml=out.xml -k 'not slow'",
        )
    ).to_record()
    report = evaluate_proof_v2(
        vault, "B", project_id="harbor-api", identity=ident, attestations=[benign]
    )
    assert report["stages"]["TESTS"]["status"] == "PRESENT"
    ident2 = seal_execution_identity(identity_body())
    bad = seal_evidence_attestation(
        attestation_body(
            ident2.identity_digest, "TESTS", command_ref="x --api_key=AKIAIOSFODNN7EXAMPLE"
        )
    ).to_record()
    with pytest.raises(Atlas3Error) as excinfo:
        evaluate_proof_v2(vault, "B2", project_id="harbor-api", identity=ident2, attestations=[bad])
    assert "AKIAIOSFODNN7EXAMPLE" not in str(excinfo.value)


def test_report_does_not_persist_free_form_input_values(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    ident = seal_execution_identity(
        identity_body(
            toolchain={
                "status": "OBSERVED",
                "tools": [{"name": "pytest", "version": "8.3.2+sentinelv"}],
            },
        )
    )
    atts = [
        seal_evidence_attestation(
            attestation_body(
                ident.identity_digest,
                stage,
                command_ref="SENTINEL-COMMAND-REF",
                result={"status": "PASS", "summary": {"passed": 4242}},
            )
        ).to_record()
        for stage in PROOF_STAGES
    ]
    evaluate_proof_v2(vault, "RC", project_id="harbor-api", identity=ident, attestations=atts)
    text = (_proof_dir(vault, "RC") / f"{ident.identity_digest[:16]}.json").read_text(
        encoding="utf-8"
    )
    assert "SENTINEL-COMMAND-REF" not in text
    assert "sentinelv" not in text
    assert "4242" not in text
    assert "b0lk13" not in text


def test_unknown_status_attestation_alone_is_not_present(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    ident = seal_execution_identity(identity_body())
    unknown = seal_evidence_attestation(
        attestation_body(ident.identity_digest, "TESTS", result={"status": "UNKNOWN"})
    ).to_record()
    report = evaluate_proof_v2(
        vault, "UNK", project_id="harbor-api", identity=ident, attestations=[unknown]
    )
    assert report["stages"]["TESTS"]["status"] == "UNKNOWN"
    assert report["present_count"] == 0
    assert report["independence_verified"] is False
    assert report["independence_declared_only"] is True


def test_tampered_attestation_id_is_refused(tmp_path: Path) -> None:
    ident = seal_execution_identity(identity_body())
    record = seal_evidence_attestation(attestation_body(ident.identity_digest, "TESTS")).to_record()
    record["attestation_id"] = "att-" + "f" * 16
    _refused(tmp_path, "ATTESTATION_ID_MISMATCH", identity=ident, attestations=[record])


def test_secret_shaped_attestation_content_is_refused_even_when_whitespace_adjacent(
    tmp_path: Path,
) -> None:
    ident = seal_execution_identity(identity_body())
    record = seal_evidence_attestation(
        attestation_body(
            ident.identity_digest,
            "TESTS",
            command_ref="curl -H 'Authorization: Bearer\tAKIAIOSFODNN7EXAMPLE' https://x",
        )
    ).to_record()
    _refused(tmp_path, "PROOF_SECRET_FORBIDDEN", identity=ident, attestations=[record])
    ident_secret_task = seal_execution_identity(identity_body())
    vault = _vault(tmp_path)
    with pytest.raises(Atlas3Error) as excinfo:
        evaluate_proof_v2(
            vault,
            "AKIAIOSFODNN7EXAMPLE",
            project_id="harbor-api",
            identity=ident_secret_task,
            attestations=[],
        )
    assert excinfo.value.code == "PROOF_SECRET_FORBIDDEN"


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


def test_cli_refuses_symlink_oversize_and_nested_inputs(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    vault = _vault(tmp_path)
    ident = seal_execution_identity(identity_body())
    real_identity = tmp_path / "identity.json"
    real_identity.write_text(json.dumps(ident.to_record()), encoding="utf-8")
    atts_ok = tmp_path / "atts.json"
    atts_ok.write_text(json.dumps(full_chain(ident.identity_digest)), encoding="utf-8")

    def run(identity: Path, atts: Path) -> str:
        code = main(
            [
                "proof",
                "X",
                "--vault",
                str(vault),
                "--project",
                "harbor-api",
                "--identity",
                str(identity),
                "--attestations",
                str(atts),
            ]
        )
        assert code == EXIT_ERROR
        return str(json.loads(capsys.readouterr().out)["error"])

    link = tmp_path / "identity-link.json"
    try:
        link.symlink_to(real_identity)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks unavailable")
    assert run(link, atts_ok) == "PROOF_INPUT_INVALID"
    big = tmp_path / "big.json"
    big.write_bytes(b"[" + b" " * 1_048_576 + b"]")
    assert run(real_identity, big) == "PROOF_INPUT_INVALID"
    nested = tmp_path / "nested.json"
    nested.write_text("[" * 200_000 + "]" * 200_000, encoding="utf-8")
    assert run(real_identity, nested) == "PROOF_INPUT_INVALID"
    wrapped = tmp_path / "wrapped.json"
    wrapped.write_text(
        json.dumps({"attestations": full_chain(ident.identity_digest)}), encoding="utf-8"
    )
    assert (
        main(
            [
                "proof",
                "W",
                "--vault",
                str(vault),
                "--project",
                "harbor-api",
                "--identity",
                str(real_identity),
                "--attestations",
                str(wrapped),
            ]
        )
        == EXIT_OK
    )
    assert json.loads(capsys.readouterr().out)["chain_status"] == "PROVEN"
    assert (
        main(
            [
                "proof",
                "C",
                "--vault",
                str(vault),
                "--project",
                "harbor-api",
                "--identity",
                str(real_identity),
                "--attestations",
                str(atts_ok),
                "--evidence",
                "{}",
            ]
        )
        == EXIT_ERROR
    )
    assert json.loads(capsys.readouterr().out)["error"] == "PROOF_V2_INPUTS_CONFLICT"
    assert (
        main(
            [
                "proof",
                "C2",
                "--vault",
                str(vault),
                "--project",
                "harbor-api",
                "--identity",
                str(real_identity),
                "--attestations",
                str(atts_ok),
                "--evidence",
                "",
            ]
        )
        == EXIT_ERROR
    )
    assert json.loads(capsys.readouterr().out)["error"] == "PROOF_V2_INPUTS_CONFLICT"
    dup = tmp_path / "dup.json"
    text = json.dumps(ident.to_record())
    dup.write_text(text[:-1] + ',"project_id":"harbor-api"}', encoding="utf-8")
    assert run(dup, atts_ok) == "PROOF_INPUT_INVALID"


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
