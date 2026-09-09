"""ULT-01b-1 negative controls.

Each mutation must fail at least one of the ULT-01b-1 suites (receipt contract,
observer unit, live integration); the source is restored byte-identical
(sha256-asserted) after every control. Failing test names are recorded per
control; `pairwise_distinct` is REPORTED, not asserted. The store's
identity-digest collision check is covered by the AT3-103 matrix (NC-N) and,
for receipts, subsumed by the content_hash check (OC-X). Run from the
repository root with the project venv:
    python docs/scripts/ult_01b_1_negative_controls.py
"""
import hashlib, json, subprocess, sys, tempfile
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
PY = Path(sys.executable)
TESTS = ["tests/unit/test_atlas_contracts_observation_receipt_01b.py","tests/unit/test_execution_observation_01b.py","tests/integration/test_execution_observation_live_01b.py","tests/unit/test_authz_execution_observe_01b.py"]
CONTROLS = {
 "OC-A dirty worktree accepted": ("src/project_atlas/execution_observation/git.py",
   "    if status:\n        raise ObservationError(\n            \"WORKTREE_NOT_CLEAN\"", "    if False:\n        raise ObservationError(\n            \"WORKTREE_NOT_CLEAN\""),
 "OC-B pin validation dropped": ("src/project_atlas/execution_observation/git.py",
   "            return require_full_pin(out, ref)", "            return out"),
 "OC-C userinfo remote accepted": ("src/project_atlas/execution_observation/git.py",
   "        if not at or user != \"git\" or \"@\" in tail:", "        if False:"),
 "OC-D child env inherited": ("src/project_atlas/execution_observation/runner.py",
   "    for key in PASSTHROUGH_ENV:\n        value = source.get(key)", "    for key in source:\n        value = source.get(key)"),
 "OC-E windows wrapper accepted": ("src/project_atlas/execution_observation/runner.py",
   "    if effective_os == \"nt\" and resolved.suffix.lower() != WINDOWS_EXECUTABLE_SUFFIX:", "    if False:"),
 "OC-F unmapped arch guessed": ("src/project_atlas/execution_observation/host.py",
   "    arch_token = ARCH_NORMALIZATION.get(raw_arch.strip().lower())", "    arch_token = ARCH_NORMALIZATION.get(raw_arch.strip().lower(), raw_arch.strip().lower() or None)"),
 "OC-G toolchain invalid version accepted": ("src/project_atlas/execution_observation/host.py",
   "        if version is None or not _VERSION_RE.fullmatch(str(version)):", "        if version is None:"),
 "OC-H receipt dimension/identity consistency dropped": ("src/atlas_contracts/observation_receipt.py",
   "            if observed != expected[name]:", "            if False:"),
 "OC-I receipt hash recomputation skipped": ("src/atlas_contracts/observation_receipt.py",
   "        if self.content_hash != digest:", "        if False:"),
 "OC-J method refs may carry urls": ("src/atlas_contracts/observation_receipt.py",
   "    return bool(re.fullmatch(METHOD_REF_PATTERN, ref)) and \"://\" not in ref and \"@\" not in ref", "    return True"),
 "OC-K proof linkage identity check dropped": ("src/project_atlas/atlas3/proof.py",
   "        if observation.identity_digest != ident.identity_digest:", "        if False:"),
 "OC-M store symlink walk dropped": ("src/project_atlas/atlas3/contracts.py",
   "        if current.is_symlink() or current.is_junction():", "        if False:"),
 "OC-O root must be toplevel dropped": ("src/project_atlas/execution_observation/git.py",
   "        if Path(toplevel).resolve(strict=True) != root:", "        if False:"),
 "OC-P base-ref validation dropped": ("src/project_atlas/execution_observation/git.py",
   "        or not _REF_RE.fullmatch(base_ref)\n        or \"..\" in base_ref\n", ""),
 "OC-Q timeout not distinguished": ("src/project_atlas/execution_observation/git.py",
   "            raise ObservationError(\"GIT_OBSERVATION_TIMEOUT\", f\"{ref}: timed out\")", "            raise ObservationError(code, f\"{ref}: timed out\")"),
 "OC-R secret scan of receipt dropped": ("src/project_atlas/execution_observation/observe.py",
   "    _scan_for_secrets(receipt.to_record())", "    pass"),
 "OC-S receipt observer kind widened to model": ("src/atlas_contracts/observation_receipt.py",
   "    kind: Literal[\"tool\"]", "    kind: Literal[\"tool\", \"model\", \"agent\", \"human\", \"ci\"]"),
 "OC-T unsafe project id accepted": ("src/project_atlas/execution_observation/observe.py",
   "        pid = safe_relative_component(project_id, label=\"project id\")", "        pid = project_id"),
 "OC-U core.fsmonitor pin dropped (repo/global hook command would run)": ("src/project_atlas/execution_observation/runner.py",
   "    \"GIT_CONFIG_COUNT\": \"1\",\n    \"GIT_CONFIG_KEY_0\": \"core.fsmonitor\",\n    \"GIT_CONFIG_VALUE_0\": \"false\",\n", ""),
 "OC-V remote read through get-url (insteadOf applied)": ("src/project_atlas/execution_observation/git.py",
   "        [\"config\", \"-z\", \"--get-all\", f\"remote.{remote}.url\"],", "        [\"remote\", \"get-url\", remote],"),
 "OC-W hostless/local-path remote accepted": ("src/project_atlas/execution_observation/git.py",
   "    if \".\" not in host or not rest or url.lower().startswith(\"file:\") or url.startswith(\"/\"):", "    if False:"),
 "OC-X same-identity different receipt overwritten": ("src/project_atlas/execution_observation/store.py",
   "            content_field=\"content_hash\",\n", ""),
 "OC-Y raw remote url secret scan dropped": ("src/project_atlas/execution_observation/git.py",
   "    if scan_text(url):", "    if False:"),
 "OC-Z observed_is_current strictness dropped": ("src/atlas_contracts/observation_receipt.py",
   "        if self.observed_is_current is not False:", "        if False:"),
 "OC-AA store digest argument unvalidated": ("src/project_atlas/execution_observation/store.py",
   "    if not isinstance(identity_digest, str) or not _DIGEST_RE.fullmatch(identity_digest):", "    if False:"),
 "OC-AB base-ref length ceiling dropped": ("src/project_atlas/execution_observation/git.py",
   "        or len(base_ref) > MAX_BASE_REF_LENGTH\n", ""),
 "OC-AC multi-valued remote url accepted (first taken)": ("src/project_atlas/execution_observation/git.py",
   "    if len(urls) != 1:", "    if not urls:"),
 "OC-AD bound content filter scan dropped": ("src/project_atlas/execution_observation/git.py",
   "        if bound:\n            raise ObservationError(\n                \"REPO_CONTENT_FILTERS_CONFIGURED\",", "        if False:\n            raise ObservationError(\n                \"REPO_CONTENT_FILTERS_CONFIGURED\","),
 "OC-AE submodule work trees observed (nested git status spawned)": ("src/project_atlas/execution_observation/git.py",
   "            \"--ignore-submodules=dirty\",\n        ],", "        ],"),
 "OC-AF filter driver name not validated": ("src/project_atlas/execution_observation/git.py",
   "        if not _FILTER_DRIVER_RE.fullmatch(name):", "        if False:"),
 # --- operational authorization (owner grant OG-ULT-01B-1-AUTHZ-EXECUTION-OBSERVE-20260909)
 "OC-AG execution.observe granted to the default operator": ("src/project_atlas/authz.py",
   "        \"scheduler.arm\",\n        \"chatgpt.bridge\",\n        \"collab.session\",\n    }\n)\n\n# Caps that a read session credential may carry",
   "        \"scheduler.arm\",\n        \"chatgpt.bridge\",\n        \"collab.session\",\n        \"execution.observe\",\n    }\n)\n\n# Caps that a read session credential may carry"),
 "OC-AH execution.observe carried by read credentials": ("src/project_atlas/authz.py",
   "        \"collab.session\",\n    }\n)\n\n# Privileged / mutating capabilities",
   "        \"collab.session\",\n        \"execution.observe\",\n    }\n)\n\n# Privileged / mutating capabilities"),
 "OC-AI execution.observe demoted from privileged": ("src/project_atlas/authz.py",
   "        # receipt under the vault; dedicated capability, default off (O3).\n        \"execution.observe\",\n", ""),
 "OC-AJ CLI observation gate removed (default operator observes)": ("src/project_atlas/atlas3/cli.py",
   "                require_cli_elevated_operator(\n                    \"local-operator-observe\",\n                    required={cast(Capability, OBSERVE_CAPABILITY)},\n                )",
   "                pass"),
 "OC-AK CLI elevation allow-list not checked for completeness": ("src/project_atlas/authz.py",
   "    if missing:\n        raise AuthzError(", "    if False:\n        raise AuthzError("),
 # --- ULT-01b-1-T: guards the ADV harnesses found protected only by the sha pin / untested
 "OC-AL CLI gate: unknown required capability not refused (Z06)": ("src/project_atlas/authz.py",
   "    unknown = needed - ALL_CAPABILITIES\n", "    unknown = set()\n"),
 "OC-AM CLI allow-list accepts a wildcard (Z08)": ("src/project_atlas/authz.py",
   "    granted = {part.strip() for part in raw.split(\",\") if part.strip()}\n",
   "    granted = {part.strip() for part in raw.split(\",\") if part.strip()}\n    if \"*\" in granted:\n        granted = set(needed)\n"),
 "OC-AN CLI allow-list case-insensitive (Z09)": ("src/project_atlas/authz.py",
   "    granted = {part.strip() for part in raw.split(\",\") if part.strip()}\n",
   "    granted = {part.strip().lower() for part in raw.split(\",\") if part.strip()}\n"),
 "OC-AO CLI allow-list prefix match (Z10)": ("src/project_atlas/authz.py",
   "    missing = sorted(cap for cap in needed if cap not in granted)\n",
   "    missing = sorted(cap for cap in needed if not any(cap.startswith(g) or g.startswith(cap) for g in granted))\n"),
 "OC-AP elevated_operator unknown-capability check dropped (Z11)": ("src/project_atlas/authz.py",
   "    unknown = caps - set(ALL_CAPABILITIES)\n", "    unknown = set()\n"),
 "OC-AQ read credential widened to the launch operator (Z16)": ("src/project_atlas/authz.py",
   "        capabilities=frozenset(base.capabilities & READ_ONLY_CAPABILITIES)\n",
   "        capabilities=frozenset(base.capabilities)\n"),
 "OC-AR filter scan regexp reduced to clean drivers (W12)": ("src/project_atlas/execution_observation/git.py",
   "        [\"config\", \"-z\", \"--get-regexp\", r\"^filter\\..*\\.(clean|smudge|process)$\"],",
   "        [\"config\", \"-z\", \"--get-regexp\", r\"^filter\\..*\\.(clean)$\"],"),
 "OC-AS filter scan restricted to repo-local config (W20)": ("src/project_atlas/execution_observation/git.py",
   "        [\"config\", \"-z\", \"--get-regexp\", r\"^filter\\..*\\.(clean|smudge|process)$\"],",
   "        [\"config\", \"--local\", \"-z\", \"--get-regexp\", r\"^filter\\..*\\.(clean|smudge|process)$\"],"),
 "OC-AT runner stdin inherited (U03)": ("src/project_atlas/execution_observation/runner.py",
   "                stdin=subprocess.DEVNULL,\n", ""),
 "OC-AU runner stdout cap dropped (U04)": ("src/project_atlas/execution_observation/runner.py",
   "        raw = completed.stdout[:MAX_STDOUT_BYTES] if completed.stdout else b\"\"\n",
   "        raw = completed.stdout if completed.stdout else b\"\"\n"),
 "OC-AV is-inside-work-tree accepted by prefix (U14)": ("src/project_atlas/execution_observation/git.py",
   "    if inside != \"true\":", "    if not inside.lower().startswith(\"true\"):"),
 # (U21 "second @ in tail" is a redundant guard: normalize_repository_identity refuses it too; no control)
 "OC-AX receipt secret scan skips dict keys (U41)": ("src/project_atlas/execution_observation/observe.py",
   "            found.append(str(key))\n", ""),
 "OC-AY default git executable is a bare name (U45)": ("src/project_atlas/execution_observation/observe.py",
   "    git = git_executable if git_executable is not None else resolve_executable(\"git\")",
   "    git = git_executable if git_executable is not None else Path(\"git\")"),
 "OC-AZ receipt git scalars not strict (U68/U69)": ("src/atlas_contracts/observation_receipt.py",
   "    worktree_clean: StrictBool | None = None\n    shallow: StrictBool | None = None\n",
   "    worktree_clean: bool | None = None\n    shallow: bool | None = None\n"),
 "OC-BA proof v2 trusts receipt instances (U80)": ("src/project_atlas/atlas3/proof.py",
   "    if isinstance(receipt, ObservationReceipt):\n        receipt = receipt.to_record()\n",
   "    if isinstance(receipt, ObservationReceipt):\n        return receipt\n"),
 "OC-BB proof v2 receipt secret scan dropped (U81)": ("src/project_atlas/atlas3/proof.py",
   "        _scan_for_secrets(observation.to_record())\n", ""),
}
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def failing():
    xml = Path(tempfile.mkdtemp(prefix="ult-01b-nc-")) / "nc.xml"
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
