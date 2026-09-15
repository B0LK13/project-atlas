"""MCP server surface tests — resources, outputTemplate/CSP, WRITE_TOOL_COUNT=0."""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("mcp")

import atlas_gateway as gw
import mcp.types as types
import server as srv


def test_write_tool_count_is_zero() -> None:
    assert srv.WRITE_TOOL_COUNT == 0
    assert srv.write_tool_count() == 0
    assert len(srv.build_tools()) == 4


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
        assert meta["openai/outputTemplate"] == srv.WIDGET_URI, tool.name
        assert meta["ui"]["resourceUri"] == srv.WIDGET_URI, tool.name


def test_widget_resource_registered_with_csp() -> None:
    resources = srv.build_resources()
    assert len(resources) == 1
    resource = resources[0]
    assert str(resource.uri) == srv.WIDGET_URI
    # mcp SDK drift: the field is `mime_type` (wire alias `mimeType`).
    assert resource.mime_type == srv.WIDGET_MIME
    html = srv.load_widget_html()
    assert "Content-Security-Policy" in html
    assert "default-src 'none'" in html
    assert "GRAPH != AUTHORITY" in html
    assert "DEMO_FIXTURE" in html or "not authentic pilot" in html
    assert "ATLAS EVIDENCE" in html


@pytest.mark.asyncio
async def test_server_handlers_list_and_read_widget(demo_vault: Path) -> None:
    """mcp 2.0: handlers are constructor ``on_*`` callables, not decorator maps."""
    server = srv.build_server(demo_vault)
    assert server.get_request_handler("tools/list") is not None
    assert server.get_request_handler("tools/call") is not None
    assert server.get_request_handler("resources/list") is not None
    assert server.get_request_handler("resources/read") is not None

    list_tools = server.get_request_handler("tools/list")
    assert list_tools is not None
    tools_result = await list_tools.handler(None, None)
    tools = tools_result.tools  # type: ignore[attr-defined]
    assert {t.name for t in tools} == {
        "search",
        "fetch",
        "atlas_project_status",
        "atlas_graph_neighbors",
    }
    assert srv.write_tool_count() == 0

    list_res = server.get_request_handler("resources/list")
    assert list_res is not None
    res_result = await list_res.handler(None, None)
    resources = res_result.resources  # type: ignore[attr-defined]
    assert any(str(r.uri) == srv.WIDGET_URI for r in resources)

    read_res = server.get_request_handler("resources/read")
    assert read_res is not None
    read_params = types.ReadResourceRequestParams(uri=srv.WIDGET_URI)
    read_result = await read_res.handler(None, read_params)
    contents = read_result.contents  # type: ignore[attr-defined]
    assert len(contents) == 1
    assert contents[0].mime_type == srv.WIDGET_MIME
    assert "Content-Security-Policy" in contents[0].text
    assert "GRAPH != AUTHORITY" in contents[0].text


def test_to_call_result_carries_structured_content(demo_vault: Path) -> None:
    result = srv.to_call_result(gw.atlas_project_status(demo_vault, "harbor-api"))
    dumped = result.model_dump(by_alias=True, exclude_none=True)
    assert dumped["structuredContent"]["project"] == "harbor-api"
    assert dumped["structuredContent"]["source_class"] == "DEMO_FIXTURE"
    assert dumped["structuredContent"]["graph_authority"] is False
    assert dumped["content"][0]["type"] == "text"
    assert dumped.get("isError") in (False, None)


def test_no_write_tools_registered() -> None:
    for tool in srv.build_tools():
        assert not any(
            verb in tool.name for verb in ("write", "ingest", "delete", "mutate", "create", "update")
        ), tool.name
