"""OpenGraph FastMCP server with a compact GCP-centric toolset.

Exposes only four tools:
1) List current data on GCP.
2) Upload dropped Claude files to GCP.
3) Extract graph from GCP data, store in Neo4j, persist artifacts to GCP, and return PNG.
4) Full upload + extract workflow in one call.
"""

from __future__ import annotations

import base64
import os
from pathlib import Path
from typing import Annotated
from typing import Any

from mcp.server.fastmcp import FastMCP
from pydantic import Field

from engine.config import load_env_config
from engine.upload.gcp import download_file_from_gcs
from engine.upload.gcp import upload_file_content_to_gcs
from engine.workflows.cloud_run import run_graph_from_gcs_file_via_cloud_run
from engine.workflows.cloud_run import run_graph_from_gcs_via_cloud_run

mcp = FastMCP("OpenGraphMCP", log_level="ERROR")

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _resolve_gcp(bucket: str | None, project_id: str | None) -> tuple[str, str]:
    load_env_config(search_from=PROJECT_ROOT)
    resolved_bucket = bucket or os.environ.get("GCS_BUCKET")
    resolved_project = project_id or os.environ.get("GCP_PROJECT_ID")
    if not resolved_bucket:
        raise EnvironmentError("Missing GCS_BUCKET. Set it in env or pass bucket.")
    if not resolved_project:
        raise EnvironmentError("Missing GCP_PROJECT_ID. Set it in env or pass project_id.")
    return resolved_bucket, resolved_project


def _classify_file(filename: str) -> str:
    ext = Path(filename).suffix.lower()
    if ext in {".txt", ".md"}:
        return "text"
    if ext == ".pdf":
        return "pdf"
    if ext in {".csv", ".tsv"}:
        return "dataset"
    return "other"


def _list_gcs_objects(bucket_name: str, prefix: str, project_id: str) -> list[dict[str, Any]]:
    try:
        from google.auth.exceptions import DefaultCredentialsError
        from google.cloud import storage
    except ImportError as exc:
        raise RuntimeError(
            "google-cloud-storage is not installed. Install project dependencies first."
        ) from exc

    try:
        client = storage.Client(project=project_id)
    except DefaultCredentialsError as exc:
        raise RuntimeError(
            "GCP credentials not found. Run 'gcloud auth application-default login' "
            "or set GOOGLE_APPLICATION_CREDENTIALS."
        ) from exc

    clean_prefix = prefix.strip("/")
    blobs = client.list_blobs(bucket_name, prefix=f"{clean_prefix}/" if clean_prefix else None)

    results: list[dict[str, Any]] = []
    for blob in blobs:
        if blob.name.endswith("/"):
            continue
        file_type = _classify_file(Path(blob.name).name)
        results.append(
            {
                "name": blob.name,
                "uri": f"gs://{bucket_name}/{blob.name}",
                "size": blob.size,
                "updated": blob.updated.isoformat() if blob.updated else None,
                "type": file_type,
            }
        )
    return results


@mcp.tool(
    name="list_gcp_data",
    description="Return current data on GCP (text, pdf, dataset files) under input/output prefixes.",
)
def list_gcp_data(
    bucket: Annotated[str | None, Field(description="GCS bucket name (defaults to env).")]=None,
    project_id: Annotated[str | None, Field(description="GCP project id (defaults to env).")]=None,
    input_prefix: Annotated[str, Field(description="GCS input prefix.")]="opengraph-ai/input",
    output_prefix: Annotated[str, Field(description="GCS output prefix.")]="opengraph-ai/output",
) -> dict[str, Any]:
    try:
        resolved_bucket, resolved_project = _resolve_gcp(bucket, project_id)
        input_objects = _list_gcs_objects(resolved_bucket, input_prefix, resolved_project)
        output_objects = _list_gcs_objects(resolved_bucket, output_prefix, resolved_project)
        return {
            "ok": True,
            "bucket": resolved_bucket,
            "input_prefix": input_prefix,
            "output_prefix": output_prefix,
            "input_objects": input_objects,
            "output_objects": output_objects,
            "input_count": len(input_objects),
            "output_count": len(output_objects),
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


@mcp.tool(
    name="upload_data_to_gcp",
    description="Upload dropped Claude data (text/pdf/csv) to GCP.",
)
def upload_data_to_gcp(
    dataset_name: Annotated[str, Field(description="Dataset/folder key to store the file under.")],
    filename: Annotated[str, Field(description="Original filename, e.g. report.pdf or table.csv.")],
    file_content_base64: Annotated[str, Field(description="Base64-encoded file content from Claude.")],
    bucket: Annotated[str | None, Field(description="GCS bucket name (defaults to env).")]=None,
    project_id: Annotated[str | None, Field(description="GCP project id (defaults to env).")]=None,
    input_prefix: Annotated[str, Field(description="Base GCS input prefix.")]="opengraph-ai/input",
) -> dict[str, Any]:
    try:
        resolved_bucket, resolved_project = _resolve_gcp(bucket, project_id)
        file_bytes = base64.b64decode(file_content_base64)
        clean_prefix = input_prefix.strip("/")
        blob_name = f"{clean_prefix}/{dataset_name}/{filename}" if clean_prefix else f"{dataset_name}/{filename}"
        gcs_uri = upload_file_content_to_gcs(
            file_bytes,
            filename=filename,
            bucket_name=resolved_bucket,
            blob_name=blob_name,
            project_id=resolved_project,
        )
        return {
            "ok": True,
            "bucket": resolved_bucket,
            "dataset_name": dataset_name,
            "filename": filename,
            "file_type": _classify_file(filename),
            "gcs_uri": gcs_uri,
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


@mcp.tool(
    name="extract_graph_from_gcp",
    description="Extract graph from data already on GCP, save graph to GCP, and return PNG preview for Claude.",
)
def extract_graph_from_gcp(
    dataset_name: Annotated[str, Field(description="Dataset key/folder under GCS input prefix.")],
    data_type: Annotated[str, Field(description="One of: text, pdf, dataset.")],
    filename: Annotated[str | None, Field(description="Required for text/pdf: file name under dataset folder.")]=None,
    bucket: Annotated[str | None, Field(description="GCS bucket name (defaults to env).")]=None,
    project_id: Annotated[str | None, Field(description="GCP project id (defaults to env).")]=None,
    input_prefix: Annotated[str, Field(description="GCS input prefix.")]="opengraph-ai/input",
    output_prefix: Annotated[str, Field(description="GCS output prefix.")]="opengraph-ai/output",
    model: Annotated[str | None, Field(description="Optional LLM model override.")]=None,
    schema_view: Annotated[bool, Field(description="Schema view for dataset graph rendering.")]=False,
    api_url: Annotated[str | None, Field(description="Cloud Run base URL override.")]=None,
) -> dict[str, Any]:
    try:
        resolved_bucket, resolved_project = _resolve_gcp(bucket, project_id)
        kind = data_type.strip().lower()

        if kind == "dataset":
            workflow = run_graph_from_gcs_via_cloud_run(
                dataset=dataset_name,
                bucket=resolved_bucket,
                input_prefix=input_prefix,
                output_prefix=output_prefix,
                project_id=resolved_project,
                model=model,
                schema_view=schema_view,
                api_url=api_url,
            )
            png_bytes = download_file_from_gcs(
                workflow["gcs_png_uri"],
                project_id=resolved_project,
            )
            return {
                "ok": True,
                "mode": "dataset",
                "dataset": dataset_name,
                "gcs_json_uri": workflow["gcs_json_uri"],
                "gcs_png_uri": workflow["gcs_png_uri"],
                "entity_count": workflow["entity_count"],
                "relationship_count": workflow["relationship_count"],
                "png_base64": base64.b64encode(png_bytes).decode("utf-8"),
                "png_mime_type": "image/png",
            }

        if kind not in {"text", "pdf"}:
            raise ValueError("data_type must be one of: text, pdf, dataset")
        if not filename:
            raise ValueError("filename is required for text/pdf extraction")

        workflow = run_graph_from_gcs_file_via_cloud_run(
            dataset=dataset_name,
            file_name=filename,
            bucket=resolved_bucket,
            input_prefix=input_prefix,
            output_prefix=output_prefix,
            project_id=resolved_project,
            model=model,
            api_url=api_url,
        )
        png_bytes = download_file_from_gcs(workflow["gcs_png_uri"], project_id=resolved_project)

        return {
            "ok": True,
            "mode": kind,
            "dataset": dataset_name,
            "source_uri": workflow["source_uri"],
            "gcs_json_uri": workflow["gcs_json_uri"],
            "gcs_png_uri": workflow["gcs_png_uri"],
            "entity_count": workflow["entity_count"],
            "relationship_count": workflow["relationship_count"],
            "png_base64": base64.b64encode(png_bytes).decode("utf-8"),
            "png_mime_type": "image/png",
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc), "dataset": dataset_name}


@mcp.tool(
    name="full_upload_and_extract",
    description="Upload dropped Claude file to GCP, extract graph, save artifacts to GCP, and return PNG in one step.",
)
def full_upload_and_extract(
    dataset_name: Annotated[str, Field(description="Dataset/folder key.")],
    filename: Annotated[str, Field(description="Original filename.")],
    file_content_base64: Annotated[str, Field(description="Base64-encoded file bytes from Claude.")],
    data_type: Annotated[str | None, Field(description="Optional override: text, pdf, dataset.")]=None,
    bucket: Annotated[str | None, Field(description="GCS bucket name (defaults to env).")]=None,
    project_id: Annotated[str | None, Field(description="GCP project id (defaults to env).")]=None,
    input_prefix: Annotated[str, Field(description="GCS input prefix.")]="opengraph-ai/input",
    output_prefix: Annotated[str, Field(description="GCS output prefix.")]="opengraph-ai/output",
    model: Annotated[str | None, Field(description="Optional LLM model override.")]=None,
    schema_view: Annotated[bool, Field(description="Schema view for dataset graph rendering.")]=False,
    api_url: Annotated[str | None, Field(description="Cloud Run base URL override.")]=None,
) -> dict[str, Any]:
    upload_result = upload_data_to_gcp(
        dataset_name=dataset_name,
        filename=filename,
        file_content_base64=file_content_base64,
        bucket=bucket,
        project_id=project_id,
        input_prefix=input_prefix,
    )
    if not upload_result.get("ok"):
        return upload_result

    resolved_type = (data_type or upload_result.get("file_type") or "other").lower()
    extract_result = extract_graph_from_gcp(
        dataset_name=dataset_name,
        data_type=resolved_type,
        filename=filename if resolved_type in {"text", "pdf"} else None,
        bucket=bucket,
        project_id=project_id,
        input_prefix=input_prefix,
        output_prefix=output_prefix,
        model=model,
        schema_view=schema_view,
        api_url=api_url,
    )
    if not extract_result.get("ok"):
        return {
            "ok": False,
            "upload": upload_result,
            "extract": extract_result,
        }

    return {
        "ok": True,
        "upload": upload_result,
        "extract": extract_result,
    }


if __name__ == "__main__":
    mcp.run(transport="stdio")
