"""Typer CLI for ingesting images and querying the knowledge graph locally."""

import typer

app = typer.Typer(name="opengraph-image", help="Image knowledge-graph CLI (v0).")


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
