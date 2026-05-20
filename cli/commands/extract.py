"""CLI extract subcommands for OpenGraph AI (Cloud Run execution mode)."""

import typer

from engine.upload.gcp import DEFAULT_GCS_PREFIX
from engine.workflows.cloud_run import run_graph_from_gcs_file_via_cloud_run
from engine.workflows.cloud_run import run_graph_from_gcs_via_cloud_run
from engine.workflows.graph_from_gcs import DEFAULT_GCS_OUTPUT_PREFIX

app = typer.Typer(help="Extract graph structures from GCP data sources via Cloud Run API.")


def _parse_gcs_uri(uri: str) -> tuple[str, str]:
    if not uri.startswith("gs://"):
        raise ValueError("Expected gs:// URI")
    path = uri[5:]
    bucket, _, key = path.partition("/")
    if not bucket or not key:
        raise ValueError("Invalid gs:// URI")
    return bucket, key


@app.command("text")
def extract_text(
    gcs_file_uri: str = typer.Argument(
        ...,
        help="GCS file URI for text or PDF input (for example: gs://bucket/opengraph-ai/input/dataset/file.pdf).",
    ),
    output_gcs_uri: str = typer.Option(
        ...,
        "--output-gcs-uri",
        help="GCS destination base URI (for example: gs://bucket/opengraph-ai/output/dataset).",
    ),
    project_id: str | None = typer.Option(
        None,
        "--project-id",
        help="GCP project id override.",
    ),
    model: str | None = typer.Option(
        None,
        "--model",
        help="Optional LLM model override.",
    ),
    api_url: str | None = typer.Option(
        None,
        "--api-url",
        help="Cloud Run base URL. Defaults to OPENGRAPH_API_URL from env.",
    ),
) -> None:
    """Extract entities and relationships by invoking Cloud Run API for one GCS text/PDF file."""
    try:
        source_bucket, source_key = _parse_gcs_uri(gcs_file_uri)
        output_bucket, output_key = _parse_gcs_uri(output_gcs_uri)
    except ValueError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    parts = source_key.split("/")
    if len(parts) < 3:
        typer.echo(
            "Error: gcs_file_uri must include input prefix, dataset, and file name.",
            err=True,
        )
        raise typer.Exit(code=1)

    file_name = parts[-1]
    dataset = parts[-2]
    input_prefix = "/".join(parts[:-2])

    out_parts = output_key.split("/")
    if len(out_parts) < 2:
        typer.echo(
            "Error: output_gcs_uri must include output prefix and dataset folder.",
            err=True,
        )
        raise typer.Exit(code=1)
    output_prefix = "/".join(out_parts[:-1])

    if source_bucket != output_bucket:
        typer.echo(
            "Warning: source and output buckets differ; using source bucket for processing.",
            err=True,
        )

    try:
        result = run_graph_from_gcs_file_via_cloud_run(
            dataset=dataset,
            file_name=file_name,
            bucket=source_bucket,
            input_prefix=input_prefix,
            output_prefix=output_prefix,
            project_id=project_id,
            model=model,
            api_url=api_url,
        )
    except (EnvironmentError, RuntimeError, ValueError) as exc:
        typer.echo(f"Extraction failed: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    typer.echo("Extraction complete via Cloud Run:")
    typer.echo(f"  - Source:   {result['source_uri']}")
    typer.echo(f"  - GCS JSON: {result['gcs_json_uri']}")
    typer.echo(f"  - GCS PNG:  {result['gcs_png_uri']}")
    typer.echo(f"  - Entities: {result['entity_count']}")
    typer.echo(f"  - Relationships: {result['relationship_count']}")


@app.command("tables-gcs")
def extract_tables_gcs(
    dataset_name: str = typer.Argument(
        ...,
        help="Dataset folder name already present in GCS under gcs-prefix.",
    ),
    bucket: str | None = typer.Option(
        None,
        "--bucket",
        help="GCS bucket name (defaults to GCS_BUCKET from env).",
    ),
    project_id: str | None = typer.Option(
        None,
        "--project-id",
        help="GCP project id (defaults to GCP_PROJECT_ID from env).",
    ),
    gcs_prefix: str = typer.Option(
        DEFAULT_GCS_PREFIX,
        "--gcs-prefix",
        help="Base GCS prefix that contains dataset folders.",
    ),
    output_prefix: str = typer.Option(
        DEFAULT_GCS_OUTPUT_PREFIX,
        "--output-prefix",
        help="Base GCS prefix used for graph artifacts.",
    ),
    model: str | None = typer.Option(
        None,
        "--model",
        help="Optional LLM model override for table extraction.",
    ),
    schema_view: bool = typer.Option(
        False,
        "--schema-view",
        help="Render schema/entity-type graph view.",
    ),
    api_url: str | None = typer.Option(
        None,
        "--api-url",
        help="Cloud Run base URL. Defaults to OPENGRAPH_API_URL from env.",
    ),
) -> None:
    """Run table graph extraction via Cloud Run API and write artifacts to GCS."""
    try:
        result = run_graph_from_gcs_via_cloud_run(
            dataset=dataset_name,
            bucket=bucket,
            input_prefix=gcs_prefix,
            output_prefix=output_prefix,
            model=model,
            project_id=project_id,
            schema_view=schema_view,
            api_url=api_url,
        )
    except (EnvironmentError, RuntimeError, ValueError) as exc:
        typer.echo(f"Extraction failed: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    typer.echo("Extraction complete via Cloud Run:")
    typer.echo(f"  - GCS input: {result['gcs_input_uri']}")
    typer.echo(f"  - GCS JSON:  {result['gcs_json_uri']}")
    typer.echo(f"  - GCS PNG:   {result['gcs_png_uri']}")
    typer.echo(f"  - Entities: {result['entity_count']}")
    typer.echo(f"  - Relationships: {result['relationship_count']}")
