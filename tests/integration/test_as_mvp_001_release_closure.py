"""AS-MVP-001 release-closure remediation tests.

Covers, over and above the ten ADR-005 acceptance scenarios in
``test_as_mvp_001_portfolio.py``:

- K-004: expected (golden) discovery manifest for the three pilots.
- K-005: expected (golden) generated portfolio outputs for the three
  pilots, both for semantic correctness and settled-rebuild byte
  identity.
- K-006: an explicit, itemized proof of every contradiction-handling
  property, reusing the existing dark-factory pilot and the certified
  conflict pipeline (ADR-005's own design: "Contradiction fixtures
  (K-006) ... reuse the dark-factory project for conflicts").
- K-007: a dedicated, minimal fixture project
  (tests/fixtures/k007-canary-secrets/) carrying one safe,
  credential-shaped canary string, proving zero leakage into every
  portfolio output and CLI stdout/stderr (ADR-005's own design: "add
  one credential-shaped string to a fourth, minimal fixture project").
- The overview.json "coverage_categories_present" vs. maturity-matrix
  "required_coverage_present" field-semantics reconciliation.
- A multi-batch discover/ingest regression for AS-INGEST-MANIFEST-001:
  narrower second-batch ingest retains sibling-project discovery
  snapshot rows, classifications, coverage, and stale-knowledge inputs
  (closing the AS-MVP-001 accepted overwrite limitation).

Golden fixtures under tests/fixtures/expected/ were generated once by
running the real pipeline against tests/fixtures/pilots/ with every
fixture file's mtime pinned to a fixed, non-wall-clock epoch (so
`stale-knowledge.json`'s freshness labels are reproducible), then
reviewed and committed; they are not computed by the test itself
calling the same production code under test.
"""

from __future__ import annotations

import io
import json
import os
import shutil
from contextlib import redirect_stderr, redirect_stdout
from datetime import UTC, datetime
from pathlib import Path

import pytest

from project_atlas.cli import EXIT_OK, main
from project_atlas.portfolio import build_portfolio

pytestmark = pytest.mark.integration
PILOTS = Path("tests/fixtures/pilots")
EXPECTED = Path("tests/fixtures/expected")
K007_FIXTURE = Path("tests/fixtures/k007-canary-secrets")

# Fixed, non-wall-clock epochs (seconds since the Unix epoch), never
# read from the real filesystem clock: 2026-07-01T00:00:00Z is "fresh"
# relative to the 2026-08-01 reference date used below; 2024-01-01T00:00:00Z
# is well past the 180-day default staleness threshold.
_FRESH_MTIME = 1782864000
_STALE_MTIME = 1704067200
_REFERENCE_DATE = datetime(2026, 8, 1, tzinfo=UTC)

# Fixed, pre-declared per-pilot project UUIDs (arbitrary but valid UUIDv4
# constants, generated once and frozen here -- never regenerated at test
# time). The committed pilot fixtures deliberately do not declare a
# project_uuid of their own (so real, uncopied `atlas discover`/`ingest`
# runs against them do not durably mutate the committed
# .atlas-project.yaml marker files -- see
# test_multi_batch_ingest_manifest_merge_retains_sibling_projects'
# docstring). ingestion.py's `_prepare_project_identity()` allocates a
# fresh, genuinely random UUID exactly once for any project marker with
# no `project_uuid` field (AS-ID-001's "genesis" design), which would
# make every K-004/K-005 golden comparison here non-reproducible. Pre-
# declaring a fixed UUID in this test's *scratch copy only* mimics an
# already-settled identity and makes the whole downstream pipeline
# (including source_lineage_id, which hashes project_uuid) deterministic.
_FIXED_PROJECT_UUIDS = {
    "nebula": "dde3eba3-3655-45da-b3aa-45c5cddcc28e",
    "black-agency-os": "d7d87859-33bb-4184-bd31-b21a5eca4ba6",
    "dark-factory": "9dd2dfe1-a757-4a58-962b-02c900c31891",
}


def _frozen_pilots(tmp_path: Path) -> Path:
    """Copy the pilot corpus with every file's mtime pinned to a fixed
    epoch (not derived from ``time.time()``) and a fixed, pre-declared
    ``project_uuid`` written into each copied marker, so discovery's
    ``modified_at`` field and ingestion's identity/lineage derivations
    are byte-reproducible across machines and invocations -- required
    for the K-004/K-005 golden comparisons."""
    root = tmp_path / "pilots"
    shutil.copytree(PILOTS, root)
    for project, project_uuid in _FIXED_PROJECT_UUIDS.items():
        marker = root / project / ".atlas-project.yaml"
        text = marker.read_text(encoding="utf-8")
        assert "project_uuid" not in text, f"{marker} already declares a project_uuid"
        # newline="\n" pins LF bytes on every platform; the default text-mode
        # translation writes CRLF on Windows and changed size_bytes there.
        marker.write_text(
            text + f"project_uuid: {project_uuid}\n", encoding="utf-8", newline="\n"
        )
    for path in root.rglob("*"):
        if path.is_file():
            os.utime(path, (_FRESH_MTIME, _FRESH_MTIME))
    os.utime(root / "black-agency-os" / "README.md", (_STALE_MTIME, _STALE_MTIME))
    return root


def _run_pipeline(source: Path, tmp_path: Path, *, reference_date: datetime) -> Path:
    manifest = tmp_path / "manifest.json"
    vault = tmp_path / "vault"
    assert main(["init", "--output", str(vault)]) == EXIT_OK
    assert main(["discover", "--source", str(source), "--output", str(manifest)]) == EXIT_OK
    assert main(
        [
            "ingest",
            "--manifest",
            str(manifest),
            "--vault",
            str(vault),
            "--source",
            str(source),
        ]
    ) == EXIT_OK
    assert main(["build-indexes", "--vault", str(vault)]) == EXIT_OK
    build_portfolio(vault, reference_date=reference_date)
    assert main(["validate", "--vault", str(vault)]) == EXIT_OK
    return vault


# ---------------------------------------------------------------------------
# K-004: expected manifest fixture
# ---------------------------------------------------------------------------


def test_k004_discovery_manifest_matches_golden_fixture(tmp_path: Path) -> None:
    pilots = _frozen_pilots(tmp_path)
    manifest_path = tmp_path / "manifest.json"
    assert main(["discover", "--source", str(pilots), "--output", str(manifest_path)]) == EXIT_OK

    actual = json.loads(manifest_path.read_text(encoding="utf-8"))
    # Excluded, not compared: "source_root" is the absolute scratch-directory
    # path (machine/run-specific by construction); "inventory_sha256" is a
    # hash *of* source_root (discovery.py), so it is equally run-specific.
    # Every other field -- source identities, paths, classification state,
    # project_uuid, sha256, size_bytes, modified_at (pinned above) -- is
    # fully deterministic and is compared exactly.
    actual.pop("source_root", None)
    actual.pop("inventory_sha256", None)

    expected = json.loads(
        (EXPECTED / "manifests" / "pilots-manifest.json").read_text(encoding="utf-8")
    )
    assert actual == expected


# ---------------------------------------------------------------------------
# K-005: expected (golden) portfolio outputs
# ---------------------------------------------------------------------------


def test_k005_portfolio_outputs_match_golden_fixtures(tmp_path: Path) -> None:
    pilots = _frozen_pilots(tmp_path)
    vault = _run_pipeline(pilots, tmp_path, reference_date=_REFERENCE_DATE)

    for name in (
        "overview.json",
        "maturity-matrix.json",
        "documentation-coverage.json",
        "stale-knowledge.json",
        "dependency-report.json",
        "capability-report.json",
    ):
        actual = (vault / "generated" / "portfolio" / name).read_text(encoding="utf-8")
        expected = (EXPECTED / "portfolio" / name).read_text(encoding="utf-8")
        assert actual == expected, f"{name} does not match golden fixture"

    actual_nav = (vault / "generated" / "navigation" / "portfolio-overview.md").read_text(
        encoding="utf-8"
    )
    expected_nav = (EXPECTED / "portfolio" / "portfolio-overview.md").read_text(encoding="utf-8")
    assert actual_nav == expected_nav


def test_k005_settled_rebuild_is_byte_identical_to_golden_state(tmp_path: Path) -> None:
    """Golden-fixture comparison supplements, but does not replace, the
    existing behavioral settled-rebuild assertion (test_scenario_8)."""
    pilots = _frozen_pilots(tmp_path)
    vault = _run_pipeline(pilots, tmp_path, reference_date=_REFERENCE_DATE)
    first = {
        p.name: p.read_bytes() for p in sorted((vault / "generated" / "portfolio").glob("*.json"))
    }
    build_portfolio(vault, reference_date=_REFERENCE_DATE)
    second = {
        p.name: p.read_bytes() for p in sorted((vault / "generated" / "portfolio").glob("*.json"))
    }
    assert first == second
    for name, content in first.items():
        expected = (EXPECTED / "portfolio" / name).read_bytes()
        assert content == expected


# ---------------------------------------------------------------------------
# K-006: dedicated contradiction-handling checklist (dark-factory, per
# ADR-005's own explicit design)
# ---------------------------------------------------------------------------


def test_k006_contradiction_handling_full_checklist(tmp_path: Path) -> None:
    pilots = _frozen_pilots(tmp_path)
    vault = _run_pipeline(pilots, tmp_path, reference_date=_REFERENCE_DATE)

    # (1) Two source records express incompatible project facts, and (2)
    # the existing certified conflict pipeline identifies the contradiction.
    conflict_path = vault / "review" / "conflicts" / "dark-factory.json"
    before = json.loads(conflict_path.read_text(encoding="utf-8"))
    entries = before["entries"]
    assert len(entries) == 1
    assert entries[0]["field"] == "roadmap"
    conflict_id = entries[0]["conflict_id"]

    # (3) Stable conflict identity, and (4) the conflict appears in the
    # approved review output (generated/indexes/conflicts.json).
    conflicts_index = json.loads(
        (vault / "generated" / "indexes" / "conflicts.json").read_text(encoding="utf-8")
    )
    assert conflict_id in conflicts_index["ids"]

    # (5) Unrelated projects remain unaffected: nebula and black-agency-os
    # each get their own review/conflicts/ file (knowledge_compiler.py
    # writes one per project unconditionally) with zero entries.
    for other in ("nebula", "black-agency-os"):
        other_conflicts = json.loads(
            (vault / "review" / "conflicts" / f"{other}.json").read_text(encoding="utf-8")
        )
        assert other_conflicts["entries"] == []
    overview_by_project = {
        entry["project_id"]: entry
        for entry in json.loads(
            (vault / "generated" / "portfolio" / "overview.json").read_text(encoding="utf-8")
        )["projects"]
    }
    assert overview_by_project["nebula"]["open_conflicts"] == 0
    assert overview_by_project["black-agency-os"]["open_conflicts"] == 0
    assert overview_by_project["dark-factory"]["open_conflicts"] == 1

    # (6) No conflict resolution state is mutated by portfolio generation:
    # rerun build-portfolio and confirm review/conflicts/dark-factory.json
    # is untouched, and (7) deterministic rebuild preserves the same
    # conflict reference.
    conflict_before_bytes = conflict_path.read_bytes()
    build_portfolio(vault, reference_date=_REFERENCE_DATE)
    assert conflict_path.read_bytes() == conflict_before_bytes
    after = json.loads(conflict_path.read_text(encoding="utf-8"))
    assert after["entries"][0]["conflict_id"] == conflict_id


# ---------------------------------------------------------------------------
# K-007: dedicated secret/adversarial fixture (fourth, minimal project,
# per ADR-005's own explicit design), including CLI stdout/stderr
# ---------------------------------------------------------------------------


def test_k007_dedicated_secret_fixture_never_leaks(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.json"
    vault = tmp_path / "vault"

    stdout = io.StringIO()
    stderr = io.StringIO()
    with redirect_stdout(stdout), redirect_stderr(stderr):
        assert main(["init", "--output", str(vault)]) == EXIT_OK
        assert (
            main(["discover", "--source", str(K007_FIXTURE), "--output", str(manifest)])
            == EXIT_OK
        )
        assert (
            main(
                [
                    "ingest",
                    "--manifest",
                    str(manifest),
                    "--vault",
                    str(vault),
                    "--source",
                    str(K007_FIXTURE),
                ]
            )
            == EXIT_OK
        )
        assert main(["build-indexes", "--vault", str(vault)]) == EXIT_OK
        build_portfolio(vault, reference_date=_REFERENCE_DATE)
        assert main(["validate", "--vault", str(vault)]) == EXIT_OK

    findings = json.loads(
        (vault / "generated" / "reports" / "secret-findings.json").read_text(encoding="utf-8")
    )
    assert findings, "canary fixture must produce at least one secret-scan finding"
    quarantined_source_ids = {finding["source_id"] for finding in findings}

    canary = "AKIAFAKEFAKEFAKEFAKE"
    surfaces: dict[str, str] = {
        "cli-stdout": stdout.getvalue(),
        "cli-stderr": stderr.getvalue(),
    }
    for path in sorted((vault / "generated" / "portfolio").glob("*.json")):
        surfaces[f"portfolio/{path.name}"] = path.read_text(encoding="utf-8")
    nav = vault / "generated" / "navigation" / "portfolio-overview.md"
    if nav.is_file():
        surfaces["portfolio-overview.md"] = nav.read_text(encoding="utf-8")

    for label, text in surfaces.items():
        assert canary not in text, f"canary secret leaked in {label}"
        for source_id in quarantined_source_ids:
            assert source_id not in text, f"quarantined source_id leaked in {label}"

    # The quarantined source is still safely, non-specifically counted.
    overview = json.loads(
        (vault / "generated" / "portfolio" / "overview.json").read_text(encoding="utf-8")
    )
    assert overview["projects"][0]["quarantined_sources"] == 1


# ---------------------------------------------------------------------------
# Overview aggregation semantics: "present" vs. "present or partial"
# ---------------------------------------------------------------------------


def test_overview_coverage_categories_present_counts_strictly_present_only(
    tmp_path: Path,
) -> None:
    """overview.json's "coverage_categories_present" and
    maturity-matrix.json's "required_coverage_present" are deliberately
    different fields answering different questions, not one field
    inconsistently computed:

    - overview.json reports a literal count of categories in the
      "present" CoverageRecord.state (semantic_compiler.py's own
      absent/partial/present/stale/conflicting vocabulary), matching
      the field's name exactly -- ADR-005 draws no equivalence between
      "coverage_categories_present" and any partial-inclusive count.
    - maturity-matrix.json's "required_coverage_present" is a narrower,
      boolean maturity *input* answering "does this project have at
      least some evidence (present or partial) for every one of the
      three required categories" -- a deliberately lower bar suited to
      a categorical maturity signal, not a coverage tally.

    This test pins that reconciliation down with a project (nebula) whose
    "architecture" and "security" categories are "partial" (not
    "present"), so the two fields provably diverge by design rather than
    by accident.
    """
    pilots = _frozen_pilots(tmp_path)
    vault = _run_pipeline(pilots, tmp_path, reference_date=_REFERENCE_DATE)

    coverage = json.loads(
        (vault / "generated" / "portfolio" / "documentation-coverage.json").read_text(
            encoding="utf-8"
        )
    )["projects"]["nebula"]["categories"]
    by_category = {item["category"]: item["state"] for item in coverage}
    assert by_category["architecture"] == "partial"
    assert by_category["security"] == "partial"
    assert by_category["overview"] == "present"

    overview = {
        entry["project_id"]: entry
        for entry in json.loads(
            (vault / "generated" / "portfolio" / "overview.json").read_text(encoding="utf-8")
        )["projects"]
    }["nebula"]
    # coverage_categories_present counts "present" only -- "architecture"
    # and "security" being "partial" does not increment it, even though
    # they are the two required categories (besides "overview") that
    # maturity_inputs["required_coverage_present"] treats as satisfied.
    strictly_present = sum(1 for item in coverage if item["state"] == "present")
    assert overview["coverage_categories_present"] == strictly_present
    assert strictly_present == 2  # "overview" and "testing" only

    maturity_inputs = json.loads(
        (vault / "generated" / "portfolio" / "maturity-matrix.json").read_text(encoding="utf-8")
    )["projects"]["nebula"]["inputs"]
    # required_coverage_present is a separate boolean over the fixed
    # three-category subset (overview/architecture/security) accepting
    # "present" or "partial"; all three are satisfied (present, partial,
    # partial) even though only one of them contributes to
    # coverage_categories_present -- proving the two fields are
    # independently, deliberately scoped rather than aliases of each
    # other, per this test's module docstring.
    assert maturity_inputs["required_coverage_present"] is True


# ---------------------------------------------------------------------------
# Multi-batch discover/ingest: AS-INGEST-MANIFEST-001 snapshot merge
# ---------------------------------------------------------------------------


def test_multi_batch_ingest_manifest_merge_retains_sibling_projects(
    tmp_path: Path,
) -> None:
    """AS-INGEST-MANIFEST-001: narrower second-batch ingest retains sibling
    projects' discovery snapshot rows, classifications, coverage signals,
    and stale-knowledge inventory.

    Closes the AS-MVP-001 accepted overwrite limitation for
    ``sources/manifests/source-manifest.json`` and batch reports.
    """
    # Never discover directly from the committed tests/fixtures/pilots/
    # tree: a first-ever ingest durably allocates and writes a one-time
    # project_uuid *back into the scanned source's own .atlas-project.yaml*
    # (ingestion.py's project-identity-allocation / AS-ID-001 "genesis"
    # design -- by design, not a defect; see _prepare_project_identity()).
    # Every other test in this suite copies the pilots first for the same
    # reason (_copy_pilots()); this test does the same via shutil.copytree.
    pilots = tmp_path / "pilots-copy"
    shutil.copytree(PILOTS, pilots)

    vault = tmp_path / "vault"
    assert main(["init", "--output", str(vault)]) == EXIT_OK

    manifest_1 = tmp_path / "m1.json"
    assert main(["discover", "--source", str(pilots), "--output", str(manifest_1)]) == EXIT_OK
    assert (
        main(
            [
                "ingest",
                "--manifest",
                str(manifest_1),
                "--vault",
                str(vault),
                "--source",
                str(pilots),
            ]
        )
        == EXIT_OK
    )
    combined_manifest = json.loads(
        (vault / "sources" / "manifests" / "source-manifest.json").read_text(encoding="utf-8")
    )
    assert {s["likely_project"] for s in combined_manifest["sources"]} == {
        "nebula",
        "black-agency-os",
        "dark-factory",
    }
    combined_report = json.loads(
        (vault / "generated" / "reports" / "ingestion-report.json").read_text(encoding="utf-8")
    )
    sibling_classification_ids = {
        source_id
        for source_id, _info in combined_report["classifications"].items()
        if any(
            entry["source_id"] == source_id
            and entry["likely_project"] in {"black-agency-os", "dark-factory"}
            for entry in combined_manifest["sources"]
        )
    }
    assert sibling_classification_ids

    assert main(["build-indexes", "--vault", str(vault)]) == EXIT_OK
    assert main(["build-portfolio", "--vault", str(vault)]) == EXIT_OK
    coverage_before = json.loads(
        (vault / "generated" / "portfolio" / "documentation-coverage.json").read_text(
            encoding="utf-8"
        )
    )
    stale_before = json.loads(
        (vault / "generated" / "portfolio" / "stale-knowledge.json").read_text(encoding="utf-8")
    )

    def _presentish_counts(coverage: dict[str, object], project_id: str) -> int:
        project = coverage["projects"][project_id]  # type: ignore[index]
        categories = project["categories"]  # type: ignore[index]
        return sum(
            1
            for category in categories  # type: ignore[union-attr]
            if category["state"] in {"present", "partial"}
        )

    sibling_presentish_before = {
        project_id: _presentish_counts(coverage_before, project_id)
        for project_id in ("black-agency-os", "dark-factory")
    }
    assert all(count > 0 for count in sibling_presentish_before.values())
    sibling_stale_before = {
        project_id: list(
            stale_before["projects"].get(project_id, {}).get("sources", [])  # type: ignore[index]
        )
        for project_id in ("black-agency-os", "dark-factory")
    }

    manifest_2 = tmp_path / "m2.json"
    assert (
        main(["discover", "--source", str(pilots / "nebula"), "--output", str(manifest_2)])
        == EXIT_OK
    )
    assert (
        main(
            [
                "ingest",
                "--manifest",
                str(manifest_2),
                "--vault",
                str(vault),
                "--source",
                str(pilots / "nebula"),
            ]
        )
        == EXIT_OK
    )

    merged_manifest = json.loads(
        (vault / "sources" / "manifests" / "source-manifest.json").read_text(encoding="utf-8")
    )
    merged_projects = {s["likely_project"] for s in merged_manifest["sources"]}
    assert merged_projects == {"nebula", "black-agency-os", "dark-factory"}
    merged_report = json.loads(
        (vault / "generated" / "reports" / "ingestion-report.json").read_text(encoding="utf-8")
    )
    assert sibling_classification_ids <= set(merged_report["classifications"])

    assert main(["build-indexes", "--vault", str(vault)]) == EXIT_OK
    assert main(["build-portfolio", "--vault", str(vault)]) == EXIT_OK

    overview_by_project = {
        entry["project_id"]: entry
        for entry in json.loads(
            (vault / "generated" / "portfolio" / "overview.json").read_text(encoding="utf-8")
        )["projects"]
    }
    assert set(overview_by_project) == {"nebula", "black-agency-os", "dark-factory"}
    assert overview_by_project["black-agency-os"]["quarantined_sources"] == 0
    assert overview_by_project["dark-factory"]["quarantined_sources"] == 0
    assert overview_by_project["nebula"]["quarantined_sources"] == 0

    coverage_after = json.loads(
        (vault / "generated" / "portfolio" / "documentation-coverage.json").read_text(
            encoding="utf-8"
        )
    )
    for project_id, before_count in sibling_presentish_before.items():
        assert _presentish_counts(coverage_after, project_id) == before_count

    stale_after = json.loads(
        (vault / "generated" / "portfolio" / "stale-knowledge.json").read_text(encoding="utf-8")
    )
    for project_id, before_entries in sibling_stale_before.items():
        after_entries = stale_after["projects"].get(project_id, {}).get("sources", [])
        assert {entry["source_id"] for entry in before_entries} <= {
            entry["source_id"] for entry in after_entries
        }
