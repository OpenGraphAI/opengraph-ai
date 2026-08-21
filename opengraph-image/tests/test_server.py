"""Integration tests for the opengraph-image MCP server, using the MCP SDK's
in-process client/server harness (no subprocess, no real transport)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from mcp.shared.memory import create_connected_server_and_client_session

from opengraph_image.graph import ImageGraph
from opengraph_image.render import render_graph_html
from opengraph_image.server import mcp


@pytest.mark.asyncio
async def test_lists_six_tools() -> None:
    async with create_connected_server_and_client_session(mcp._mcp_server) as session:
        result = await session.list_tools()
        tool_names = {tool.name for tool in result.tools}
        assert tool_names == {
            "build_graph",
            "query_graph",
            "get_image_entities",
            "list_images",
            "graph_summary",
            "build_graph_html",
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


def test_render_graph_html_embeds_node_data(tmp_path: Path) -> None:
    graph = ImageGraph()
    graph._g.add_node("img_1", type="image", path="/photos/dog.jpg", seen_in=["img_1"])
    graph._g.add_node("img_1__dog_1", type="object", label="dog", confidence=0.9, seen_in=["img_1"])
    graph._g.add_edge("img_1", "img_1__dog_1", relation="contains", confidence=0.9)

    output = tmp_path / "graph.html"
    result = render_graph_html(graph, output)

    assert result == output
    assert output.exists()
    html = output.read_text()
    assert "cytoscape" in html.lower()
    assert "img_1__dog_1" in html
    assert '"label": "dog"' in html or '"label":"dog"' in html
