"""Integration tests for the opengraph-image MCP server, using the MCP SDK's
in-process client/server harness (no subprocess, no real transport)."""

from __future__ import annotations

import json

import pytest
from mcp.shared.memory import create_connected_server_and_client_session

from opengraph_image.server import mcp


@pytest.mark.asyncio
async def test_lists_five_tools() -> None:
    async with create_connected_server_and_client_session(mcp._mcp_server) as session:
        result = await session.list_tools()
        tool_names = {tool.name for tool in result.tools}
        assert tool_names == {
            "build_graph",
            "query_graph",
            "get_image_entities",
            "list_images",
            "graph_summary",
        }


@pytest.mark.asyncio
async def test_list_images_missing_graph_returns_well_formed_error() -> None:
    async with create_connected_server_and_client_session(mcp._mcp_server) as session:
        result = await session.call_tool(
            "list_images", {"graph_path": "/nonexistent/path/graph.json"}
        )

        text = result.content[0].text
        payload = json.loads(text)
        assert payload["status"] == "error"
        assert "message" in payload
