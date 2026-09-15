"""AS-CORE-002 semantic model and security coverage."""

import pytest
from pydantic import ValidationError

from project_atlas.domain import CoverageRecord, ProjectRecord, SourceLifecycleRecord
from project_atlas.secrets import scan_text


def test_project_record_is_versioned_and_strict() -> None:
    record = ProjectRecord(project_id="demo", name="Demo")
    assert record.schema_version == 1
    assert record.generated is True
    with pytest.raises(ValidationError):
        ProjectRecord(project_id="demo", name="Demo", unexpected=True)


def test_source_lifecycle_and_coverage_are_explicit() -> None:
    source = SourceLifecycleRecord(source_id="source-a", path="README.md")
    coverage = CoverageRecord(category="overview", state="absent")
    assert source.lifecycle.value == "verified"
    assert coverage.state == "absent"


def test_secret_scanner_returns_redacted_metadata_only() -> None:
    findings = scan_text("password = 'not-a-real-secret-value'\n")
    assert findings
    assert findings[0].pattern == "password-assignment"
    assert "not-a-real" not in findings[0].redacted_hint
