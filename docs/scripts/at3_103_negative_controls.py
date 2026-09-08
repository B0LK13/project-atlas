"""AT3-103 negative controls: each mutation must fail a distinct, named test set; source restored byte-identical."""
import hashlib, json, subprocess, sys, tempfile
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
PY = Path(sys.executable)
TESTS = ["tests/unit/test_atlas_contracts_canonical_103.py","tests/unit/test_atlas_contracts_execution_identity_103.py","tests/unit/test_atlas_contracts_attestation_103.py","tests/unit/test_atlas3_proof_v2_103.py"]
CONTROLS = {
 "NC-A object==candidate check removed": ("src/project_atlas/atlas3/proof.py",
   "        if att.object_binding.head != head or att.object_binding.tree != tree:",
   "        if False:"),
 "NC-B content_hash recomputation skipped": ("src/atlas_contracts/attestation.py",
   "        if self.content_hash != expected:",
   "        if False:"),
 "NC-C model/agent producer denylist dropped": ("src/atlas_contracts/attestation.py",
   '        if self.kind == "model":',
   '        if False:'),
 "NC-D ensure_ascii=False in canonical helper": ("src/atlas_contracts/canonical.py",
   "            ensure_ascii=True,",
   "            ensure_ascii=False,"),
 "NC-E report written before validation": ("src/project_atlas/atlas3/proof.py",
   "    loaded: list[EvidenceAttestation] = []\n",
   "    write_json_atomic(root / OPS_RELATIVE / 'proof' / tid / 'early.json', {'early': True})\n    loaded: list[EvidenceAttestation] = []\n"),
 "NC-F attestation secret scan dropped (ADV M05)": ("src/project_atlas/atlas3/proof.py",
   "        _scan_for_secrets(att.to_record())\n", "        pass\n"),
 "NC-G PRESENT without PASS (ADV M09)": ("src/project_atlas/atlas3/proof.py",
   "        elif passes:", "        elif matching:"),
 "NC-H attestation_id derivation unchecked (ADV M22)": ("src/atlas_contracts/attestation.py",
   "        if self.attestation_id != short_id(ATTESTATION_ID_PREFIX, expected):", "        if False:"),
 "NC-I symlink accepted (ADV M38)": ("src/project_atlas/atlas3/cli.py",
   "    if not path.is_file() or path.is_symlink():", "    if not path.is_file():"),
 "NC-J size cap dropped (ADV M39)": ("src/project_atlas/atlas3/cli.py",
   "    if path.stat().st_size > _MAX_PROOF_INPUT_BYTES:", "    if False:"),
 "NC-K instance trusted without re-validation (ADV M42)": ("src/project_atlas/atlas3/proof.py",
   "    if isinstance(identity, ExecutionIdentity):\n        identity = identity.to_record()",
   "    if isinstance(identity, ExecutionIdentity):\n        return identity"),
 "NC-L task id guard weakened to v1 check": ("src/project_atlas/atlas3/proof.py",
   "        return safe_relative_component(task_id, label=\"task id\")",
   "        return task_id"),
 "NC-M RecursionError not wrapped": ("src/project_atlas/atlas3/cli.py",
   "    except (OSError, UnicodeError, ValueError, RecursionError) as exc:",
   "    except (OSError, UnicodeError, ValueError) as exc:"),
 "NC-N locator collision check dropped": ("src/project_atlas/atlas3/proof.py",
   "        if existing is None or existing.get(\"identity_digest\") != ident.identity_digest:",
   "        if False:"),
 "NC-O duplicate JSON keys accepted": ("src/project_atlas/atlas3/cli.py",
   "        if key in result:\n            raise ValueError", "        if False:\n            raise ValueError"),
 "NC-P summary positive vocabulary dropped": ("src/atlas_contracts/attestation.py",
   "            if key not in SUMMARY_COUNTERS:", "            if False:"),
 "NC-Q task-id secret scan dropped": ("src/project_atlas/atlas3/proof.py",
   "    _scan_for_secrets({\"task_id\": tid})\n", "    pass\n"),
 "NC-R raw-value secret scan dropped (canonical text only)": ("src/project_atlas/atlas3/proof.py",
   "    for text in [canonical_json(payload), *_string_values(payload)]:", "    for text in [canonical_json(payload)]:"),
 "NC-S v2 namespace collapsed onto v1": ("src/project_atlas/atlas3/proof.py",
   "PROOF_V2_RELATIVE: Final[Path] = OPS_RELATIVE / \"proof\" / \"v2\"", "PROOF_V2_RELATIVE: Final[Path] = OPS_RELATIVE / \"proof\""),
 "NC-T strict summary ints relaxed": ("src/atlas_contracts/attestation.py",
   "    summary: dict[str, Annotated[StrictInt, Field(ge=0, le=MAX_SUMMARY_COUNT)]] = Field(",
   "    summary: dict[str, Annotated[int, Field(ge=0, le=MAX_SUMMARY_COUNT)]] = Field("),
 "NC-U symlink component walk dropped": ("src/project_atlas/atlas3/proof.py",
   "        if current.is_symlink():", "        if False:"),
 "NC-V resolved containment re-check dropped": ("src/project_atlas/atlas3/proof.py",
   "    if not target.resolve().is_relative_to((root / PROOF_V2_RELATIVE).resolve()):", "    if False:"),
 "NC-W attestations sequence check dropped": ("src/project_atlas/atlas3/proof.py",
   "    if isinstance(attestations, (str, bytes, Mapping)) or not isinstance(attestations, Sequence):", "    if False:"),
 "NC-X --evidence empty string conflict dropped": ("src/project_atlas/atlas3/cli.py",
   "                if getattr(args, \"evidence\", None) is not None:", "                if getattr(args, \"evidence\", None):"),
 "NC-Y task-id identifier pattern dropped": ("src/project_atlas/atlas3/proof.py",
   "    if not isinstance(task_id, str) or not _TASK_ID_RE.fullmatch(task_id):", "    if not isinstance(task_id, str):"),
 "NC-Z schema_version strictness relaxed (attestation)": ("src/atlas_contracts/attestation.py",
   "    schema_version: StrictInt = Field(default=1, ge=1, le=1)", "    schema_version: int = Field(default=1, ge=1, le=1)"),
 "NC-AA summary count upper bound dropped": ("src/atlas_contracts/attestation.py",
   "MAX_SUMMARY_COUNT: Final[int] = 10**9", "MAX_SUMMARY_COUNT: Final[int] = 10**40"),
 "NC-AB task-dir-is-file check dropped": ("src/project_atlas/atlas3/proof.py",
   "    if task_dir.exists() and not task_dir.is_dir():", "    if False:"),
}
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def failing():
    xml = Path(tempfile.mkdtemp(prefix="at3-103-nc-")) / "nc.xml"
    subprocess.run([str(PY),"-m","pytest","-p","no:cacheprovider","--no-cov","-q","-o","addopts=","--junitxml",str(xml),*TESTS],cwd=ROOT,capture_output=True,env=None)
    import xml.etree.ElementTree as ET
    root = ET.parse(xml).getroot(); s = root if root.tag=="testsuite" else root[0]
    names = sorted(f"{tc.get('classname')}::{tc.get('name')}" for tc in s.iter("testcase") if tc.find("failure") is not None or tc.find("error") is not None)
    return int(s.get("tests")), names
out = {}
base_total, base_fail = failing(); assert not base_fail, base_fail
out["baseline"] = {"tests": base_total, "failures": 0}
for name,(rel,old,new) in CONTROLS.items():
    p = ROOT/rel; before = sha(p); text = p.read_text()
    assert old in text, (name, "anchor missing")
    p.write_text(text.replace(old,new,1)); assert sha(p) != before, name
    try:
        total, fails = failing()
    finally:
        p.write_text(text); assert sha(p) == before, (name, "restore failed")
    out[name] = {"tests": total, "failures": len(fails), "failing": fails}
sets = {k: set(v["failing"]) for k,v in out.items() if k!="baseline"}
keys = list(sets)
out["pairwise_distinct"] = all(sets[a] != sets[b] for i,a in enumerate(keys) for b in keys[i+1:])
out["each_nonempty"] = all(sets[k] for k in keys)
print(json.dumps(out, indent=1))
