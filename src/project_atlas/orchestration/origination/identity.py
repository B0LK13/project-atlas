"""Stable, deterministic origination identity. No wall-clock component.

``origination_identity()`` is a pure function of durable inputs (project
id, the authoritative fact's location, and the exact byte content already
consulted). Same inputs -> same identity, forever, across process
restarts and re-scans -- this is what makes ``NO_DUPLICATE_ORIGINATION``
and ``PROVENANCE_SURVIVES_RESTART`` structural rather than conventional.
If the underlying evidence file's content changes, ``content_digest``
changes, so the identity changes too: a genuinely new identity, not a
silently-reused stale one.
"""

from __future__ import annotations

import hashlib

from project_atlas.orchestration.origination.facts import SourceFact


def origination_identity(project_id: str, authoritative_source: SourceFact) -> str:
    """sha256(project_id :: authoritative evidence location :: its content digest), hex."""
    loc = authoritative_source.location
    digest = authoritative_source.content_digest
    payload = f"{project_id}::{loc}::{digest}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def work_id_for(origination_id: str) -> str:
    """A ``WorkNode.package_id``-safe id derived from the origination identity.

    ``atlas_contracts.versions.ID_PATTERN`` requires an alphanumeric-first,
    ``[A-Za-z0-9._-]*`` string; a raw hex digest already satisfies that, but
    a short, prefixed form keeps ids readable in logs/receipts while
    remaining fully derived (no counter, no wall-clock).
    """
    return f"ORIG-{origination_id[:16]}"
