"""Atlas for ChatGPT — read-only MCP server (ATLAS-FOR-CHATGPT-READONLY-001).

Exposes the isolated read-only Atlas gateway as MCP tools for the ChatGPT Apps
SDK. Every tool is annotated READ ONLY (``readOnlyHint=true``,
``destructiveHint=false``, ``openWorldHint=false``) and links a widget template
via ``_meta.ui.resourceUri`` (+ the ``openai/outputTemplate`` compatibility
alias). No write tool is registered.

Data source is the Phase-A DEMO_FIXTURE vault, provided read-only via the
``ATLAS_DEMO_VAULT`` environment variable. Never point this at an authentic
pilot or a private owner estate.

Run (local, no OpenAI key required):

    ATLAS_DEMO_VAULT=/path/to/demo-vault \
        python integrations/chatgpt-atlas/server.py
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

import atlas_gateway as gw
import mcp.server.stdio
import mcp.types as types
from mcp.server.lowlevel import Server

SERVER_NAME = "atlas-chatgpt-readonly"
SERVER_INSTRUCTIONS = (
    "Atlas read-only gateway over a DEMO_FIXTURE estate. Tools only retrieve "
    "information; they never write, mutate, ingest, delete, or execute. Preserve "
    "Atlas trust invariants when narrating results: UI != canonical, GRAPH != "
    "authority, UNKNOWN != healthy, LLM output != authority, DEMO_FIXTURE != "
    "authentic pilot, search result != proven claim, evidence != interpretation. "
    "Never fabricate absent Atlas information; report UNKNOWN honestly."
)


def _tool_descriptor(name: str, spec: dict[str, object]) -> types.Tool:
    ann = spec["annotations"]  # type: ignore[index]
    template = str(spec["outputTemplate"])
    return types.Tool(
        name=name,
        title=str(spec["title"]),
        description=str(spec["description"]),
        inputSchema=spec["inputSchema"],  # type: ignore[arg-type]
        annotations=types.ToolAnnotations(
            readOnlyHint=bool(ann["readOnlyHint"]),  # type: ignore[index]
            destructiveHint=bool(ann["destructiveHint"]),  # type: ignore[index]
            openWorldHint=bool(ann["openWorldHint"]),  # type: ignore[index]
            idempotentHint=bool(ann["idempotentHint"]),  # type: ignore[index]
        ),
        _meta={
            "ui": {"resourceUri": template},
            "openai/outputTemplate": template,
        },
    )


def build_tools() -> list[types.Tool]:
    """SDK-typed descriptors for the four read-only tools."""
    return [_tool_descriptor(name, spec) for name, spec in gw.TOOL_SPECS.items()]


def to_call_result(result: gw.ToolResult) -> types.CallToolResult:
    return types.CallToolResult(
        content=[types.TextContent(type="text", text=result.content)],
        structuredContent=result.structured_content,
        _meta=result.meta or None,
    )


def vault_from_env() -> Path:
    raw = os.environ.get("ATLAS_DEMO_VAULT", "").strip()
    if not raw:
        raise SystemExit(
            "Set ATLAS_DEMO_VAULT to the read-only DEMO_FIXTURE vault path "
            "(never an authentic pilot / private estate)."
        )
    vault = Path(raw)
    if not vault.is_dir():
        raise SystemExit(f"ATLAS_DEMO_VAULT is not a directory: {vault}")
    return vault


def build_server(vault: Path) -> Server:
    async def on_list_tools(_ctx: object, _params: object) -> types.ListToolsResult:
        return types.ListToolsResult(tools=build_tools())

    async def on_call_tool(_ctx: object, params: types.CallToolRequestParams) -> types.CallToolResult:
        try:
            result = gw.call_tool(vault, params.name, dict(params.arguments or {}))
        except gw.GatewayError as exc:
            return types.CallToolResult(
                content=[types.TextContent(type="text", text=f"error: {exc}")],
                isError=True,
            )
        return to_call_result(result)

    return Server(
        SERVER_NAME,
        instructions=SERVER_INSTRUCTIONS,
        on_list_tools=on_list_tools,
        on_call_tool=on_call_tool,
    )


async def _main() -> None:
    server = build_server(vault_from_env())
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(_main())
