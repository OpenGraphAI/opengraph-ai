"""Typer CLI for ingesting images and querying the knowledge graph locally."""

import json
from pathlib import Path

import typer

app = typer.Typer(name="opengraph-image", help="Image knowledge-graph CLI (v0).")


@app.command()
def build(
    folder: str = typer.Argument(..., help="Directory of images to ingest."),
) -> None:
    """Build a knowledge graph from images in FOLDER, writing to FOLDER/opengraph-out/graph.json."""
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
def ingest(
    image_dir: str = typer.Argument(..., help="Directory of images to ingest."),
) -> None:
    """Ingest images from IMAGE_DIR into the knowledge graph."""
    raise NotImplementedError("Not yet implemented.")


@app.command()
def query(
    question: str = typer.Argument(..., help="Natural-language question to answer."),
) -> None:
    """Answer a question over the ingested knowledge graph."""
    raise NotImplementedError("Not yet implemented.")
