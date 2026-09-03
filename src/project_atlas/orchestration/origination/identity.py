"""Stable, deterministic origination identity. No wall-clock component.

``origination_identity()`` is a pure function of the project id, one
explicit structured roadmap subject (item id + canonical item digest),
AND the complete authority-bearing interpretation this pipeline derives
for it (``proposed_scope`` / ``success_criteria`` -- see
``pipeline.py::effective_authority_fields()``). Sibling roadmap edits
therefore cannot rename unchanged work, while a material edit to that
item's own record -- OR to the acceptance contract that governs what it
may do -- creates a new revision identity.

Owner directive D-ATLAS-AUTHORITY-SNAPSHOT-CONVERGENCE (P1 finding,
PR #678, chatgpt-codex-connector): before this, the identity hashed only
the raw roadmap subject (``item_digest``), not ``proposed_scope`` /
``success_criteria`` -- the two fields an attached acceptance contract
(``acceptance_contracts.py``) can override independently of the roadmap
item's own bytes (``pipeline.py::_build_outcome()``). Because
``origination_identity`` is this pipeline's actual store primary key
(``projection.py``'s ``persist_proposed()`` / ``reconcile_revision()``
both key their "is this a known/current revision?" lookup on it, and
``pipeline.py::originate_new_only()`` keys its TERMINAL-exclusion filter
on it too), a contract-only edit left the identity unchanged: a stalled
scan -- or a fresh one, for that matter -- reusing the OLD, now-obsolete
scope/criteria on the SAME ``origination_identity`` looked exactly like
"nothing changed, this row is already current" and never reached the
``still_current`` freshness check at all (that check only runs on the
"this looks like a new revision" path). Folding ``proposed_scope`` /
``success_criteria`` into the identity itself closes the gap at its
actual root: those two fields ARE this pipeline's entire authority-bearing
surface downstream of the roadmap item (``risk.classify()`` and
``materialize_work_node()`` consume nothing else from an
``EligibleRoadmapItem`` beyond what ``item_digest`` already covers, plus
these two), so hashing them alongside the existing parts makes
``origination_identity`` correctly represent "the exact authority-bearing
interpretation this revision was derived from" without introducing a
second, parallel identity concept that the existing supersession/
freshness machinery would need to be separately taught to consult.

Migration note: this widens what the hash covers, so upgrading changes
the identity value computed for every item that has ever had a contract
attached (items with no contract are unaffected in practice, since their
scope/criteria are themselves a deterministic function of already-hashed
evidence paths -- same inputs, same output). Any existing durably
PROPOSED/MATERIALIZED row survives as history under its old identity; the
next scan computes a new identity for the same logical work, supersedes
the old row (never deletes it -- see ``reconcile_revision()``), and
materializes fresh. That one-time supersede-and-rematerialize on upgrade
is this system's own designed self-healing transition, not a special
case -- exactly what a legitimate revision-identity change is supposed to
produce.
"""

from __future__ import annotations

import hashlib
import json

from project_atlas.orchestration.origination.facts import SourceFact


def origination_identity_from_parts(
    project_id: str,
    location: str,
    item_id: str,
    item_digest: str,
    proposed_scope: tuple[str, ...],
    success_criteria: tuple[str, ...],
) -> str:
    """The one identity formula, spelled out over its raw parts.

    Split out of ``origination_identity()`` (IV finding F2 on PR #677)
    so a scan can cheaply re-derive "is this identity still what current
    source truth yields for this item?" from a fresh
    ``eligible_work_items()`` read (via
    ``pipeline.py::effective_authority_fields()``), without constructing
    a full ``SourceFact`` -- and without a second, drift-prone copy of
    the payload format.

    ``proposed_scope`` / ``success_criteria`` are hashed as an ordered
    JSON array, not string-joined, so no boundary-shifting combination of
    entries (e.g. ``["a::b"]`` vs. ``["a", "b"]``) can collide.
    """
    payload = json.dumps(
        {
            "project_id": project_id,
            "location": location,
            "item_id": item_id,
            "item_digest": item_digest,
            "proposed_scope": list(proposed_scope),
            "success_criteria": list(success_criteria),
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def origination_identity(
    project_id: str,
    authoritative_source: SourceFact,
    *,
    proposed_scope: tuple[str, ...],
    success_criteria: tuple[str, ...],
) -> str:
    """Return a stable per-item, per-revision, per-authority-interpretation
    origination identity.

    ``proposed_scope`` / ``success_criteria`` are keyword-only and
    required (no default) so every caller states explicitly which
    authority-bearing interpretation this identity is for -- see this
    module's own docstring for why both are part of the identity.
    """
    loc = authoritative_source.location
    item_id = authoritative_source.subject_id
    item_digest = authoritative_source.subject_digest
    if item_id is None or item_digest is None:
        raise ValueError("authoritative source is missing its structured roadmap subject")
    return origination_identity_from_parts(
        project_id,
        loc,
        item_id,
        item_digest,
        proposed_scope,
        success_criteria,
    )


def work_id_for(project_id: str, item_id: str) -> str:
    """A stable ``WorkNode.package_id`` for one logical roadmap item.

    ``atlas_contracts.versions.ID_PATTERN`` requires an alphanumeric-first,
    ``[A-Za-z0-9._-]*`` string. Hashing the explicit project/item pair makes
    dependency edges resolvable before either node is materialized, and keeps
    the package id stable when the item's own specification is revised.
    """
    payload = f"{project_id}::{item_id}"
    return f"ORIG-{hashlib.sha256(payload.encode('utf-8')).hexdigest()[:16]}"
