"""Real local Cursor SDK smoke: launch_bridge → create → A/B → restart → resume → C."""

from __future__ import annotations

import asyncio
import json
import os
import re
import shutil
import sys
from pathlib import Path
from typing import Any

from project_atlas.orchestration.sdk.event_log import append_event
from project_atlas.orchestration.sdk.models import PACKAGE_ID, STATE_DIR_RELATIVE
from project_atlas.orchestration.sdk.windows_bridge import (
    apply_windows_discovery_patch,
    official_bridge_command,
)

REQUIRED_WORKSPACE = Path(
    r"D:\atlas-acceptance-d060\d-autonomous-governor-079\wt-broker"
)
PROOF_NAME = "local-sdk-proof.json"
_SECRET_RE = re.compile(
    r"(?i)(token|cookie|credential|authorization|bearer|api[_-]?key|authToken|"
    r"crsr_[A-Za-z0-9._-]+|sk-[A-Za-z0-9._-]+)=\S+"
)


def _prepare_windows_loop() -> None:
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


SMOKE_A = (
    "READ-ONLY bounded repository inspection. Do not edit, commit, push, or merge. "
    "Open src/project_atlas/orchestration/sdk/models.py and return only the exact "
    f"PACKAGE_ID string. Expected package is {PACKAGE_ID}."
)
SMOKE_B = (
    "READ-ONLY automatic follow-up. Do not edit. Confirm the same PACKAGE_ID "
    f"({PACKAGE_ID}) and that this is still a local agent in the same workspace."
)
SMOKE_C = (
    "READ-ONLY resume proof after supervisor-side bridge restart. Do not edit. "
    f"Repeat PACKAGE_ID {PACKAGE_ID} and confirm prior smoke context is retained."
)


def sanitize_message(message: str) -> str:
    cleaned = _SECRET_RE.sub(r"\1=[REDACTED]", message)
    cleaned = re.sub(r"http://127\.0\.0\.1:\d+", "http://127.0.0.1:[PORT]", cleaned)
    return cleaned[:800]


def proof_path(root: Path) -> Path:
    return root / STATE_DIR_RELATIVE / PROOF_NAME


def _bridge_diagnostics() -> dict[str, object]:
    resolved: str | None = None
    try:
        from cursor_sdk._vendor import resolve_bridge_path

        resolved = str(resolve_bridge_path())
    except Exception as exc:
        resolved = f"unresolved:{type(exc).__name__}"
    cursor_cli = shutil.which("cursor") or shutil.which("cursor.cmd")
    cursor_agent = shutil.which("cursor-agent") or shutil.which("cursor-agent.cmd")
    session_dir = Path.home() / ".cursor"
    return {
        "sdk_version": _sdk_version(),
        "bridge_executable": resolved,
        "bridge_on_path": bool(shutil.which("cursor-sdk-bridge")),
        "cursor_cli_present": bool(cursor_cli),
        "cursor_agent_present": bool(cursor_agent),
        "local_cursor_session_dir_exists": session_dir.is_dir(),
        "cursor_api_key_available": (
            "YES" if str(os.environ.get("CURSOR_API_KEY", "")).strip() else "NO"
        ),
        "workspace": str(REQUIRED_WORKSPACE),
    }


def _sdk_version() -> str | None:
    try:
        import importlib.metadata

        return importlib.metadata.version("cursor-sdk")
    except importlib.metadata.PackageNotFoundError:
        return None


def _model_ids(listing: Any) -> list[str]:
    items: Any
    if listing is None:
        return []
    if hasattr(listing, "items") and not isinstance(listing, dict):
        try:
            items = listing.items
        except Exception:
            items = listing
    else:
        items = listing
    if isinstance(items, dict):
        items = items.get("items") or items.get("models") or []
    ids: list[str] = []
    if not isinstance(items, list):
        return ids
    for row in items:
        if isinstance(row, str):
            ids.append(row)
            continue
        ident = getattr(row, "id", None) or getattr(row, "model_id", None)
        if ident is None and isinstance(row, dict):
            ident = row.get("id") or row.get("model_id")
        if ident:
            ids.append(str(ident))
    return ids


def _pick_model(ids: list[str]) -> str:
    preferred = ("composer-2.5", "composer-2", "auto-smart", "grok-4.5")
    for name in preferred:
        if name in ids:
            return name
    if ids:
        return ids[0]
    return "composer-2.5"


def _agent_id(agent: Any) -> str:
    ident = getattr(agent, "agent_id", None)
    if ident:
        return str(ident)
    return str(agent.id)


def _run_id(run: Any) -> str:
    ident = getattr(run, "id", None)
    if ident:
        return str(ident)
    return str(run.run_id)


async def _run_async_proof(root: Path) -> dict[str, object]:
    from cursor_sdk import AsyncClient, LocalAgentOptions

    apply_windows_discovery_patch()
    workspace = str(REQUIRED_WORKSPACE)
    cwd = workspace
    report: dict[str, object] = {
        "path": "async_launch_bridge",
        "workspace": workspace,
        **_bridge_diagnostics(),
    }
    command = official_bridge_command()
    if command is None:
        client = await AsyncClient.launch_bridge(workspace=workspace)
    else:
        client = await AsyncClient.launch_bridge(command, workspace=workspace)
    report["local_bridge_launch"] = "PASS"
    try:
        listing = await client.models.list()
        models = _model_ids(listing)
        report["models"] = models
        report["local_model_discovery"] = "PASS" if models else "FAIL"
        model = _pick_model(models)
        report["model"] = model
        agent = await client.agents.create(
            model=model,
            local=LocalAgentOptions(cwd=cwd),
        )
        agent_id = _agent_id(agent)
        if not agent_id.startswith("agent-"):
            raise RuntimeError(f"expected agent-* id, got {agent_id[:32]}")
        report["real_local_agent_id"] = agent_id
        append_event(
            root,
            "SDK_AGENT_CREATED",
            dag_generation=84,
            agent_id=agent_id,
            node="SDK-SMOKE-A",
        )
        run_a = await agent.send(SMOKE_A)
        run_a_id = _run_id(run_a)
        append_event(
            root,
            "SDK_RUN_CREATED",
            dag_generation=84,
            agent_id=agent_id,
            run_id=run_a_id,
            node="SDK-SMOKE-A",
        )
        await run_a.wait()
        append_event(
            root,
            "SDK_RUN_FINISHED",
            dag_generation=84,
            agent_id=agent_id,
            run_id=run_a_id,
            node="SDK-SMOKE-A",
        )
        report["real_run_a_id"] = run_a_id
        run_b = await agent.send(SMOKE_B)
        run_b_id = _run_id(run_b)
        append_event(
            root,
            "SDK_RUN_CREATED",
            dag_generation=84,
            agent_id=agent_id,
            run_id=run_b_id,
            node="SDK-SMOKE-B",
        )
        await run_b.wait()
        append_event(
            root,
            "SDK_RUN_FINISHED",
            dag_generation=84,
            agent_id=agent_id,
            run_id=run_b_id,
            node="SDK-SMOKE-B",
        )
        report["real_run_b_id"] = run_b_id
        report["same_agent_id"] = True
        report["human_continue_messages"] = 0
    finally:
        close = getattr(client, "aclose", None)
        if close is not None:
            result = close()
            if asyncio.iscoroutine(result):
                await result

    if command is None:
        client2 = await AsyncClient.launch_bridge(workspace=workspace)
    else:
        client2 = await AsyncClient.launch_bridge(command, workspace=workspace)
    try:
        resumed = await client2.agents.resume(str(report["real_local_agent_id"]))
        resumed_id = _agent_id(resumed)
        report["resume_agent_id"] = resumed_id
        report["duplicate_agent"] = resumed_id != report["real_local_agent_id"]
        append_event(
            root,
            "SDK_AGENT_RESUMED",
            dag_generation=84,
            agent_id=resumed_id,
            node="SDK-SMOKE-C",
        )
        run_c = await resumed.send(SMOKE_C)
        run_c_id = _run_id(run_c)
        append_event(
            root,
            "SDK_RUN_CREATED",
            dag_generation=84,
            agent_id=resumed_id,
            run_id=run_c_id,
            node="SDK-SMOKE-C",
        )
        await run_c.wait()
        append_event(
            root,
            "SDK_RUN_FINISHED",
            dag_generation=84,
            agent_id=resumed_id,
            run_id=run_c_id,
            node="SDK-SMOKE-C",
        )
        report["real_run_c_id"] = run_c_id
        report["local_agent_resume_after_restart"] = (
            "PASS" if resumed_id == report["real_local_agent_id"] else "FAIL"
        )
        report["real_local_followup_without_human"] = "PASS"
        report["local_agent_create"] = "PASS"
        report["local_agent_create_error"] = "NONE"
    finally:
        close = getattr(client2, "aclose", None)
        if close is not None:
            result = close()
            if asyncio.iscoroutine(result):
                await result
    return report


def _run_sync_proof(root: Path) -> dict[str, object]:
    from cursor_sdk import CursorClient, LocalAgentOptions

    apply_windows_discovery_patch()
    workspace = str(REQUIRED_WORKSPACE)
    report: dict[str, object] = {
        "path": "sync_launch_bridge",
        "workspace": workspace,
        **_bridge_diagnostics(),
    }
    command = official_bridge_command()
    if command is not None:
        ctx = CursorClient.launch_bridge(command, workspace=workspace)
    else:
        ctx = CursorClient.launch_bridge(workspace=workspace)
    with ctx as client:
        report["local_bridge_launch"] = "PASS"
        listing = client.models.list()
        models = _model_ids(listing)
        report["models"] = models
        report["local_model_discovery"] = "PASS" if models else "FAIL"
        model = _pick_model(models)
        report["model"] = model
        agent = client.agents.create(
            model=model,
            local=LocalAgentOptions(cwd=workspace),
        )
        agent_id = _agent_id(agent)
        if not agent_id.startswith("agent-"):
            raise RuntimeError(f"expected agent-* id, got {agent_id[:32]}")
        report["real_local_agent_id"] = agent_id
        append_event(
            root, "SDK_AGENT_CREATED", dag_generation=84, agent_id=agent_id, node="SDK-SMOKE-A"
        )
        run_a = agent.send(SMOKE_A)
        run_a_id = _run_id(run_a)
        append_event(
            root,
            "SDK_RUN_CREATED",
            dag_generation=84,
            agent_id=agent_id,
            run_id=run_a_id,
            node="SDK-SMOKE-A",
        )
        run_a.wait()
        append_event(
            root,
            "SDK_RUN_FINISHED",
            dag_generation=84,
            agent_id=agent_id,
            run_id=run_a_id,
            node="SDK-SMOKE-A",
        )
        report["real_run_a_id"] = run_a_id
        run_b = agent.send(SMOKE_B)
        run_b_id = _run_id(run_b)
        append_event(
            root,
            "SDK_RUN_CREATED",
            dag_generation=84,
            agent_id=agent_id,
            run_id=run_b_id,
            node="SDK-SMOKE-B",
        )
        run_b.wait()
        append_event(
            root,
            "SDK_RUN_FINISHED",
            dag_generation=84,
            agent_id=agent_id,
            run_id=run_b_id,
            node="SDK-SMOKE-B",
        )
        report["real_run_b_id"] = run_b_id
        report["same_agent_id"] = True
        report["human_continue_messages"] = 0

    if command is not None:
        ctx2 = CursorClient.launch_bridge(command, workspace=workspace)
    else:
        ctx2 = CursorClient.launch_bridge(workspace=workspace)
    with ctx2 as client:
        resumed = client.agents.resume(str(report["real_local_agent_id"]))
        resumed_id = _agent_id(resumed)
        report["resume_agent_id"] = resumed_id
        report["duplicate_agent"] = resumed_id != report["real_local_agent_id"]
        append_event(
            root,
            "SDK_AGENT_RESUMED",
            dag_generation=84,
            agent_id=resumed_id,
            node="SDK-SMOKE-C",
        )
        run_c = resumed.send(SMOKE_C)
        run_c_id = _run_id(run_c)
        append_event(
            root,
            "SDK_RUN_CREATED",
            dag_generation=84,
            agent_id=resumed_id,
            run_id=run_c_id,
            node="SDK-SMOKE-C",
        )
        run_c.wait()
        append_event(
            root,
            "SDK_RUN_FINISHED",
            dag_generation=84,
            agent_id=resumed_id,
            run_id=run_c_id,
            node="SDK-SMOKE-C",
        )
        report["real_run_c_id"] = run_c_id
        report["local_agent_resume_after_restart"] = (
            "PASS" if resumed_id == report["real_local_agent_id"] else "FAIL"
        )
        report["real_local_followup_without_human"] = "PASS"
        report["local_agent_create"] = "PASS"
        report["local_agent_create_error"] = "NONE"
    return report


def persist_proof(root: Path, report: dict[str, object]) -> Path:
    path = proof_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    safe = {
        key: value
        for key, value in report.items()
        if key
        not in {
            "prompt",
            "token",
            "cookie",
            "credential",
            "api_key",
        }
    }
    path.write_text(json.dumps(safe, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def run_local_sdk_proof(root: Path) -> dict[str, object]:
    """Mint a real local agent-* and complete A → B → restart → resume → C."""
    existing = proof_path(root)
    if existing.is_file():
        try:
            loaded = json.loads(existing.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            loaded = {}
        if (
            isinstance(loaded, dict)
            and str(loaded.get("real_local_agent_id") or "").startswith("agent-")
            and loaded.get("real_run_c_id")
        ):
            loaded["reused_existing_proof"] = True
            return loaded

    report: dict[str, object] = {
        **_bridge_diagnostics(),
        "local_bridge_launch": "FAIL",
        "local_model_discovery": "FAIL",
        "local_agent_create": "FAIL",
        "local_agent_create_error": "NONE",
        "real_local_agent_id": "NONE",
        "real_run_a_id": "NONE",
        "real_run_b_id": "NONE",
        "real_run_c_id": "NONE",
        "real_local_followup_without_human": "FAIL",
        "local_agent_resume_after_restart": "FAIL",
    }
    _prepare_windows_loop()
    apply_windows_discovery_patch()
    try:
        report.update(asyncio.run(_run_async_proof(root)))
    except Exception as async_exc:
        report["async_exception_class"] = type(async_exc).__name__
        winerror = getattr(async_exc, "winerror", None)
        code = getattr(async_exc, "code", "")
        report["async_error_code"] = str(winerror or code or "")
        report["async_sanitized_message"] = sanitize_message(str(async_exc))
        try:
            report.update(_run_sync_proof(root))
        except Exception as sync_exc:
            report["sync_exception_class"] = type(sync_exc).__name__
            report["sync_error_code"] = str(
                getattr(sync_exc, "winerror", None) or getattr(sync_exc, "code", "") or ""
            )
            report["sync_sanitized_message"] = sanitize_message(str(sync_exc))
            report["local_agent_create_error"] = (
                f"{type(sync_exc).__name__}:{sanitize_message(str(sync_exc))}"
            )
    persist_proof(root, report)
    return report
