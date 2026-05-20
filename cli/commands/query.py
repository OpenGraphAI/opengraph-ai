"""Query command (disabled in GCP-only mode)."""

import typer


def query(
    file_path: str = typer.Argument(
        ...,
        help="Path to a text file, or a folder containing CSV tables.",
    ),
    term: str = typer.Argument(
        ...,
        help="Search term, e.g. 'alice'.",
    ),
    exact: bool = typer.Option(
        False,
        "--exact",
        help="Match term exactly against node label or id.",
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
    del file_path, term, exact, output_root, rebuild
    typer.echo(
        "Error: query command is disabled in GCP-only mode. Use graph data from GCP/Neo4j via MCP tools.",
        err=True,
    )
    raise typer.Exit(code=1)
