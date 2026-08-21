"""Windows-safe official cursor-sdk-bridge launch helpers.

The stock sync discovery reader calls os.set_blocking / selectors on a pipe,
which raises WinError 10038 on Windows. Async launch_bridge is preferred.
This module never logs discovery tokens.
"""

from __future__ import annotations

import os
import threading
from pathlib import Path
from typing import Any

_PATCHED = False


def official_bridge_command() -> list[str] | None:
    """Resolve node.exe + bridge.js so we do not spawn the .cmd wrapper."""
    try:
        from cursor_sdk._vendor import resolve_bridge_path
    except Exception:
        return None
    cmd = Path(resolve_bridge_path())
    node = cmd.with_name("node.exe")
    script = cmd.parent.parent / "dist" / "bin" / "cursor-sdk-bridge.js"
    if node.is_file() and script.is_file():
        return [str(node), str(script)]
    if cmd.is_file():
        return [str(cmd)]
    return None


def apply_windows_discovery_patch() -> bool:
    """Replace sync discovery reader so launch_bridge works on Windows pipes."""
    global _PATCHED
    if os.name != "nt":
        return False
    if _PATCHED:
        return True
    import cursor_sdk._bridge as bridge_mod
    from cursor_sdk._bridge import parse_discovery_line
    from cursor_sdk.errors import CursorSDKError

    def _windows_read_discovery(
        process: Any, timeout: float
    ) -> Any:
        if process.stderr is None:
            raise CursorSDKError("Bridge process stderr is unavailable")
        holder: dict[str, Any] = {}

        def _reader() -> None:
            try:
                while True:
                    line = process.stderr.readline()
                    if not line:
                        holder["eof"] = True
                        return
                    parsed = parse_discovery_line(line)
                    if parsed is not None:
                        holder["discovery"] = parsed
                        return
            except Exception as exc:  # diagnostics only; never includes secrets
                holder["error"] = exc

        thread = threading.Thread(target=_reader, daemon=True)
        thread.start()
        thread.join(timeout)
        if "discovery" in holder:
            return holder["discovery"]
        if process.poll() is not None:
            raise CursorSDKError(
                f"Bridge exited before discovery with status {process.returncode}"
            )
        if "error" in holder:
            raise CursorSDKError("Bridge discovery reader failed") from holder["error"]
        raise CursorSDKError("Timed out waiting for bridge discovery")

    bridge_mod._read_discovery = _windows_read_discovery
    _PATCHED = True
    return True
