"""Pipeline and receipt references shared across Atlas tracks."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class PipelineState(BaseModel):
    """Captured pipeline stages; verified packages require every stage."""

    model_config = ConfigDict(extra="forbid")

    captured: bool
    normalized: bool
    verified: bool
    routed: bool

    def is_verified(self) -> bool:
        return all((self.captured, self.normalized, self.verified, self.routed))


class ReceiptReference(BaseModel):
    """Reference to the immutable Control Plane event receipt."""

    model_config = ConfigDict(extra="forbid")

    receipt_id: str = Field(min_length=1)
    status: Literal["valid", "pending", "rejected"]
    event_id: str = Field(min_length=1)
