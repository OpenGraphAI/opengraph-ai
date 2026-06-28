"""Command-line interface for opengraph-table."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

from opengraph_table.graph import TableGraph, build_graph_from_tables
from opengraph_table.query import query_sync

console = Console()
app = typer.Typer(help="Build and query knowledge graphs from tables.")


@app.command()
def build(
    folder: Path = typer.Argument(
        ..., help="Folder containing table files to extract"
    ),
    output: Optional[Path] = typer.Option(
        None,
        help="Output prefix for graph files (default: folder/opengraph-out/graph)",
    ),
) -> None:
    """Send all tables to Claude at once and build the knowledge graph.

    Example:
        opengraph-table build /path/to/tables/
    """
    try:
        if output is None:
            output = folder / "opengraph-out" / "graph"

        output_parent = output.parent
        output_parent.mkdir(parents=True, exist_ok=True)

        console.print(
            f"[bold blue]Building graph from tables in {folder}[/bold blue]"
        )
        graph = build_graph_from_tables(folder, output, merge=True)
        console.print("[bold green]✓ Graph built successfully[/bold green]")
        console.print(json.dumps(graph.summary(), indent=2))

    except ValueError as e:
        console.print(f"[bold red]Error: {e}[/bold red]")
        raise typer.Exit(code=1)
    except Exception as e:
        console.print(f"[bold red]Unexpected error: {e}[/bold red]")
        raise typer.Exit(code=1)


@app.command()
def summary(
    graph_path: Path = typer.Argument(
        ..., help="Path to graph.json file"
    ),
) -> None:
    """Print graph statistics.

    Example:
        opengraph-table summary /path/to/graph.json
    """
    try:
        if not graph_path.exists():
            console.print(f"[bold red]Graph file not found: {graph_path}[/bold red]")
            raise typer.Exit(code=1)

        data = json.loads(graph_path.read_text())
        metadata = data.get("metadata", {})

        console.print("\n[bold blue]Graph Summary[/bold blue]")
        console.print(f"Total Nodes: {metadata.get('total_nodes', 0)}")
        console.print(f"Total Edges: {metadata.get('total_edges', 0)}")
        console.print(f"Sources: {metadata.get('sources', 0)}")

        console.print("\n[bold]Node Types[/bold]")
        for ntype, count in metadata.get("node_count_by_type", {}).items():
            console.print(f"  {ntype}: {count}")

        console.print("\n[bold]Relations[/bold]")
        for rel, count in metadata.get("relation_count", {}).items():
            console.print(f"  {rel}: {count}")

        console.print("\n[bold]Top Nodes (by degree)[/bold]")
        for node in metadata.get("top_nodes", [])[:10]:
            console.print(f"  {node['id']}: {node['degree']}")

    except Exception as e:
        console.print(f"[bold red]Error: {e}[/bold red]")
        raise typer.Exit(code=1)


@app.command()
def query(
    graph_path: Path = typer.Argument(
        ..., help="Path to graph.json file"
    ),
    question: str = typer.Option(
        ..., "--question", "-q", help="Question to ask about the graph"
    ),
) -> None:
    """Query the knowledge graph with natural language.

    Example:
        opengraph-table query /path/to/graph.json --question "What are the main entities?"
    """
    try:
        if not graph_path.exists():
            console.print(f"[bold red]Graph file not found: {graph_path}[/bold red]")
            raise typer.Exit(code=1)

        console.print(f"[bold blue]Querying graph with: '{question}'[/bold blue]\n")
        result = query_sync(question, graph_path)

        console.print("[bold]Answer:[/bold]")
        console.print(result["answer"])

        console.print(f"\n[dim]Sources: {', '.join(result['sources'])}")
        console.print(f"Graph size: {result['graph_nodes']} nodes, {result['graph_edges']} edges[/dim]")

    except Exception as e:
        console.print(f"[bold red]Error: {e}[/bold red]")
        raise typer.Exit(code=1)


@app.command()
def ingest(
    folder: Path = typer.Argument(
        ..., help="Folder with new table files to ingest"
    ),
    graph_path: Path = typer.Option(
        ..., "--graph", "-g", help="Path to existing graph.json file"
    ),
) -> None:
    """Incrementally ingest new tables into existing graph.

    Example:
        opengraph-table ingest /path/to/new/tables --graph /path/to/graph.json
    """
    try:
        if not graph_path.exists():
            console.print(f"[bold red]Graph file not found: {graph_path}[/bold red]")
            raise typer.Exit(code=1)

        import anthropic

        console.print(f"[bold blue]Ingesting tables from {folder}[/bold blue]")

        # Load existing graph
        graph = TableGraph()
        graph.load(graph_path)

        # Extract new tables
        table_extensions = {".tsv", ".csv", ".xlsx", ".xls"}
        table_files = sorted(
            f for f in folder.iterdir()
            if f.is_file() and f.suffix.lower() in table_extensions
        )

        if not table_files:
            console.print(f"[bold yellow]No table files found in {folder}[/bold yellow]")
            raise typer.Exit(code=0)

        client = anthropic.Anthropic()

        from opengraph_table.extract import extract_tables_llm_graph_json

        graph_json = extract_tables_llm_graph_json(table_files, client)
        graph.add_graph_json(graph_json)

        # Merge and save
        stats = graph.merge_entities()
        console.print(f"[bold green]Merging stats: {stats}[/bold green]")

        graph.to_json(graph_path)

        console.print("[bold green]✓ Graph updated[/bold green]")
        console.print(json.dumps(graph.summary(), indent=2))

    except Exception as e:
        console.print(f"[bold red]Error: {e}[/bold red]")
        raise typer.Exit(code=1)


def main() -> None:
    """Entry point for CLI."""
    app()
