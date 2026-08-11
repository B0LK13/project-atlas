"""MCP server surface tests — read-only annotations + Apps SDK widget metadata."""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("mcp")

import atlas_gateway as gw
import server as srv


def test_build_tools_are_read_only_with_widget_templates() -> None:
    tools = srv.build_tools()
    names = {t.name for t in tools}
    assert names == {"search", "fetch", "atlas_project_status", "atlas_graph_neighbors"}
    for tool in tools:
        assert tool.annotations is not None
        # Prefer wire aliases (readOnlyHint); SDK field names vary by version.
        ann = tool.annotations.model_dump(by_alias=True)
        assert ann.get("readOnlyHint") is True, tool.name
        assert ann.get("destructiveHint") is False, tool.name
        assert ann.get("openWorldHint") is False, tool.name
        dumped = tool.model_dump(by_alias=True, exclude_none=True)
        meta = dumped["_meta"]
        assert meta["openai/outputTemplate"].startswith("ui://widget/"), tool.name
        assert meta["ui"]["resourceUri"].startswith("ui://widget/"), tool.name


def test_to_call_result_carries_structured_content(demo_vault: Path) -> None:
    result = srv.to_call_result(gw.atlas_project_status(demo_vault, "harbor-api"))
    dumped = result.model_dump(by_alias=True, exclude_none=True)
    assert dumped["structuredContent"]["project"] == "harbor-api"
    assert dumped["structuredContent"]["source_class"] == "DEMO_FIXTURE"
    assert dumped["content"][0]["type"] == "text"
    assert dumped.get("isError") in (False, None)


def test_no_write_tools_registered() -> None:
    for tool in srv.build_tools():
        assert not any(
            verb in tool.name for verb in ("write", "ingest", "delete", "mutate", "create", "update")
        ), tool.name
