"""Trusted-anchor load, verify, and fail-closed advancement.

BOOTSTRAP_MAIN/TREE are historical genesis only.
TRUSTED_RUNTIME_MAIN/TREE come from a verified record.
OBSERVED_MAIN/TREE are live facts and never become authority by themselves.

GOVERNOR_CAN_INVENT_OWNER_AUTHORITY = NO
GOVERNOR_CAN_ADVANCE_ANCHOR_FROM_OBSERVED_MAIN_ONLY = NO
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from typing import Protocol

from project_atlas.orchestration.autonomy.evidence import hash_payload
from project_atlas.orchestration.autonomy.models import (
    BOOTSTRAP_MAIN,
    BOOTSTRAP_TREE,
    CANONICAL_REPOSITORY_IDENTITY,
    INITIAL_RETARGET_CERTIFIED_HEAD,
    INITIAL_RETARGET_EVIDENCE_DIGEST,
    INITIAL_RETARGET_MAIN,
    INITIAL_RETARGET_SOURCE_DIRECTIVE,
    INITIAL_RETARGET_SOURCE_PR,
    INITIAL_RETARGET_TREE,
    PIN_RETARGET_PACKAGE_ID,
    AdvancementProof,
    AdvancementReason,
    TrustedAnchorRecord,
    TrustState,
)
from project_atlas.source_identity import IdentityLockError, ProjectIdentityLock

SHIPPED_ANCHOR_NAME = "autonomy-trusted-anchor-initial.json"
CURRENT_RECORD_NAME = "current.json"
HISTORY_DIR_NAME = "history"
LOCK_NAME = ".anchor.lock"
PLACEHOLDER_DIGEST = "0" * 64
_PIN_RE = re.compile(r"^[0-9a-f]{40}$")
_IDENTITY_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,255}$")


class TrustError(ValueError):
    """Fail-closed trust-anchor error. Not an authority grant."""

    code = "TRUST_UNVERIFIABLE"

    def __init__(self, message: str, *, code: str | None = None) -> None:
        super().__init__(message)
        if code is not None:
            self.code = code


class GitTopology(Protocol):
    """Observed git facts used to verify a proof. Not an authority source."""

    def observe_main(self) -> tuple[str, str]:
        """Return (commit, tree) for the configured main ref."""

    def commit_exists(self, sha: str) -> bool:
        """True only when ``sha`` is a full-name commit object."""

    def tree_of(self, sha: str) -> str:
        """Return the 40-char tree SHA of a commit."""

    def parents_of(self, sha: str) -> tuple[str, ...]:
        """Return parent commit SHAs in git order."""

    def is_descendant(self, child: str, ancestor: str) -> bool:
        """Topology helper. Never sufficient to advance trust."""


@dataclass(frozen=True)
class AdvancementChecks:
    """§10 checklist. All fields must be True before advancement."""

    owner_authorization_proven: bool
    expected_previous_main_match: bool
    authorized_candidate_head_match: bool
    authorized_candidate_tree_match: bool
    merge_parent_1_match: bool
    merge_parent_2_match: bool
    merge_tree_match: bool
    post_merge_seal: bool
    required_post_merge_ci: bool
    evidence_integrity: bool

    @property
    def all_required(self) -> bool:
        return all(
            (
                self.owner_authorization_proven,
                self.expected_previous_main_match,
                self.authorized_candidate_head_match,
                self.authorized_candidate_tree_match,
                self.merge_parent_1_match,
                self.merge_parent_2_match,
                self.merge_tree_match,
                self.post_merge_seal,
                self.required_post_merge_ci,
                self.evidence_integrity,
            )
        )


def require_full_pin(value: str, label: str) -> str:
    if not _PIN_RE.fullmatch(value):
        raise TrustError(f"{label} is not a 40-char lowercase git SHA", code="PIN_INVALID")
    return value


def normalize_repository_identity(remote_url: str) -> str:
    """Normalize a git remote to ``host/owner/name`` without a scheme."""
    raw = remote_url.strip()
    if not raw:
        raise TrustError("repository identity is empty", code="REPO_IDENTITY_UNVERIFIABLE")
    if raw.startswith("git@"):
        _, remainder = raw.split("@", 1)
        raw = remainder.replace(":", "/", 1)
    for prefix in ("https://", "http://", "ssh://", "git://"):
        if raw.lower().startswith(prefix):
            raw = raw[len(prefix) :]
    raw = raw.removesuffix(".git").strip("/")
    if ".." in raw.split("/") or "\\" in raw or ":" in raw:
        raise TrustError("repository identity is unsafe", code="REPO_IDENTITY_UNVERIFIABLE")
    identity = raw.lower()
    if not _IDENTITY_RE.fullmatch(identity):
        raise TrustError("repository identity is malformed", code="REPO_IDENTITY_UNVERIFIABLE")
    return identity


def seal_anchor(record: TrustedAnchorRecord) -> TrustedAnchorRecord:
    digest = hash_payload(record.unsigned_payload())
    return record.model_copy(update={"record_digest": digest})


def verify_anchor_integrity(record: TrustedAnchorRecord) -> TrustedAnchorRecord:
    expected = hash_payload(record.unsigned_payload())
    if record.record_digest != expected:
        raise TrustError("trusted-anchor record digest mismatch", code="HASH_INVALID")
    return record


def build_initial_retarget_record() -> TrustedAnchorRecord:
    """Materialize the owner-specified #398 retarget. Does not read origin/main."""
    unsigned = TrustedAnchorRecord(
        repository_identity=CANONICAL_REPOSITORY_IDENTITY,
        trusted_main=INITIAL_RETARGET_MAIN,
        trusted_tree=INITIAL_RETARGET_TREE,
        predecessor_main=BOOTSTRAP_MAIN,
        predecessor_tree=BOOTSTRAP_TREE,
        advancement_reason=AdvancementReason.VERIFIED_OWNER_AUTHORIZED_MERGE,
        source_package=PIN_RETARGET_PACKAGE_ID,
        source_directive=INITIAL_RETARGET_SOURCE_DIRECTIVE,
        source_pr=INITIAL_RETARGET_SOURCE_PR,
        merge_commit=INITIAL_RETARGET_MAIN,
        merge_parent_1=BOOTSTRAP_MAIN,
        merge_parent_2=INITIAL_RETARGET_CERTIFIED_HEAD,
        merge_tree=INITIAL_RETARGET_TREE,
        certified_head=INITIAL_RETARGET_CERTIFIED_HEAD,
        certified_tree=INITIAL_RETARGET_TREE,
        certification_status="CERTIFIED",
        independent_verification_status="PASS",
        post_merge_seal="PASS",
        post_merge_ci="PASS",
        evidence_reference="as-orch-autonomy-001-merge-002/FINAL_REPORT.md",
        evidence_digest=INITIAL_RETARGET_EVIDENCE_DIGEST,
        sequence=1,
        record_digest=PLACEHOLDER_DIGEST,
    )
    return seal_anchor(unsigned)


def verify_initial_retarget_record(record: TrustedAnchorRecord) -> TrustedAnchorRecord:
    verify_anchor_integrity(record)
    expected = build_initial_retarget_record()
    if record.model_dump(mode="json") != expected.model_dump(mode="json"):
        raise TrustError(
            "shipped retarget record does not match sealed #398 pins",
            code="SHIPPED_MISMATCH",
        )
    if record.trusted_main == record.certified_head:
        raise TrustError("commit identity collapsed into certified HEAD", code="IDENTITY_COLLAPSE")
    if record.trusted_tree != record.certified_tree:
        raise TrustError("merge tree is not the certified content identity", code="TREE_MISMATCH")
    return record


def load_shipped_initial_anchor() -> TrustedAnchorRecord:
    packaged = resources.files("project_atlas").joinpath("data", SHIPPED_ANCHOR_NAME)
    if not packaged.is_file():
        raise TrustError("shipped trusted-anchor record is missing", code="TRUST_UNVERIFIABLE")
    try:
        payload = json.loads(packaged.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise TrustError(
            "shipped trusted-anchor record is unreadable",
            code="TRUST_UNVERIFIABLE",
        ) from exc
    try:
        record = TrustedAnchorRecord.model_validate(payload)
    except Exception as exc:
        raise TrustError(
            "shipped trusted-anchor record is schema-invalid",
            code="TRUST_UNVERIFIABLE",
        ) from exc
    return verify_initial_retarget_record(record)


def load_runtime_anchor(
    *,
    store: Path | None = None,
    explicit: TrustedAnchorRecord | None = None,
    allow_shipped: bool = False,
    expected_repository_identity: str | None = None,
) -> TrustedAnchorRecord:
    """Load trust. Never initializes from origin/main.

    Precedence: explicit record, then store (no shipped fallback), then shipped
    only when ``allow_shipped`` is True.
    """
    if explicit is not None:
        record = verify_anchor_integrity(explicit)
    elif store is not None:
        record = _load_store_current(store)
    elif allow_shipped:
        record = load_shipped_initial_anchor()
    else:
        raise TrustError(
            "no trust record and no explicit bootstrap authority",
            code="TRUST_UNVERIFIABLE",
        )
    if (
        expected_repository_identity is not None
        and record.repository_identity != expected_repository_identity
    ):
        raise TrustError(
            "trusted-anchor repository identity does not match this repository",
            code="REPO_IDENTITY_MISMATCH",
        )
    return record


def evaluate_target_moved(
    observed_main: str,
    observed_tree: str,
    trusted: TrustedAnchorRecord,
) -> bool:
    require_full_pin(observed_main, "observed_main")
    require_full_pin(observed_tree, "observed_tree")
    return observed_main != trusted.trusted_main or observed_tree != trusted.trusted_tree


def classify_observation(
    observed_main: str,
    observed_tree: str,
    trusted: TrustedAnchorRecord,
    *,
    descendant_of_trusted: bool = False,
) -> TrustState:
    """Classify live observation. Descendant-only is never sufficient authority."""
    del descendant_of_trusted
    if evaluate_target_moved(observed_main, observed_tree, trusted):
        return TrustState.TARGET_MOVED
    return TrustState.TRUSTED


def verify_evidence_integrity(proof: AdvancementProof) -> bool:
    if proof.evidence_payload is None:
        return False
    return hash_payload(proof.evidence_payload) == proof.evidence_digest


def evaluate_advancement(
    current: TrustedAnchorRecord,
    proof: AdvancementProof,
    topology: GitTopology,
    *,
    observed_main: str,
    observed_tree: str,
) -> AdvancementChecks:
    """Evaluate §10. Does not invent owner authorization or mutate state."""
    parents = (
        topology.parents_of(proof.merge_commit)
        if topology.commit_exists(proof.merge_commit)
        else ()
    )
    merge_tree = (
        topology.tree_of(proof.merge_commit) if topology.commit_exists(proof.merge_commit) else ""
    )
    head_exists = topology.commit_exists(proof.authorized_candidate_head)
    head_tree = topology.tree_of(proof.authorized_candidate_head) if head_exists else ""
    parent_1_ok = len(parents) >= 2 and parents[0] == proof.merge_parent_1
    parent_2_ok = len(parents) >= 2 and parents[1] == proof.merge_parent_2
    return AdvancementChecks(
        owner_authorization_proven=proof.owner_authorization == "OWNER_AUTHORIZED",
        expected_previous_main_match=(
            proof.expected_previous_main == current.trusted_main
            and proof.expected_previous_tree == current.trusted_tree
            and proof.merge_parent_1 == current.trusted_main
        ),
        authorized_candidate_head_match=(
            head_exists
            and proof.authorized_candidate_head == proof.merge_parent_2
            and proof.merge_parent_2 in parents
        ),
        authorized_candidate_tree_match=(
            head_exists and head_tree == proof.authorized_candidate_tree
        ),
        merge_parent_1_match=(
            parent_1_ok and proof.merge_parent_1 == current.trusted_main
        ),
        merge_parent_2_match=(
            parent_2_ok and proof.merge_parent_2 == proof.authorized_candidate_head
        ),
        merge_tree_match=(
            bool(merge_tree)
            and merge_tree == proof.merge_tree
            and proof.merge_tree == proof.authorized_candidate_tree
            and observed_tree == proof.merge_tree
            and observed_main == proof.merge_commit
        ),
        post_merge_seal=proof.post_merge_seal == "PASS",
        required_post_merge_ci=proof.post_merge_ci == "PASS",
        evidence_integrity=verify_evidence_integrity(proof),
    )


def _record_from_verified_proof(
    current: TrustedAnchorRecord,
    proof: AdvancementProof,
) -> TrustedAnchorRecord:
    unsigned = TrustedAnchorRecord(
        repository_identity=proof.repository_identity,
        trusted_main=proof.merge_commit,
        trusted_tree=proof.merge_tree,
        predecessor_main=current.trusted_main,
        predecessor_tree=current.trusted_tree,
        advancement_reason=AdvancementReason.VERIFIED_OWNER_AUTHORIZED_MERGE,
        source_package=proof.source_package,
        source_directive=proof.source_directive,
        source_pr=proof.source_pr,
        merge_commit=proof.merge_commit,
        merge_parent_1=proof.merge_parent_1,
        merge_parent_2=proof.merge_parent_2,
        merge_tree=proof.merge_tree,
        certified_head=proof.authorized_candidate_head,
        certified_tree=proof.authorized_candidate_tree,
        certification_status="CERTIFIED",
        independent_verification_status="PASS",
        post_merge_seal="PASS",
        post_merge_ci="PASS",
        evidence_reference=proof.evidence_reference,
        evidence_digest=proof.evidence_digest,
        sequence=current.sequence + 1,
        record_digest=PLACEHOLDER_DIGEST,
    )
    return seal_anchor(unsigned)


def advance_trusted_anchor(
    current: TrustedAnchorRecord,
    proof: AdvancementProof,
    topology: GitTopology,
    *,
    store: Path | None = None,
    expected_repository_identity: str | None = None,
) -> TrustedAnchorRecord:
    """OBSERVE → VERIFY → REOBSERVE → COMPARE → ATOMIC_ADVANCE."""
    if expected_repository_identity is not None:
        if proof.repository_identity != expected_repository_identity:
            raise TrustError("proof repository identity mismatch", code="REPO_IDENTITY_MISMATCH")
        if current.repository_identity != expected_repository_identity:
            raise TrustError("current repository identity mismatch", code="REPO_IDENTITY_MISMATCH")
    if proof.repository_identity != current.repository_identity:
        raise TrustError(
            "cross-repository anchor reuse is forbidden",
            code="REPO_IDENTITY_MISMATCH",
        )
    if proof.expected_previous_main != current.trusted_main:
        raise TrustError("stale or concurrent predecessor", code="PREDECESSOR_MISMATCH")

    observed_main, observed_tree = topology.observe_main()
    require_full_pin(observed_main, "observed_main")
    require_full_pin(observed_tree, "observed_tree")
    if not topology.commit_exists(proof.merge_commit):
        raise TrustError("proof references a nonexistent merge commit", code="GIT_OBJECT_MISSING")
    if not topology.commit_exists(proof.authorized_candidate_head):
        raise TrustError("proof references a nonexistent certified HEAD", code="GIT_OBJECT_MISSING")

    checks = evaluate_advancement(
        current,
        proof,
        topology,
        observed_main=observed_main,
        observed_tree=observed_tree,
    )
    if not checks.all_required:
        raise TrustError("verified advancement proof is incomplete", code="ADVANCEMENT_DENIED")

    re_main, re_tree = topology.observe_main()
    if (re_main, re_tree) != (observed_main, observed_tree):
        raise TrustError(
            "live state changed during verification",
            code="TARGET_MOVED_DURING_VERIFICATION",
        )
    if re_main != proof.merge_commit or re_tree != proof.merge_tree:
        raise TrustError(
            "re-observed main does not match authorized merge",
            code="ADVANCEMENT_DENIED",
        )

    new_record = _record_from_verified_proof(current, proof)
    if new_record.predecessor_main != current.trusted_main:
        raise TrustError("history monotonicity violated", code="PREDECESSOR_MISMATCH")
    if store is None:
        return new_record
    return compare_and_advance(store, current, new_record)


def _inside(root: Path, target: Path) -> bool:
    try:
        target.relative_to(root)
    except ValueError:
        return False
    return True


def _require_store_root(store: Path) -> Path:
    resolved = store.resolve()
    if resolved.parent == resolved or resolved == Path.home().resolve():
        raise TrustError("trust store root is not a safe writable directory", code="PATH_UNSAFE")
    return resolved


def _store_path(store: Path, relative_name: str) -> Path:
    if ".." in Path(relative_name).parts or Path(relative_name).is_absolute():
        raise TrustError("trust store relative path is unsafe", code="PATH_UNSAFE")
    target = (store / relative_name).resolve()
    if not _inside(store, target):
        raise TrustError("trust store path escapes root", code="PATH_UNSAFE")
    return target


def _write_json_atomic(target: Path, payload: dict[str, object]) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(payload, sort_keys=True, indent=2, ensure_ascii=True)
    tmp = target.with_name(f".{target.name}.tmp")
    tmp.write_text(encoded + "\n", encoding="utf-8")
    os.replace(tmp, target)


def initialize_store(store: Path, record: TrustedAnchorRecord) -> TrustedAnchorRecord:
    """Persist an explicit record. Does not read origin/main. No overwrite."""
    verify_anchor_integrity(record)
    root = _require_store_root(store)
    current_path = _store_path(root, CURRENT_RECORD_NAME)
    if current_path.exists():
        existing = _load_store_current(root)
        if existing.record_digest != record.record_digest:
            raise TrustError("existing trust record conflicts; refusing overwrite", code="BLOCKED")
        return existing
    _write_json_atomic(current_path, record.model_dump(mode="json"))
    return record


def _load_store_current(store: Path) -> TrustedAnchorRecord:
    root = _require_store_root(store)
    current_path = _store_path(root, CURRENT_RECORD_NAME)
    if not current_path.is_file():
        raise TrustError("trusted-anchor store record is missing", code="TRUST_UNVERIFIABLE")
    try:
        payload = json.loads(current_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise TrustError(
            "trusted-anchor store record is unreadable",
            code="TRUST_UNVERIFIABLE",
        ) from exc
    if not isinstance(payload, dict):
        raise TrustError("trusted-anchor store record is schema-invalid", code="TRUST_UNVERIFIABLE")
    try:
        record = TrustedAnchorRecord.model_validate(payload)
    except Exception as exc:
        raise TrustError(
            "trusted-anchor store record is schema-invalid",
            code="TRUST_UNVERIFIABLE",
        ) from exc
    return verify_anchor_integrity(record)


def compare_and_advance(
    store: Path,
    expected_current: TrustedAnchorRecord,
    new_record: TrustedAnchorRecord,
) -> TrustedAnchorRecord:
    """Serialized compare-and-advance. Concurrent writers fail closed."""
    verify_anchor_integrity(expected_current)
    verify_anchor_integrity(new_record)
    if new_record.predecessor_main != expected_current.trusted_main:
        raise TrustError(
            "new predecessor_main must equal old trusted_main",
            code="PREDECESSOR_MISMATCH",
        )
    if new_record.sequence != expected_current.sequence + 1:
        raise TrustError("sequence must increase by one", code="DOWNGRADE_FORBIDDEN")
    if new_record.trusted_main == expected_current.predecessor_main:
        raise TrustError("arbitrary rollback is forbidden", code="ROLLBACK_FORBIDDEN")
    root = _require_store_root(store)
    lock_path = _store_path(root, LOCK_NAME)
    try:
        with ProjectIdentityLock(lock_path, wait_seconds=2.0, stale_seconds=30.0):
            current = _load_store_current(root)
            if current.record_digest != expected_current.record_digest:
                raise TrustError(
                    "concurrent or stale compare-and-advance",
                    code="ANCHOR_CAS_MISMATCH",
                )
            history_name = f"{HISTORY_DIR_NAME}/{current.sequence:08d}.json"
            history_path = _store_path(root, history_name)
            if history_path.exists():
                raise TrustError(
                    "refusing to rewrite anchor history",
                    code="TRUST_ANCHOR_HISTORY_REWRITTEN",
                )
            _write_json_atomic(history_path, current.model_dump(mode="json"))
            _write_json_atomic(
                _store_path(root, CURRENT_RECORD_NAME),
                new_record.model_dump(mode="json"),
            )
            return new_record
    except IdentityLockError as exc:
        raise TrustError(
            "anchor lock is held by another writer",
            code="CONCURRENT_ADVANCE",
        ) from exc


def observe_repository_identity(repo: Path, *, git_runner: GitRunner | None = None) -> str:
    runner = git_runner or LiveGitObserver(repo)
    return runner.repository_identity()


class GitRunner(Protocol):
    def repository_identity(self) -> str:
        """Normalized origin identity."""


class LiveGitObserver:
    """Fail-closed live git topology. Abbreviated SHAs are rejected."""

    def __init__(self, repo: Path, *, main_ref: str = "origin/main") -> None:
        # Branch names are never pins. origin/main is an observation ref only.
        if main_ref != "origin/main":
            raise TrustError(
                "main observation ref is not allowed",
                code="BRANCH_NAME_CONFUSION",
            )
        self._repo = repo.resolve()
        self._main_ref = main_ref
        if not (self._repo / ".git").exists():
            raise TrustError("root is not a git repository", code="GIT_UNOBSERVABLE")

    def _run(self, *args: str) -> str:
        result = subprocess.run(
            ["git", *args],
            cwd=self._repo,
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise TrustError(f"git {' '.join(args)} failed", code="GIT_UNOBSERVABLE")
        return result.stdout.strip()

    def observe_main(self) -> tuple[str, str]:
        commit = require_full_pin(self._run("rev-parse", self._main_ref), "observed_main")
        tree = require_full_pin(
            self._run("rev-parse", f"{self._main_ref}^{{tree}}"),
            "observed_tree",
        )
        return commit, tree

    def commit_exists(self, sha: str) -> bool:
        if not _PIN_RE.fullmatch(sha):
            return False
        result = subprocess.run(
            ["git", "cat-file", "-t", sha],
            cwd=self._repo,
            check=False,
            capture_output=True,
            text=True,
        )
        return result.returncode == 0 and result.stdout.strip() == "commit"

    def tree_of(self, sha: str) -> str:
        require_full_pin(sha, "tree_of")
        return require_full_pin(self._run("rev-parse", f"{sha}^{{tree}}"), "tree")

    def parents_of(self, sha: str) -> tuple[str, ...]:
        require_full_pin(sha, "parents_of")
        raw = self._run("rev-list", "--parents", "-n", "1", sha)
        parts = raw.split()
        parents = tuple(require_full_pin(item, "parent") for item in parts[1:])
        return parents

    def is_descendant(self, child: str, ancestor: str) -> bool:
        require_full_pin(child, "child")
        require_full_pin(ancestor, "ancestor")
        result = subprocess.run(
            ["git", "merge-base", "--is-ancestor", ancestor, child],
            cwd=self._repo,
            check=False,
            capture_output=True,
            text=True,
        )
        return result.returncode == 0

    def repository_identity(self) -> str:
        return normalize_repository_identity(self._run("remote", "get-url", "origin"))


class FixtureGitObserver:
    """Disposable topology for tests. Not a live repository and not authority."""

    def __init__(
        self,
        *,
        observed_main: str,
        observed_tree: str,
        objects: dict[str, tuple[str, tuple[str, ...]]],
        identity: str = CANONICAL_REPOSITORY_IDENTITY,
        observe_sequence: tuple[tuple[str, str], ...] | None = None,
    ) -> None:
        self.observed_main = require_full_pin(observed_main, "observed_main")
        self.observed_tree = require_full_pin(observed_tree, "observed_tree")
        self._objects = objects
        self._identity = identity
        self._observe_sequence = list(observe_sequence or ())
        self._observe_calls = 0

    def observe_main(self) -> tuple[str, str]:
        if self._observe_sequence:
            index = min(self._observe_calls, len(self._observe_sequence) - 1)
            self._observe_calls += 1
            return self._observe_sequence[index]
        self._observe_calls += 1
        return self.observed_main, self.observed_tree

    def commit_exists(self, sha: str) -> bool:
        return _PIN_RE.fullmatch(sha) is not None and sha in self._objects

    def tree_of(self, sha: str) -> str:
        if sha not in self._objects:
            raise TrustError("fixture git object missing", code="GIT_OBJECT_MISSING")
        return self._objects[sha][0]

    def parents_of(self, sha: str) -> tuple[str, ...]:
        if sha not in self._objects:
            raise TrustError("fixture git object missing", code="GIT_OBJECT_MISSING")
        return self._objects[sha][1]

    def is_descendant(self, child: str, ancestor: str) -> bool:
        if child == ancestor:
            return True
        if child not in self._objects:
            return False
        for parent in self._objects[child][1]:
            if parent == ancestor or self.is_descendant(parent, ancestor):
                return True
        return False

    def repository_identity(self) -> str:
        return self._identity
