"""Documented Cursor Cloud Agents API v1 mutating backend.

Endpoints used (https://cursor.com/docs/cloud-agent/api/endpoints.md,
https://cursor.com/docs-static/cloud-agents-openapi.yaml):

POST /v1/agents
GET  /v1/agents/{id}
POST /v1/agents/{id}/runs
GET  /v1/agents/{id}/runs/{runId}
GET  /v1/agents/{id}/runs/{runId}/stream  (optional)

No invented endpoints. API keys are never persisted, printed, or stored
in broker/host JSON. Presence is reported as YES|NO only.
"""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from collections.abc import Callable
from typing import Final
from uuid import uuid4

from project_atlas.orchestration.autonomy.mutating_transport import (
    MutatingLaunchReceipt,
    MutatingLeaseBinding,
    MutatingTransportError,
    WorkerBackendType,
    compose_worker_prompt,
)

CLOUD_API_BASE: Final[str] = "https://api.cursor.com"
_AGENT_ID_RE = re.compile(
    r"^bc-[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)
_ACTIVE_RUN = frozenset({"CREATING", "RUNNING"})


HttpFn = Callable[[str, str, dict[str, object] | None], tuple[int, dict[str, object]]]


class CursorCloudBackend:
    """Lease-gated Cloud Agents client. Not a second governor."""

    def __init__(
        self,
        *,
        http: HttpFn | None = None,
        repository_url: str = "https://github.com/B0LK13/project-atlas",
        starting_ref: str | None = None,
    ) -> None:
        self._http = http or _stdlib_http
        self._repository_url = repository_url
        self._starting_ref = starting_ref
        self._lineage: dict[str, str] = {}

    def stable_agent_id(self, package_id: str) -> str:
        known = self._lineage.get(package_id)
        if known is not None:
            return known
        minted = f"bc-{uuid4()}"
        if not _AGENT_ID_RE.fullmatch(minted):
            raise MutatingTransportError("cloud agent id is invalid", code="FORGED_AGENT_ID")
        self._lineage[package_id] = minted
        return minted

    def start(self, binding: MutatingLeaseBinding, prompt: str) -> MutatingLaunchReceipt:
        self._require_lease(binding)
        agent_id = self.stable_agent_id(binding.package_id)
        body: dict[str, object] = {
            "agentId": agent_id,
            "mode": "agent",
            "prompt": {"text": compose_worker_prompt(prompt)},
            "workOnCurrentBranch": False,
            "repos": [
                {
                    "url": self._repository_url,
                    "startingRef": self._starting_ref or binding.base_main,
                }
            ],
        }
        try:
            status, payload = self._http("POST", "/v1/agents", body)
        except MutatingTransportError:
            raise
        if status == 409 and _error_code(payload) == "agent_id_conflict":
            return self._reconcile_existing(agent_id)
        if status == 409 and _error_code(payload) == "agent_busy":
            return self._recover_busy(agent_id)
        if status in {401, 403}:
            raise MutatingTransportError("cloud api credential rejected", code=f"API_{status}")
        if status == 429 or status >= 500:
            raise MutatingTransportError("cloud api transient failure", code=f"API_{status}")
        if status not in {200, 201}:
            raise MutatingTransportError("cloud api start failed", code=f"API_{status}")
        return _receipt_from_create(payload, recovered=False)

    def recover(self, agent_id: str, run_id: str) -> MutatingLaunchReceipt:
        self._require_ids(agent_id, run_id)
        status, payload = self._http("GET", f"/v1/agents/{agent_id}/runs/{run_id}", None)
        if status in {401, 403}:
            raise MutatingTransportError("cloud api credential rejected", code=f"API_{status}")
        if status == 404:
            raise MutatingTransportError("unknown cloud run", code="UNKNOWN_WORKER")
        if status == 429 or status >= 500:
            raise MutatingTransportError("cloud api transient failure", code=f"API_{status}")
        if status != 200:
            raise MutatingTransportError("cloud run recover failed", code=f"API_{status}")
        run = _require_run(payload)
        return MutatingLaunchReceipt(
            backend=WorkerBackendType.CLOUD_API,
            agent_id=str(run.get("agentId") or agent_id),
            run_id=str(run.get("id") or run_id),
            status=str(run.get("status") or "ERROR"),
            recovered=True,
        )

    def follow_up(self, agent_id: str, prompt: str) -> MutatingLaunchReceipt:
        self._require_ids(agent_id, None)
        prompt_body: dict[str, object] = {"text": compose_worker_prompt(prompt)}
        body: dict[str, object] = {"prompt": prompt_body, "mode": "agent"}
        status, payload = self._http("POST", f"/v1/agents/{agent_id}/runs", body)
        if status == 409 and _error_code(payload) == "agent_busy":
            return self._recover_busy(agent_id)
        if status in {401, 403}:
            raise MutatingTransportError("cloud api credential rejected", code=f"API_{status}")
        if status == 429 or status >= 500:
            raise MutatingTransportError("cloud api transient failure", code=f"API_{status}")
        if status not in {200, 201}:
            raise MutatingTransportError("cloud follow-up failed", code=f"API_{status}")
        run = _require_run(payload)
        return MutatingLaunchReceipt(
            backend=WorkerBackendType.CLOUD_API,
            agent_id=str(run.get("agentId") or agent_id),
            run_id=str(run.get("id") or ""),
            status=str(run.get("status") or "CREATING"),
        )

    def _reconcile_existing(self, agent_id: str) -> MutatingLaunchReceipt:
        status, payload = self._http("GET", f"/v1/agents/{agent_id}", None)
        if status != 200:
            raise MutatingTransportError("cloud agent reconcile failed", code=f"API_{status}")
        agent = payload.get("agent") if isinstance(payload.get("agent"), dict) else payload
        if not isinstance(agent, dict):
            raise MutatingTransportError("cloud agent payload invalid", code="STATE_CORRUPT")
        latest = str(agent.get("latestRunId") or "")
        if latest:
            return self.recover(agent_id, latest)
        return MutatingLaunchReceipt(
            backend=WorkerBackendType.CLOUD_API,
            agent_id=agent_id,
            run_id=latest or "run-reconciled",
            status="FINISHED",
            recovered=True,
        )

    def _recover_busy(self, agent_id: str) -> MutatingLaunchReceipt:
        # Use only documented GET /v1/agents/{id} + GET run. Do not invent a list endpoint.
        receipt = self._reconcile_existing(agent_id)
        if receipt.status in _ACTIVE_RUN:
            return receipt
        raise MutatingTransportError("agent_busy without active run", code="AGENT_BUSY")

    def _require_lease(self, binding: MutatingLeaseBinding) -> None:
        if binding.merge_authorized or binding.direct_main:
            raise MutatingTransportError(
                "cloud worker cannot carry merge authority",
                code="AUTHORITY_DENIED",
            )

    def _require_ids(self, agent_id: str, run_id: str | None) -> None:
        if not _AGENT_ID_RE.fullmatch(agent_id):
            raise MutatingTransportError("forged cloud agent id", code="FORGED_AGENT_ID")
        if run_id is not None and (not run_id.startswith("run-") or ".." in run_id):
            raise MutatingTransportError("forged cloud run id", code="FORGED_RUN_ID")


def _error_code(payload: dict[str, object]) -> str:
    for key in ("code", "error", "error_code"):
        value = payload.get(key)
        if isinstance(value, str):
            return value
    error = payload.get("error")
    if isinstance(error, dict):
        code = error.get("code")
        if isinstance(code, str):
            return code
    return ""


def _require_run(payload: dict[str, object]) -> dict[str, object]:
    run = payload.get("run") if isinstance(payload.get("run"), dict) else payload
    if not isinstance(run, dict):
        raise MutatingTransportError("cloud run payload invalid", code="STATE_CORRUPT")
    return run


def _receipt_from_create(payload: dict[str, object], *, recovered: bool) -> MutatingLaunchReceipt:
    raw_agent = payload.get("agent")
    agent: dict[str, object] = raw_agent if isinstance(raw_agent, dict) else {}
    run = _require_run(payload)
    agent_id = str(agent.get("id") or run.get("agentId") or "")
    return MutatingLaunchReceipt(
        backend=WorkerBackendType.CLOUD_API,
        agent_id=agent_id,
        run_id=str(run.get("id") or ""),
        status=str(run.get("status") or "CREATING"),
        recovered=recovered,
    )


def _stdlib_http(
    method: str,
    path: str,
    body: dict[str, object] | None,
) -> tuple[int, dict[str, object]]:
    key = os.environ.get("CURSOR_API_KEY")
    if not key:
        raise MutatingTransportError("cloud api key is absent", code="API_UNAVAILABLE")
    if not path.startswith("/v1/"):
        raise MutatingTransportError("refusing non-v1 cloud path", code="PATH_UNSAFE")
    data = None if body is None else json.dumps(body).encode("utf-8")
    request = urllib.request.Request(
        url=f"{CLOUD_API_BASE}{path}",
        data=data,
        method=method,
        headers={
            "Authorization": f"Bearer {key}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            raw = response.read().decode("utf-8")
            payload = json.loads(raw) if raw else {}
            if not isinstance(payload, dict):
                raise MutatingTransportError("cloud api payload invalid", code="STATE_CORRUPT")
            return int(response.status), payload
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8") if exc.fp is not None else "{}"
        try:
            payload = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            payload = {"code": "HTTP_ERROR"}
        if not isinstance(payload, dict):
            payload = {"code": "HTTP_ERROR"}
        return int(exc.code), payload
    except urllib.error.URLError as exc:
        raise MutatingTransportError("cloud api network failure", code="API_NETWORK") from exc
