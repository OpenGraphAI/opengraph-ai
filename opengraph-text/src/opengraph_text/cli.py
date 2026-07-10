"""Command-line interface for opengraph-text."""

import json
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(override=True)  # .env wins over shell env vars

import typer

from .graph import DocumentGraph, build_graph_from_folder

app = typer.Typer(help="Build and inspect multi-document knowledge graphs.")

OUTPUT_DIRNAME = "opengraph-out"


@app.command()
def build(folder: Path) -> None:
    """Extract every document in FOLDER and write a linked graph.json."""

    output = folder / OUTPUT_DIRNAME / "graph.json"
    build_graph_from_folder(folder, output)
    print(f"Wrote graph to {output}")


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
