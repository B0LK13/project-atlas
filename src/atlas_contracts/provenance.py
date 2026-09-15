"""Evidence and hash bindings for governed event packages."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from atlas_contracts.versions import HASH_PATTERN


class ProvenanceRecord(BaseModel):
    """Hashes and receipt linkage for one verified event package."""

    model_config = ConfigDict(extra="forbid")

    content_sha256: str = Field(pattern=HASH_PATTERN)
    normalized_sha256: str = Field(pattern=HASH_PATTERN)
    source_receipt_id: str = Field(min_length=1)
