"""Typer CLI for ingesting images and querying the knowledge graph locally."""

import json
from pathlib import Path

import typer
from dotenv import load_dotenv

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
load_dotenv(_PROJECT_ROOT / ".env", override=True)

app = typer.Typer(name="opengraph-image", help="Image knowledge-graph CLI (v0).")


@app.command()
def build(
    folder: str = typer.Argument(..., help="Directory of images to ingest."),
) -> None:
    """Build a knowledge graph from images in FOLDER, writing FOLDER/opengraph-out/graph.json
    and FOLDER/opengraph-out/graph.html."""
    from opengraph_image.graph import build_graph_from_folder

    folder_path = Path(folder)
    output = folder_path / "opengraph-out" / "graph.json"
    build_graph_from_folder(folder_path, output)


@app.command()
def summary(
    folder: str = typer.Argument(..., help="Folder containing opengraph-out/graph.json."),
) -> None:
    """Print a summary of the knowledge graph stored under FOLDER/opengraph-out/graph.json."""
    from opengraph_image.graph import ImageGraph

    graph_path = Path(folder) / "opengraph-out" / "graph.json"
    if not graph_path.exists():
        typer.echo(f"Graph not found at {graph_path}. Run 'build' first.", err=True)
        raise typer.Exit(1)

    graph = ImageGraph.from_json(graph_path)
    typer.echo(json.dumps(graph.summary(), indent=2))



@app.command()
def visualize(
    folder: str = typer.Argument(..., help="Folder containing opengraph-out/graph.json."),
) -> None:
    """Render FOLDER/opengraph-out/graph.json to an interactive FOLDER/opengraph-out/graph.html."""
    from opengraph_image.graph import ImageGraph
    from opengraph_image.render import render_graph_html

    graph_path = Path(folder) / "opengraph-out" / "graph.json"
    if not graph_path.exists():
        typer.echo(f"Graph not found at {graph_path}. Run 'build' first.", err=True)
        raise typer.Exit(1)

    graph = ImageGraph.from_json(graph_path)
    output = graph_path.parent / "graph.html"
    render_graph_html(graph, output)
    typer.echo(f"Graph visualization saved to {output}")


@app.command()
def query(
    question: str = typer.Argument(..., help="Natural-language question to answer."),
    graph: str = typer.Option("./opengraph-out/graph.json", "--graph", help="Path to graph.json."),
) -> None:
    """Answer a question over the ingested knowledge graph."""
    import anthropic

    from opengraph_image.graph import ImageGraph
    from opengraph_image.query import query_graph

    graph_path = Path(graph)
    if not graph_path.exists():
        typer.echo(f"Graph not found at {graph_path}. Run 'build' first.", err=True)
        raise typer.Exit(1)

    image_graph = ImageGraph.from_json(graph_path)
    client = anthropic.Anthropic()
    result = query_graph(image_graph, question, client)
    typer.echo(result.summary)
