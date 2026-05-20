"""API route definitions.

TODO: Add route modules for extract, graph, and query endpoints.
"""

import os

from pydantic import BaseModel
from fastapi import APIRouter
from fastapi import HTTPException

from engine.config import load_env_config
from engine.connectors.neo4j_aura import export_extraction_from_neo4j
from engine.connectors.neo4j_aura import store_extraction_in_neo4j
from engine.extractors.text_extractor import extract_from_text
from engine.extractors.text_extractor import load_text_source
from engine.extractors.text_extractor import write_extraction_artifacts
from engine.upload.gcp import DEFAULT_GCS_PREFIX
from engine.workflows.graph_from_gcs import DEFAULT_GCS_OUTPUT_PREFIX
from engine.workflows.graph_from_gcs import run_graph_from_gcs_workflow

router = APIRouter()


class GraphFromGcsRequest(BaseModel):
    """Request body for running the graph workflow from a GCS dataset."""

    dataset: str
    bucket: str | None = None
    input_prefix: str = DEFAULT_GCS_PREFIX
    output_prefix: str = DEFAULT_GCS_OUTPUT_PREFIX
    model: str | None = None
    project_id: str | None = None
    schema_view: bool = False


class GraphFromGcsResponse(BaseModel):
    """Response body for the graph workflow."""

    dataset: str
    gcs_input_uri: str
    gcs_json_uri: str
    gcs_png_uri: str
    stored_node_count: int
    stored_edge_count: int
    entity_count: int
    relationship_count: int
    graph_json: dict


class GraphFromGcsFileRequest(BaseModel):
    """Request body for running graph workflow from one GCS text/pdf file."""

    dataset: str
    file_name: str
    bucket: str | None = None
    input_prefix: str = DEFAULT_GCS_PREFIX
    output_prefix: str = DEFAULT_GCS_OUTPUT_PREFIX
    project_id: str | None = None
    model: str | None = None


class GraphFromGcsFileResponse(BaseModel):
    """Response body for GCS file graph workflow."""

    dataset: str
    source_uri: str
    gcs_json_uri: str
    gcs_png_uri: str
    entity_count: int
    relationship_count: int
    graph_json: dict


@router.get("/health", tags=["system"])
def health() -> dict[str, str]:
    """Return health status.

    TODO: Add deep dependency readiness checks.
    """
    return {"status": "ok"}


@router.post("/graph/from-gcs", tags=["graph"], response_model=GraphFromGcsResponse)
def graph_from_gcs(request: GraphFromGcsRequest) -> GraphFromGcsResponse:
    """Run the GCS → LLM → Neo4j → GCS graph workflow for a dataset."""
    try:
        result = run_graph_from_gcs_workflow(
            dataset=request.dataset,
            bucket=request.bucket,
            input_prefix=request.input_prefix,
            output_prefix=request.output_prefix,
            model=request.model,
            project_id=request.project_id,
            schema_view=request.schema_view,
        )
    except (EnvironmentError, RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return GraphFromGcsResponse(**result)


@router.post("/graph/from-gcs-file", tags=["graph"], response_model=GraphFromGcsFileResponse)
def graph_from_gcs_file(request: GraphFromGcsFileRequest) -> GraphFromGcsFileResponse:
    """Run text/pdf graph workflow from one GCS file, store in Neo4j, upload artifacts to GCS."""
    try:
        load_env_config()
        resolved_bucket = request.bucket or os.environ.get("GCS_BUCKET")
        resolved_project = request.project_id or os.environ.get("GCP_PROJECT_ID")
        if not resolved_bucket:
            raise EnvironmentError("GCS_BUCKET is not set. Pass bucket or set env.")

        clean_input = request.input_prefix.strip("/")
        source_uri = (
            f"gs://{resolved_bucket}/{clean_input}/{request.dataset}/{request.file_name}"
            if clean_input
            else f"gs://{resolved_bucket}/{request.dataset}/{request.file_name}"
        )

        text, metadata = load_text_source(source_uri)
        extraction = extract_from_text(text, source_metadata=metadata)

        clean_output = request.output_prefix.strip("/")
        output_base = (
            f"gs://{resolved_bucket}/{clean_output}/{request.dataset}"
            if clean_output
            else f"gs://{resolved_bucket}/{request.dataset}"
        )
        artifacts = write_extraction_artifacts(
            extraction,
            source=source_uri,
            output_gcs_uri=output_base,
            title=f"{request.dataset.replace('-', ' ').replace('+', ' ').title()} Graph",
        )

        store_extraction_in_neo4j(extraction, dataset=request.dataset, clear_existing=True)
        graph_json = export_extraction_from_neo4j(dataset=request.dataset)

        result = {
            "dataset": request.dataset,
            "source_uri": source_uri,
            "gcs_json_uri": str(artifacts["json_path"]),
            "gcs_png_uri": str(artifacts["graph_path"]),
            "entity_count": len(graph_json.get("entities", [])),
            "relationship_count": len(graph_json.get("relationships", [])),
            "graph_json": graph_json,
        }
    except (EnvironmentError, RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return GraphFromGcsFileResponse(**result)
