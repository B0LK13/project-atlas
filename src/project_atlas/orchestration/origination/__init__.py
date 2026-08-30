"""D-PHASE2A — specification-backed autonomous work origination.

See docs/adr/ADR-033-phase2a-specification-backed-work-origination.md for
the full architecture decision. This package is additive: it reads real
project sources directly (never the Atlas vault-ingestion path), derives
durable, evidence-bound origination proposals, and hands READY proposals
to the existing, unmodified governed DAG/lease/dispatch machinery in
``orchestration.autonomy``.

EXPLICITLY_SPECIFIED_BUT_UNSTRUCTURED_WORK = IN_SCOPE
AI_INVENTED_WORK = OUT_OF_SCOPE
FREE_FORM_MODEL_REASONING_IS_AUTHORITY = NO
"""

from __future__ import annotations
