"""MCP server for OpenGraph Text using FastMCP."""

from __future__ import annotations

from pathlib import Path

import anthropic
from mcp.server.fastmcp import FastMCP

from opengraph_text.extract import extract_document
from opengraph_text.graph import build_graph_from_folder
from opengraph_text.query import query_graph_file

mcp = FastMCP("opengraph-text")


@mcp.tool()
def extract_text_document(document_path: str) -> str:
    """Extract a text knowledge graph from one document."""
    client = anthropic.Anthropic()
    extraction = extract_document(Path(document_path), client)
    return extraction.model_dump_json(indent=2)


@mcp.tool()
def build_text_graph(folder: str, output: str) -> str:
    """Build a text knowledge graph from all .txt and .md files in a folder."""
    graph = build_graph_from_folder(Path(folder), Path(output))
    return graph.summary()


@mcp.tool()
def query_text_graph(graph_path: str, question: str) -> str:
    """Ask a natural-language question over a saved text graph."""
    client = anthropic.Anthropic()
    result = query_graph_file(Path(graph_path), question, client)
    return result.model_dump_json(indent=2)


if __name__ == "__main__":
    mcp.run()