"""Command-line interface for opengraph-text."""

import json
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(override=True)  # .env wins over shell env vars

import anthropic
import typer

from .graph import DocumentGraph, build_graph_from_folder
from .query import query_graph
from .render import render_graph_html

app = typer.Typer(help="Build and inspect multi-document knowledge graphs.")

OUTPUT_DIRNAME = "opengraph-out"


@app.command()
def build(folder: Path) -> None:
    """Extract every document in FOLDER and write a linked graph.json and graph.html."""

    output = folder / OUTPUT_DIRNAME / "graph.json"
    build_graph_from_folder(folder, output)
    print(f"Wrote graph to {output}")


@app.command()
def visualize(folder: Path) -> None:
    """Render the graph previously built from FOLDER to an interactive graph.html."""

    graph_path = folder / OUTPUT_DIRNAME / "graph.json"
    if not graph_path.exists():
        raise typer.BadParameter(
            f"No graph found at {graph_path}. Run `opengraph-text build {folder}` first."
        )

    graph = DocumentGraph.from_json(graph_path)
    output = graph_path.parent / "graph.html"
    render_graph_html(graph, output)
    print(f"Wrote graph visualization to {output}")


@app.command()
def summary(folder: Path) -> None:
    """Print summary stats for the graph previously built from FOLDER."""

    graph_path = folder / OUTPUT_DIRNAME / "graph.json"
    if not graph_path.exists():
        raise typer.BadParameter(
            f"No graph found at {graph_path}. Run `opengraph-text build {folder}` first."
        )

    graph = DocumentGraph.from_json(graph_path)
    print(json.dumps(graph.summary(), indent=2))


@app.command()
def query(
    question: str,
    graph: Path = typer.Option(
        None, "--graph", help="Path to graph.json (default ./opengraph-out/graph.json)"
    ),
) -> None:
    """Answer a natural-language QUESTION about a previously built graph."""

    graph_path = graph or Path.cwd() / OUTPUT_DIRNAME / "graph.json"
    if not graph_path.exists():
        raise typer.BadParameter(
            f"No graph found at {graph_path}. Run `opengraph-text build <folder>` first."
        )

    document_graph = DocumentGraph.from_json(graph_path)
    client = anthropic.Anthropic()
    result = query_graph(document_graph, question, client)
    print(result.summary)
