"""MCP server exposing table graph build/query tools."""

from __future__ import annotations

import json
from pathlib import Path

import anthropic
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
load_dotenv(_PROJECT_ROOT / ".env", override=True)
load_dotenv(_PROJECT_ROOT / ".env.local", override=True)

mcp = FastMCP(
    name="opengraph-table",
    instructions="Build and query merged table knowledge graphs",
)

_TABLE_EXTENSIONS = {".tsv", ".csv", ".xlsx", ".xls"}


def _error(message: str) -> str:
    return json.dumps({"status": "error", "message": message})


def _resolve_graph_path(graph_path: str) -> Path:
    if not graph_path:
        return Path.cwd() / "opengraph-out" / "graph.json"
    p = Path(graph_path)
    if p.suffix == ".json":
        return p
    return p / "opengraph-out" / "graph.json"


@mcp.tool()
def build_graph(folder_path: str, output_prefix: str = "") -> str:
    """Build a merged knowledge graph from all table files in folder_path."""
    try:
        from opengraph_table.graph import build_graph_from_tables

        folder = Path(folder_path)
        if not folder.exists() or not folder.is_dir():
            return _error(f"Folder not found: {folder_path}")

        has_tables = any(
            f.is_file() and f.suffix.lower() in _TABLE_EXTENSIONS for f in folder.iterdir()
        )
        if not has_tables:
            return _error(f"No table files found in {folder_path}")

        out_prefix = Path(output_prefix) if output_prefix else folder / "opengraph-out" / "graph"
        graph = build_graph_from_tables(folder, out_prefix, merge=True)

        return json.dumps(
            {
                "status": "ok",
                "graph_path": str(out_prefix.with_suffix(".json")),
                "summary": graph.summary(),
            }
        )
    except Exception as e:
        return _error(str(e))


@mcp.tool()
async def query_graph(question: str, graph_path: str = "") -> str:
    """Answer a natural-language question over a table graph."""
    try:
        from opengraph_table.query import query_graph as query_graph_async

        path = _resolve_graph_path(graph_path)
        if not path.exists():
            return _error(f"Graph not found at {path}. Run build_graph first.")

        client = anthropic.Anthropic()
        result = await query_graph_async(question, path, client)
        return json.dumps({"status": "ok", **result})
    except Exception as e:
        return _error(str(e))


@mcp.tool()
def graph_summary(graph_path: str = "") -> str:
    """Return high-level summary stats for a built graph."""
    try:
        path = _resolve_graph_path(graph_path)
        if not path.exists():
            return _error(f"Graph not found at {path}. Run build_graph first.")

        data = json.loads(path.read_text())
        return json.dumps({"status": "ok", "summary": data.get("metadata", {})})
    except Exception as e:
        return _error(str(e))


@mcp.tool()
def build_graph_from_content(tables: list[dict], output_path: str = "") -> str:
    """Build a knowledge graph from table files dropped directly in the chat.

    Call this when the user pastes or drops CSV/TSV/Excel content into the chat.

    Args:
        tables: List of dicts, each with:
            - "filename": original filename, e.g. "sales.csv"
            - "content":  the raw text content of the file (CSV/TSV rows as a string)
        output_path: Optional path to save graph JSON for later querying
                     (e.g. "/tmp/my_graph.json").  If omitted the graph is
                     returned inline and not persisted.

    Returns:
        JSON with status, summary stats, and the full graph (when not persisted).
    """
    try:
        from opengraph_table.extract import extract_tables_from_content
        from opengraph_table.graph import TableGraph

        if not tables:
            return _error("No tables provided. Pass a list of {filename, content} dicts.")

        client = anthropic.Anthropic()
        graph_json = extract_tables_from_content(tables, client)

        graph = TableGraph()
        graph.add_graph_json(graph_json)
        graph.merge_entities()

        result: dict = {
            "status": "ok",
            "tables_processed": len(tables),
            "filenames": [t.get("filename", "?") for t in tables],
            "summary": graph.summary(),
        }

        if output_path:
            import json as _json
            from pathlib import Path as _Path

            out = _Path(output_path)
            graph.to_json(out)
            result["graph_path"] = str(out)
            result["note"] = "Graph saved. Use query_graph or graph_summary with this path."
        else:
            import json as _json
            import networkx as nx

            result["graph"] = nx.node_link_data(graph._g)

        return json.dumps(result)
    except Exception as e:
        return _error(str(e))


@mcp.tool()
def list_sources(graph_path: str = "") -> str:
    """List source tables represented in the graph."""
    try:
        path = _resolve_graph_path(graph_path)
        if not path.exists():
            return _error(f"Graph not found at {path}. Run build_graph first.")

        data = json.loads(path.read_text())
        sources = data.get("sources", {})
        return json.dumps(
            {
                "status": "ok",
                "source_count": len(sources),
                "sources": list(sources.values()),
            }
        )
    except Exception as e:
        return _error(str(e))


def serve() -> None:
    mcp.run(transport="stdio")
