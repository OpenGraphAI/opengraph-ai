"""MCP server for opengraph-text."""

from __future__ import annotations

import json
from pathlib import Path

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

load_dotenv(override=True)

mcp = FastMCP(
    name="opengraph-text",
    instructions="Build and query knowledge graphs from folders of text documents (.txt, .md, .pdf)",
)

_TEXT_EXTENSIONS = {".txt", ".md", ".pdf"}


def _error(message: str) -> str:
    return json.dumps({"status": "error", "message": message})


def _resolve_graph_path(graph_path: str) -> Path:
    if not graph_path:
        return Path.cwd() / "opengraph-out" / "graph.json"
    path = Path(graph_path)
    if path.suffix == ".json":
        return path
    return path / "opengraph-out" / "graph.json"


def _load_graph(graph_path: str):
    from opengraph_text.graph import DocumentGraph

    path = _resolve_graph_path(graph_path)
    if not path.exists():
        raise FileNotFoundError(f"Graph not found at {path}. Run build_graph first.")
    return DocumentGraph.from_json(path)


@mcp.tool()
def build_graph(folder_path: str) -> str:
    """Build a knowledge graph from all supported documents in folder_path."""
    try:
        from opengraph_text.graph import build_graph_from_folder

        folder = Path(folder_path)
        if not folder.exists() or not folder.is_dir():
            return _error(f"Folder not found: {folder_path}")

        has_documents = any(
            f.is_file() and f.suffix.lower() in _TEXT_EXTENSIONS for f in folder.iterdir()
        )
        if not has_documents:
            return _error(
                f"No text documents (.txt, .md, .pdf) found in {folder_path}."
            )

        output = folder / "opengraph-out" / "graph.json"
        graph = build_graph_from_folder(folder, output)
        return json.dumps(
            {
                "status": "ok",
                "graph_path": str(output),
                "summary": graph.summary(),
            }
        )
    except Exception as e:
        return _error(str(e))


@mcp.tool()
def query_graph(question: str, graph_path: str = "") -> str:
    """Answer a natural-language question over a previously built text graph."""
    try:
        import anthropic

        from opengraph_text.query import query_graph as run_query

        graph = _load_graph(graph_path)
        client = anthropic.Anthropic()
        result = run_query(graph, question, client)
        return json.dumps({"status": "ok", **result.model_dump()})
    except Exception as e:
        return _error(str(e))


@mcp.tool()
def get_document_entities(document_filename: str, graph_path: str = "") -> str:
    """Return all entities and edges connected to the given document node."""
    try:
        import networkx as nx

        graph = _load_graph(graph_path)
        document_filename = Path(document_filename).name

        document_node_id = None
        for node_id, attrs in graph.graph.nodes(data=True):
            if attrs.get("type") != "document":
                continue
            if Path(attrs.get("path", "")).name == document_filename:
                document_node_id = node_id
                break
            if node_id == Path(document_filename).stem:
                document_node_id = node_id
                break

        if document_node_id is None:
            return _error(
                f"Document not found in graph: {document_filename}."
            )

        ego = nx.ego_graph(graph.graph, document_node_id, radius=1, undirected=True)
        nodes = [
            {"id": node_id, **attrs} for node_id, attrs in ego.nodes(data=True)
        ]
        edges = [
            {"source": u, "target": v, **data}
            for u, v, data in ego.edges(data=True)
        ]

        return json.dumps(
            {
                "status": "ok",
                "document": document_filename,
                "nodes": nodes,
                "edges": edges,
            }
        )
    except Exception as e:
        return _error(str(e))


@mcp.tool()
def list_documents(graph_path: str = "") -> str:
    """Return the list of document filenames present in the graph."""
    try:
        graph = _load_graph(graph_path)
        documents = [
            Path(attrs.get("path", "")).name
            for _node_id, attrs in graph.graph.nodes(data=True)
            if attrs.get("type") == "document"
        ]
        return json.dumps({"status": "ok", "documents": sorted(documents)})
    except Exception as e:
        return _error(str(e))


@mcp.tool()
def graph_summary(graph_path: str = "") -> str:
    """Return high-level summary stats for a built graph."""
    try:
        graph = _load_graph(graph_path)
        return json.dumps({"status": "ok", "summary": graph.summary()})
    except Exception as e:
        return _error(str(e))


def serve() -> None:
    mcp.run(transport="stdio")


def main() -> None:
    serve()


if __name__ == "__main__":
    main()