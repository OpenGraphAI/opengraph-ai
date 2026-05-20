"""Visualize command (disabled in GCP-only mode)."""

import typer


def visualize(
    file_path: str = typer.Argument(
        ...,
        help="Path to a text file, or a folder containing CSV tables.",
    ),
    output: str = typer.Option(
        "./output/graph.png",
        "--output",
        "-o",
        help="Destination image path (default: ./output/graph.png).",
    ),
    title: str | None = typer.Option(
        None,
        "--title",
        help="Optional chart title.",
    ),
    schema_view: bool = typer.Option(
        False,
        "--schema-view",
        help="Render a high-level entity/table graph instead of every row-level node.",
    ),
    output_root: str = typer.Option(
        "./output",
        "--output-root",
        help="Root folder containing saved dataset graph JSON files.",
    ),
    rebuild: bool = typer.Option(
        False,
        "--rebuild",
        help="Rebuild graph from source files instead of loading from output folder.",
    ),
) -> None:
    """Deprecated in GCP-only mode."""
    del file_path, output, title, schema_view, output_root, rebuild
    typer.echo(
        "Error: visualize command is disabled in GCP-only mode. Use MCP extraction tools that return PNG.",
        err=True,
    )
    raise typer.Exit(code=1)
