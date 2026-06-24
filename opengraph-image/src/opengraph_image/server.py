"""MCP server exposing image ingestion and graph query as tools.

Built with the official Python MCP SDK's FastMCP API.
https://github.com/modelcontextprotocol/python-sdk
"""

from __future__ import annotations

import json
from pathlib import Path

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(_PROJECT_ROOT / ".env", override=True)

mcp = FastMCP(
    name="opengraph-image",
    instructions="Build and query knowledge graphs from folders of images",
)

_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}


def _error(message: str) -> str:
    return json.dumps({"status": "error", "message": message})


def _resolve_graph_path(graph_path: str) -> Path:
    """Resolve a graph_path argument to a concrete graph.json path.

    - "" defaults to ./opengraph-out/graph.json relative to cwd
    - a path ending in .json is used as-is
    - any other path is treated as a folder containing opengraph-out/graph.json
    """
    if not graph_path:
        return Path.cwd() / "opengraph-out" / "graph.json"
    path = Path(graph_path)
    if path.suffix == ".json":
        return path
    return path / "opengraph-out" / "graph.json"


def _load_graph(graph_path: str):
    from opengraph_image.graph import ImageGraph

    path = _resolve_graph_path(graph_path)
    if not path.exists():
        raise FileNotFoundError(f"Graph not found at {path}. Run build_graph first.")
    return ImageGraph.from_json(path)


@mcp.tool()
def build_graph(folder_path: str) -> str:
    """Build a knowledge graph from all images in folder_path and save it to
    folder_path/opengraph-out/graph.json."""
    try:
        folder = Path(folder_path)
        if not folder.exists() or not folder.is_dir():
            return _error(f"Folder not found: {folder_path}")

        has_images = any(
            f.is_file() and f.suffix.lower() in _IMAGE_EXTENSIONS for f in folder.iterdir()
        )
        if not has_images:
            return _error(f"No image files found in {folder_path}.")

        from opengraph_image.graph import build_graph_from_folder

        output = folder / "opengraph-out" / "graph.json"
        graph = build_graph_from_folder(folder, output)

        return json.dumps(
            {"status": "ok", "graph_path": str(output), "summary": graph.summary()}
        )
    except Exception as e:
        return _error(str(e))


@mcp.tool()
def query_graph(question: str, graph_path: str = "") -> str:
    """Answer a natural-language question over a previously built knowledge graph."""
    try:
        import anthropic

        from opengraph_image.query import query_graph as run_query

        graph = _load_graph(graph_path)
        client = anthropic.Anthropic()
        result = run_query(graph, question, client)
        return result.model_dump_json()
    except Exception as e:
        return _error(str(e))


@mcp.tool()
def get_image_entities(image_filename: str, graph_path: str = "") -> str:
    """Return all entities (with edges) connected to the given image node."""
    try:
        from opengraph_image.query import get_neighbors

        graph = _load_graph(graph_path)
        result = get_neighbors(graph, image_filename)
        return json.dumps({"status": "ok", **result})
    except Exception as e:
        return _error(str(e))


@mcp.tool()
def list_images(graph_path: str = "") -> str:
    """Return the list of image filenames present in the knowledge graph."""
    try:
        graph = _load_graph(graph_path)
        images = graph.summary()["images"]
        return json.dumps({"status": "ok", "images": images})
    except Exception as e:
        return _error(str(e))


@mcp.tool()
def graph_summary(graph_path: str = "") -> str:
    """Return high-level statistics about the knowledge graph."""
    try:
        graph = _load_graph(graph_path)
        return json.dumps({"status": "ok", "summary": graph.summary()})
    except Exception as e:
        return _error(str(e))


def serve() -> None:
    mcp.run(transport="stdio")
