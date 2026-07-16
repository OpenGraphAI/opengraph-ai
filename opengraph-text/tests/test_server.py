"""Integration tests for the opengraph-text MCP server."""

from __future__ import annotations

import json

import pytest
from mcp.shared.memory import create_connected_server_and_client_session

from opengraph_text.server import mcp


@pytest.mark.asyncio
async def test_lists_five_tools() -> None:
    async with create_connected_server_and_client_session(mcp._mcp_server) as session:
        result = await session.list_tools()
        tool_names = {tool.name for tool in result.tools}
        assert tool_names == {
            "build_graph",
            "query_graph",
            "get_document_entities",
            "list_documents",
            "graph_summary",
        }


@pytest.mark.asyncio
async def test_list_documents_missing_graph_returns_well_formed_error() -> None:
    async with create_connected_server_and_client_session(mcp._mcp_server) as session:
        result = await session.call_tool(
            "list_documents", {"graph_path": "/nonexistent/path/graph.json"}
        )

        text = result.content[0].text
        payload = json.loads(text)
        assert payload["status"] == "error"
        assert "message" in payload
