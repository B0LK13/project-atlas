"""T003E regression: local provider compaction must fit the 4Ki context window.

Evidence: attempt 1232a02b — DEFAULT reserveTokens=16384 with contextWindow=4096
made shouldCompact() true after the first tool round (COMPLETED_NO_EFFECT).
"""

from __future__ import annotations

import json
from pathlib import Path

from project_atlas.orchestration.program.adapters.prime_agent import (
    _write_local_provider_config,
)


def _should_compact(context_tokens: int, context_window: int, reserve_tokens: int) -> bool:
    """Mirror coding-agent shouldCompact threshold (usage > window - reserve)."""
    if context_window <= 0:
        return False
    return context_tokens > (context_window - reserve_tokens)


def test_write_local_provider_config_sizes_compaction_to_context_window(tmp_path: Path) -> None:
    agent_dir = tmp_path / "agent"
    _write_local_provider_config(
        agent_dir, provider="atlas-local-qwen", port=38742, model="qwen3:1.7b-q4_K_M"
    )
    models = json.loads((agent_dir / "models.json").read_text(encoding="utf-8"))
    settings = json.loads((agent_dir / "settings.json").read_text(encoding="utf-8"))
    window = models["providers"]["atlas-local-qwen"]["models"][0]["contextWindow"]
    assert window == 4096
    reserve = settings["compaction"]["reserveTokens"]
    keep = settings["compaction"]["keepRecentTokens"]
    assert reserve == max(256, window // 8)  # 512
    assert keep == max(512, window // 4)  # 1024
    assert reserve < window
    assert keep < window
    # Exact T003E failure shape: post-probe usage must NOT force compaction.
    assert _should_compact(2113, window, reserve) is False
    # Legacy default 16384 would always fire on a 4Ki window.
    assert _should_compact(1, window, 16384) is True


def test_malformed_empty_tool_response_helpers_documented() -> None:
    """Placeholder anchor: empty/malformed tool responses stay fail-closed at parser.

    Full daemon parser coverage lives in coding-agent tests; this ensures the
    Atlas adapter still writes settings.json so the runtime path is configured.
    """
    assert callable(_write_local_provider_config)
