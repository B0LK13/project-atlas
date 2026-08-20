"""CURSOR_API_KEY discovery without ever printing or persisting the secret."""

from __future__ import annotations

import importlib.metadata
import json
import os
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from project_atlas.orchestration.sdk.models import (
    AUTH_PREREQ_NAME,
    STATE_DIR_RELATIVE,
    SdkRuntimeError,
)


class AuthDiscovery(BaseModel):
    """Public auth capability report. Never includes secret material."""

    model_config = ConfigDict(extra="forbid")

    cursor_api_key_available: Literal["YES", "NO"]
    local_sdk_available: Literal["YES", "NO"]
    cloud_sdk_runtime: Literal["ENABLED", "DISABLED"]
    cursor_sdk_version: str | None = None
    prerequisite: str | None = None
    merge_authorized: Literal[False] = False
    execution_authorized: Literal[False] = False


def cursor_sdk_version() -> str | None:
    try:
        return importlib.metadata.version("cursor-sdk")
    except importlib.metadata.PackageNotFoundError:
        return None


def discover_auth(*, environ: dict[str, str] | None = None) -> AuthDiscovery:
    """Detect API key presence and local SDK importability. Never returns the key."""
    env = environ if environ is not None else dict(os.environ)
    key_present = bool(str(env.get("CURSOR_API_KEY", "")).strip())
    version = cursor_sdk_version()
    local_ok = False
    try:
        import cursor_sdk  # noqa: F401

        local_ok = version is not None
    except ImportError:
        local_ok = False

    cloud_enabled = key_present and local_ok
    # Functional backend exists when cloud is enabled or the official package imports
    # (local runtime may still use ambient Cursor app auth).
    functional = cloud_enabled or local_ok
    return AuthDiscovery(
        cursor_api_key_available="YES" if key_present else "NO",
        local_sdk_available="YES" if local_ok else "NO",
        cloud_sdk_runtime="ENABLED" if cloud_enabled else "DISABLED",
        cursor_sdk_version=version,
        prerequisite=None if functional else "CURSOR_SDK_AUTH_REQUIRED",
    )


def record_auth_prerequisite(root: Path, discovery: AuthDiscovery) -> bool:
    """Persist at most one CURSOR_SDK_AUTH_REQUIRED receipt. Returns True if newly written."""
    if discovery.prerequisite != "CURSOR_SDK_AUTH_REQUIRED":
        return False
    store = root / STATE_DIR_RELATIVE
    store.mkdir(parents=True, exist_ok=True)
    target = store / AUTH_PREREQ_NAME
    if target.exists():
        return False
    payload = {
        "prerequisite": "CURSOR_SDK_AUTH_REQUIRED",
        "cursor_api_key_available": discovery.cursor_api_key_available,
        "local_sdk_available": discovery.local_sdk_available,
        "cloud_sdk_runtime": discovery.cloud_sdk_runtime,
        "cursor_sdk_version": discovery.cursor_sdk_version,
        "owner_action_required_now": False,
        "merge_authorized": False,
        "execution_authorized": False,
        "note": "Do not repeatedly ask owner. Do not store API key.",
    }
    encoded = json.dumps(payload, sort_keys=True, indent=2, ensure_ascii=True) + "\n"
    tmp = target.with_name(f".{target.name}.tmp")
    tmp.write_text(encoded, encoding="utf-8")
    os.replace(tmp, target)
    return True


def require_functional_backend(discovery: AuthDiscovery) -> None:
    """Fail closed only when no execution backend remains."""
    if discovery.cloud_sdk_runtime == "ENABLED":
        return
    if discovery.local_sdk_available == "YES":
        return
    raise SdkRuntimeError(
        "no functional Cursor SDK execution backend",
        code="CURSOR_SDK_AUTH_REQUIRED",
    )


class BudgetConfig(BaseModel):
    """Spend guard configuration. Metrics are not authority."""

    model_config = ConfigDict(extra="forbid")

    max_charged_cents: float | None = Field(default=None, ge=0)
    max_total_tokens: int | None = Field(default=None, ge=0)
    park_optional_when_exceeded: bool = True
