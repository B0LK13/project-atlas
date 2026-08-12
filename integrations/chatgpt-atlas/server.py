"""Atlas for ChatGPT — read-only MCP server (ATLAS-FOR-CHATGPT-READONLY-001).

Exposes the isolated read-only Atlas gateway as MCP tools for the ChatGPT Apps
SDK. Every tool is annotated READ ONLY (``readOnlyHint=true``,
``destructiveHint=false``, ``openWorldHint=false``) and links a widget template
via ``_meta.ui.resourceUri`` (+ the ``openai/outputTemplate`` compatibility
alias). The widget HTML is registered as an MCP resource so Apps SDK clients
can ``resources/read`` ``ui://widget/atlas-card.html``. No write tool is
registered (``WRITE_TOOL_COUNT = 0``).

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
from typing import Any

import atlas_gateway as gw
import mcp.server.stdio
import mcp.types as types
from mcp.server.lowlevel import Server

SERVER_NAME = "atlas-chatgpt-readonly"
WIDGET_URI = "ui://widget/atlas-card.html"
WIDGET_MIME = "text/html;profile=mcp-app"
WIDGET_PATH = Path(__file__).resolve().parent / "web" / "atlas-card.html"
# Explicit invariant for validators / evidence packs.
WRITE_TOOL_COUNT = 0
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


def write_tool_count() -> int:
    """Count registered tools whose name implies mutation. Must stay 0."""
    forbidden = ("write", "ingest", "delete", "mutate", "create", "update", "run", "execute")
    return sum(1 for t in build_tools() if any(verb in t.name.lower() for verb in forbidden))


def load_widget_html() -> str:
    """Load the Apps SDK card HTML (CSP + GRAPH != AUTHORITY cues included)."""
    if not WIDGET_PATH.is_file():
        raise FileNotFoundError(f"missing widget template: {WIDGET_PATH}")
    return WIDGET_PATH.read_text(encoding="utf-8")


def build_resources() -> list[types.Resource]:
    """MCP resources advertised to Apps SDK clients (widget only)."""
    html = load_widget_html()
    return [
        types.Resource(
            uri=WIDGET_URI,
            name="atlas-card",
            title="Atlas read-only card",
            description=(
                "Adaptive DEMO_FIXTURE project/graph/evidence/search card. "
                "Read-only display; GRAPH != AUTHORITY; not authentic pilot."
            ),
            mimeType=WIDGET_MIME,
            size=len(html.encode("utf-8")),
        )
    ]


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
    """Build the read-only MCP server with tools + widget resource handlers.

    mcp>=2.0 registers handlers via ``on_*`` constructor kwargs (decorator
    ``Server.list_tools`` / ``call_tool`` APIs were removed).
    """

    async def on_list_tools(_ctx: Any, _params: Any) -> types.ListToolsResult:
        return types.ListToolsResult(tools=build_tools())

    async def on_call_tool(_ctx: Any, params: Any) -> types.CallToolResult:
        try:
            result = gw.call_tool(
                vault, str(params.name), dict(params.arguments or {})
            )
        except gw.GatewayError as exc:
            return types.CallToolResult(
                content=[types.TextContent(type="text", text=f"error: {exc}")],
                isError=True,
            )
        return to_call_result(result)

    async def on_list_resources(_ctx: Any, _params: Any) -> types.ListResourcesResult:
        return types.ListResourcesResult(resources=build_resources())

    async def on_read_resource(_ctx: Any, params: Any) -> types.ReadResourceResult:
        uri = params.uri
        if str(uri) != WIDGET_URI:
            raise ValueError(f"unknown resource URI: {uri}")
        return types.ReadResourceResult(
            contents=[
                types.TextResourceContents(
                    uri=uri,
                    mimeType=WIDGET_MIME,
                    text=load_widget_html(),
                )
            ]
        )

    return Server(
        SERVER_NAME,
        instructions=SERVER_INSTRUCTIONS,
        on_list_tools=on_list_tools,
        on_call_tool=on_call_tool,
        on_list_resources=on_list_resources,
        on_read_resource=on_read_resource,
    )


async def _main() -> None:
    server = build_server(vault_from_env())
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(_main())
