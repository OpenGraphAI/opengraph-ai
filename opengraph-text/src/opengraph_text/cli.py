"""Typer CLI for building and inspecting the text knowledge graph."""

import json
from pathlib import Path

import typer
from dotenv import load_dotenv

load_dotenv(override=True)

app = typer.Typer(name="opengraph-text", help="Text knowledge-graph CLI (v0).")


@app.command()
def build(
    folder: str = typer.Argument(..., help="Directory of documents to ingest."),
) -> None:
    """Build a knowledge graph from documents in FOLDER, writing to FOLDER/opengraph-out/graph.json."""
    from opengraph_text.graph import build_graph_from_folder

    folder_path = Path(folder)
    output = folder_path / "opengraph-out" / "graph.json"
    build_graph_from_folder(folder_path, output)


@app.command()
def summary(
    folder: str = typer.Argument(..., help="Folder containing opengraph-out/graph.json."),
) -> None:
    """Print a summary of the knowledge graph stored under FOLDER/opengraph-out/graph.json."""
    from opengraph_text.graph import DocumentGraph

    graph_path = Path(folder) / "opengraph-out" / "graph.json"
    if not graph_path.exists():
        typer.echo(f"Graph not found at {graph_path}. Run 'build' first.", err=True)
        raise typer.Exit(1)

    graph = DocumentGraph.from_json(graph_path)
    typer.echo(json.dumps(graph.summary(), indent=2))


@app.command()
def query(
    question: str = typer.Argument(..., help="Natural-language question to answer."),
    graph: str = typer.Option("./opengraph-out/graph.json", "--graph", help="Path to graph.json."),
) -> None:
    """Answer a question over the ingested knowledge graph."""
    import anthropic

    from opengraph_text.graph import DocumentGraph
    from opengraph_text.query import query_graph

    graph_path = Path(graph)
    if not graph_path.exists():
        typer.echo(f"Graph not found at {graph_path}. Run 'build' first.", err=True)
        raise typer.Exit(1)

    document_graph = DocumentGraph.from_json(graph_path)
    client = anthropic.Anthropic()
    result = query_graph(document_graph, question, client)
    typer.echo(result.summary)
