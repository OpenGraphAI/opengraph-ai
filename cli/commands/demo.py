"""Demo command (disabled in GCP-only mode)."""

import typer


def demo(
    file_path: str = typer.Argument(
        ...,
        help="Path to a text file, or a folder containing CSV tables.",
    ),
    output: str = typer.Option(
        "./output/graph.json",
        "--output",
        "-o",
        help="Destination file for graph JSON (default: ./output/graph.json).",
    ),
    llm: bool = typer.Option(
        False,
        "--llm",
        help="Use LLM-backed extraction for table folders (requires OPENAI_API_KEY).",
    ),
) -> None:
    """Deprecated in GCP-only mode."""
    del file_path, output, llm
    typer.echo(
        "Error: demo command is disabled in GCP-only mode. Use MCP workflow tools.",
        err=True,
    )
    raise typer.Exit(code=1)
