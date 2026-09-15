#!/usr/bin/env python3
"""Thin Cursor beforeSubmitPrompt adapter for broker successor consumption.

No routing policy, merge authority, task selection, or owner policy.
Trusted handshake only: exact broker marker + matching cycle identity.
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
        payload: object = json.loads(raw.decode("utf-8")) if raw else {}
    except (UnicodeError, json.JSONDecodeError) as exc:
        print(f"atlas_before_submit: invalid stdin JSON: {exc}", file=sys.stderr)
        sys.stdout.write('{"continue":true}\n')
        return 0
    root = repository_root()
    root, src = bind_worktree_src()
    try:
        from project_atlas.orchestration.autonomy import continuation_broker
        from project_atlas.orchestration.autonomy.continuation_broker import (
            append_hook_trace,
            handle_before_submit_event,
            hook_config_digest,
        )
    except Exception as exc:  # noqa: BLE001
        print(f"atlas_before_submit: HOOK_IMPORT_FAILURE: {type(exc).__name__}", file=sys.stderr)
        sys.stdout.write('{"continue":true}\n')
        return 0
    match = module_root_match(str(continuation_broker.__file__), src)
    session_id = None
    if isinstance(payload, dict) and isinstance(payload.get("conversation_id"), str):
        session_id = payload["conversation_id"][:256]
    if not match:
        print("atlas_before_submit: HOOK_CODE_IDENTITY MODULE_ROOT_MISMATCH", file=sys.stderr)
        try:
            append_hook_trace(
                root,
                {
                    "event_type": "BEFORE_SUBMIT_MODULE_ROOT_MISMATCH",
                    "session_id": session_id,
                    "hook_pid": _pid(),
                    "python_executable": sys.executable,
                    "resolved_repo_root": str(root),
                    "resolved_project_atlas_module_path": str(
                        Path(continuation_broker.__file__).resolve()
                    ),
                    "module_root_match": False,
                    "successor_consumed": False,
                    "error_code": "MODULE_ROOT_MISMATCH",
                    "hook_config_digest": hook_config_digest(root),
                    "hook_adapter_version": HOOK_ADAPTER_VERSION,
                },
            )
        except Exception:  # noqa: BLE001
            pass
        sys.stdout.write('{"continue":true}\n')
        return 0
    try:
        append_hook_trace(
            root,
            {
                "event_type": "BEFORE_SUBMIT_FIRED",
                "session_id": session_id,
                "hook_pid": _pid(),
                "python_executable": sys.executable,
                "resolved_repo_root": str(root),
                "resolved_project_atlas_module_path": str(
                    Path(continuation_broker.__file__).resolve()
                ),
                "module_root_match": True,
                "hook_config_digest": hook_config_digest(root),
                "hook_adapter_version": HOOK_ADAPTER_VERSION,
            },
        )
        response = handle_before_submit_event(payload, root=root)
    except Exception as exc:  # noqa: BLE001
        print(f"atlas_before_submit: handshake error: {type(exc).__name__}", file=sys.stderr)
        sys.stdout.write('{"continue":true}\n')
        return 0
    sys.stdout.write(json.dumps(response, sort_keys=True, separators=(",", ":")) + "\n")
    return 0


def _pid() -> int:
    import os

    return os.getpid()


if __name__ == "__main__":
    raise SystemExit(main())
