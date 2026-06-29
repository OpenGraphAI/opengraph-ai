"""MCP server for opengraph-table."""

from __future__ import annotations

from pathlib import Path
from typing import Any


def serve() -> None:
    """Start the MCP server for table graph operations.

    This server exposes table extraction and graph operations as MCP tools.
    """
    # Stub implementation - full MCP integration to be added
    print("OpenGraph Table MCP Server")
    print("Not yet implemented - use CLI instead")
    print("")
    print("Available commands:")
    print("  opengraph-table build <folder>")
    print("  opengraph-table summary <graph_path>")
    print("  opengraph-table query <graph_path> --question '<q>'")
    print("  opengraph-table ingest <folder> --graph <graph_path>")


# Placeholder for future MCP tool definitions
class TableGraphTools:
    """MCP tools for table graph operations."""

    @staticmethod
    def extract_table_tool(table_path: str, table_index: int = 0) -> dict[str, Any]:
        """Extract entities from a single table."""
        from pathlib import Path

        import anthropic

        from opengraph_table.extract import extract_table

        client = anthropic.Anthropic()
        extraction = extract_table(Path(table_path), client, table_index=table_index)
        return extraction.model_dump()

    @staticmethod
    def build_graph_tool(folder: str, output_prefix: str | None = None) -> dict[str, Any]:
        """Build knowledge graph from tables in folder."""
        from pathlib import Path

        from opengraph_table.graph import build_graph_from_tables

        folder_path = Path(folder)
        output_path = Path(output_prefix) if output_prefix else folder_path / "opengraph-out" / "graph"
        graph = build_graph_from_tables(folder_path, output_path)
        return graph.summary()

    @staticmethod
    def query_graph_tool(graph_path: str, question: str) -> dict[str, Any]:
        """Query a knowledge graph with natural language."""
        from pathlib import Path

        from opengraph_table.query import query_sync

        return query_sync(question, Path(graph_path))
