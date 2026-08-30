"""Stable, deterministic origination identity. No wall-clock component.

``origination_identity()`` is a pure function of the project id plus one
explicit structured roadmap subject (item id + canonical item digest).
Sibling roadmap edits therefore cannot rename unchanged work, while a
material edit to that item's own record creates a new revision identity.
"""

from __future__ import annotations

import hashlib

from project_atlas.orchestration.origination.facts import SourceFact


def origination_identity(project_id: str, authoritative_source: SourceFact) -> str:
    """Return a stable per-item, per-revision origination identity."""
    loc = authoritative_source.location
    item_id = authoritative_source.subject_id
    item_digest = authoritative_source.subject_digest
    if item_id is None or item_digest is None:
        raise ValueError("authoritative source is missing its structured roadmap subject")
    payload = f"{project_id}::{loc}::{item_id}::{item_digest}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def work_id_for(project_id: str, item_id: str) -> str:
    """A stable ``WorkNode.package_id`` for one logical roadmap item.

    ``atlas_contracts.versions.ID_PATTERN`` requires an alphanumeric-first,
    ``[A-Za-z0-9._-]*`` string. Hashing the explicit project/item pair makes
    dependency edges resolvable before either node is materialized, and keeps
    the package id stable when the item's own specification is revised.
    """
    payload = f"{project_id}::{item_id}"
    return f"ORIG-{hashlib.sha256(payload.encode('utf-8')).hexdigest()[:16]}"
