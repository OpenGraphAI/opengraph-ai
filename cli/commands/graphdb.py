"""Graph database subcommands for Neo4j AuraDB integration."""

from __future__ import annotations

import json
import re
from pathlib import Path

import typer

from engine.connectors.neo4j_aura import export_extraction_from_neo4j
from engine.connectors.neo4j_aura import store_extraction_in_neo4j
from engine.graphs.builder import build_graph_from_extraction
from engine.graphs.visualize import visualize_graph
from engine.graphs.visualize import visualize_schema_graph
from engine.upload.gcp import DEFAULT_GCS_PREFIX
from engine.workflows.cloud_run import run_graph_from_gcs_via_cloud_run
from engine.workflows.graph_from_gcs import DEFAULT_GCS_OUTPUT_PREFIX
from engine.workflows.graph_from_gcs import resolve_output_json_path

app = typer.Typer(help="Store and retrieve extraction graphs from Neo4j AuraDB.")


def _dataset_name_from_json_path(path: Path) -> str:
    """Derive a stable dataset key from a graph JSON path."""
    base = path.parent.name if path.name == "graph.json" else path.stem
    normalized = re.sub(r"[^a-zA-Z0-9._-]+", "-", base).strip("-._")
    return normalized or "dataset"


@app.command("push")
def push(
    graph_json: str = typer.Argument(
        ..., help="Path to extraction graph JSON with entities/relationships keys."
    ),
    dataset: str | None = typer.Option(
        None,
        "--dataset",
        help="Dataset namespace in Neo4j (default derived from graph_json path).",
    ),
    clear_existing: bool = typer.Option(
        True,
        "--clear-existing/--append",
        help="Clear existing records for this dataset before upload (default: clear).",
    ),
) -> None:
    """Deprecated in GCP-only mode."""
    typer.echo(
        "Error: graphdb push is disabled in GCP-only mode. Use graphdb from-gcs.",
        err=True,
    )
    raise typer.Exit(code=1)


@app.command("pull")
def pull(
    dataset: str = typer.Argument(..., help="Dataset namespace to export from Neo4j."),
    output: str = typer.Option(
        "./output/graph.json",
        "--output",
        "-o",
        help="Destination file for exported graph JSON.",
    ),
    graph_output: str | None = typer.Option(
        None,
        "--graph-output",
        help="Destination PNG path for rendered graph (default: <json_dir>/graph.png).",
    ),
    schema_view: bool = typer.Option(
        False,
        "--schema-view",
        help="Render schema/entity-type graph view instead of full row-level graph.",
    ),
    title: str | None = typer.Option(
        None,
        "--title",
        help="Optional graph title for rendered PNG.",
    ),
) -> None:
    """Deprecated in GCP-only mode."""
    typer.echo(
        "Error: graphdb pull is disabled in GCP-only mode. Use graphdb from-gcs.",
        err=True,
    )
    raise typer.Exit(code=1)


@app.command("from-gcs")
def from_gcs(
    dataset: str = typer.Argument(..., help="Dataset folder name already uploaded to GCS."),
    bucket: str | None = typer.Option(
        None,
        "--bucket",
        help="GCS bucket name (defaults to GCS_BUCKET from env).",
    ),
    input_prefix: str = typer.Option(
        DEFAULT_GCS_PREFIX,
        "--input-prefix",
        help="Base GCS input prefix containing uploaded dataset folders.",
    ),
    output_prefix: str = typer.Option(
        DEFAULT_GCS_OUTPUT_PREFIX,
        "--output-prefix",
        help="Base GCS output prefix for graph artifacts.",
    ),
    model: str | None = typer.Option(
        None,
        "--model",
        help="Optional LLM model override for extraction.",
    ),
    project_id: str | None = typer.Option(
        None,
        "--project-id",
        help="GCP project id (defaults to GCP_PROJECT_ID from env).",
    ),
    schema_view: bool = typer.Option(
        False,
        "--schema-view",
        help="Render schema/entity-type graph view instead of full row-level graph.",
    ),
    api_url: str | None = typer.Option(
        None,
        "--api-url",
        help="Cloud Run base URL. Defaults to OPENGRAPH_API_URL from env.",
    ),
    print_json: bool = typer.Option(
        True,
        "--print-json/--no-print-json",
        help="Print final Neo4j-exported graph JSON in CLI output.",
    ),
) -> None:
    """Create graph from GCS dataset by invoking the Cloud Run graph API."""
    try:
        result = run_graph_from_gcs_via_cloud_run(
            dataset=dataset,
            bucket=bucket,
            input_prefix=input_prefix,
            output_prefix=output_prefix,
            model=model,
            project_id=project_id,
            schema_view=schema_view,
            api_url=api_url,
        )
    except (EnvironmentError, RuntimeError, ValueError) as exc:
        typer.echo(f"Workflow failed: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    typer.echo(f"Workflow complete for dataset '{dataset}'")
    typer.echo(f"  - GCS input:  {result['gcs_input_uri']}")
    typer.echo(f"  - Neo4j stored nodes: {result['stored_node_count']}")
    typer.echo(f"  - Neo4j stored edges: {result['stored_edge_count']}")
    typer.echo(f"  - GCS JSON:   {result['gcs_json_uri']}")
    typer.echo(f"  - GCS PNG:    {result['gcs_png_uri']}")
    typer.echo(f"  - Entities: {result['entity_count']}")
    typer.echo(f"  - Relationships: {result['relationship_count']}")

    if print_json:
        typer.echo("\nNeo4j graph JSON:")
        typer.echo(json.dumps(result["graph_json"], indent=2))
