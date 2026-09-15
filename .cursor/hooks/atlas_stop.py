#!/usr/bin/env python3
"""AS-ORCH-001C / continuation-broker thin Cursor stop adapter.

Cursor is transport only. This script contains no workflow policy, role
selection, privilege decisions, or prose parsing. It binds the current
worktree ``src`` before any ``project_atlas`` import, then prints exactly
one JSON object to stdout.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from atlas_hook_runtime import (
    HOOK_ADAPTER_VERSION,
    bind_worktree_src,
    module_root_match,
    repository_root,
)


def main() -> int:
    raw = sys.stdin.buffer.read()
    try:
        payload: object = json.loads(raw.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        print(f"atlas_stop: invalid stdin JSON: {exc}", file=sys.stderr)
        sys.stdout.write("{}\n")
        return 0
    root = repository_root()
    src: Path
    root, src = bind_worktree_src()
    try:
        from project_atlas.orchestration import cursor_bridge
        from project_atlas.orchestration.autonomy.continuation_broker import (
            append_hook_trace,
            hook_config_digest,
        )
        from project_atlas.orchestration.cursor_bridge import handle_stop_event
    except Exception as exc:  # noqa: BLE001 — hook must fail closed to {}
        print(f"atlas_stop: HOOK_IMPORT_FAILURE: {type(exc).__name__}", file=sys.stderr)
        sys.stdout.write("{}\n")
        return 0
    match = module_root_match(str(cursor_bridge.__file__), src)
    loop_count = 0
    session_id = None
    if isinstance(payload, dict):
        raw_loop = payload.get("loop_count")
        if isinstance(raw_loop, int):
            loop_count = raw_loop
        raw_session = payload.get("conversation_id")
        if isinstance(raw_session, str):
            session_id = raw_session[:256]
    if not match:
        print("atlas_stop: HOOK_CODE_IDENTITY MODULE_ROOT_MISMATCH", file=sys.stderr)
        try:
            append_hook_trace(
                root,
                {
                    "event_type": "STOP_HOOK_MODULE_ROOT_MISMATCH",
                    "session_id": session_id,
                    "loop_count": loop_count,
                    "hook_pid": os_getpid(),
                    "python_executable": sys.executable,
                    "resolved_repo_root": str(root),
                    "resolved_project_atlas_module_path": str(
                        Path(cursor_bridge.__file__).resolve()
                    ),
                    "module_root_match": False,
                    "followup_returned": False,
                    "error_code": "MODULE_ROOT_MISMATCH",
                    "hook_config_digest": hook_config_digest(root),
                    "hook_adapter_version": HOOK_ADAPTER_VERSION,
                },
            )
        except Exception:  # noqa: BLE001
            pass
        sys.stdout.write("{}\n")
        return 0
    try:
        append_hook_trace(
            root,
            {
                "event_type": "STOP_HOOK_FIRED",
                "session_id": session_id,
                "loop_count": loop_count,
                "hook_pid": os_getpid(),
                "python_executable": sys.executable,
                "resolved_repo_root": str(root),
                "resolved_project_atlas_module_path": str(Path(cursor_bridge.__file__).resolve()),
                "module_root_match": True,
                "hook_config_digest": hook_config_digest(root),
                "hook_adapter_version": HOOK_ADAPTER_VERSION,
            },
        )
        response = handle_stop_event(payload, root=root)
    except Exception as exc:  # noqa: BLE001 — hook must fail closed to {}
        print(f"atlas_stop: bridge error: {type(exc).__name__}", file=sys.stderr)
        try:
            append_hook_trace(
                root,
                {
                    "event_type": "STOP_HOOK_RUNTIME_FAILURE",
                    "session_id": session_id,
                    "loop_count": loop_count,
                    "followup_returned": False,
                    "error_code": "HOOK_INTERPRETER_FAILURE",
                    "module_root_match": True,
                },
            )
        except Exception:  # noqa: BLE001
            pass
        sys.stdout.write("{}\n")
        return 0
    sys.stdout.write(json.dumps(response, sort_keys=True, separators=(",", ":")) + "\n")
    return 0


def os_getpid() -> int:
    import os

    return os.getpid()


if __name__ == "__main__":
    raise SystemExit(main())
