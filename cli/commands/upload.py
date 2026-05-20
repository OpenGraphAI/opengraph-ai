import os
from pathlib import Path

import typer

from engine.config import load_env_config
from engine.upload.gcp import DEFAULT_GCS_PREFIX
from engine.upload.gcp import upload_file_content_to_gcs


def upload(
    file_path: str = typer.Argument(..., help="Local file path to upload."),
    dataset_name: str = typer.Argument(..., help="Dataset key/folder in GCS."),
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
    prefix: str = typer.Option(
        DEFAULT_GCS_PREFIX,
        "--prefix",
        help="Base GCS prefix for uploaded files.",
    ),
    filename: str | None = typer.Option(
        None,
        "--filename",
        help="Optional filename override in GCS.",
    ),
) -> None:
    """Upload one local file to GCS for a dataset.

    Destination pattern:
    gs://<bucket>/<prefix>/<dataset_name>/<filename>
    """
    load_env_config()

    src = Path(file_path).expanduser()
    if not src.exists() or not src.is_file():
        typer.echo(f"Error: file not found: {src}", err=True)
        raise typer.Exit(code=1)

    resolved_bucket = bucket or os.environ.get("GCS_BUCKET")
    resolved_project = project_id or os.environ.get("GCP_PROJECT_ID")
    if not resolved_bucket:
        typer.echo("Error: missing GCS_BUCKET. Set env or pass --bucket.", err=True)
        raise typer.Exit(code=1)
    if not resolved_project:
        typer.echo("Error: missing GCP_PROJECT_ID. Set env or pass --project-id.", err=True)
        raise typer.Exit(code=1)

    target_name = filename or src.name
    clean_prefix = prefix.strip("/")
    blob_name = f"{clean_prefix}/{dataset_name}/{target_name}" if clean_prefix else f"{dataset_name}/{target_name}"

    try:
        gcs_uri = upload_file_content_to_gcs(
            src.read_bytes(),
            filename=target_name,
            bucket_name=resolved_bucket,
            blob_name=blob_name,
            project_id=resolved_project,
        )
    except Exception as exc:
        typer.echo(f"Upload failed: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    typer.echo(f"Uploaded: {src}")
    typer.echo(f"GCS URI:  {gcs_uri}")