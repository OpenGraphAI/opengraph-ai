"""Text extraction helpers for OpenGraph AI.

Two modes:
- extract_from_text_offline: regex heuristics, no API key needed (demo / tests).
- extract_from_text: LLM-backed pipeline with chunking, retries, and artifact export.

TODO: Replace heuristics with production NLP pipelines.
"""

from __future__ import annotations

import importlib
import json
import logging
import re
from collections.abc import Callable
from io import BytesIO
from pathlib import Path
from typing import Any

PdfReader: Any | None = None

from engine.config import get_optional_env
from engine.graphs.builder import build_graph_from_extraction
from engine.graphs.visualize import visualize_graph
from engine.llm.provider import call_llm
from engine.upload.gcp import download_file_from_gcs
from engine.upload.gcp import upload_file_to_gcs

logger = logging.getLogger(__name__)

_DEFAULT_CHUNK_SIZE = 3500
_DEFAULT_CHUNK_OVERLAP = 250
_DEFAULT_MAX_RETRIES = 3


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------

def extract_text(raw_text: str) -> list[str]:
    """Return non-empty stripped lines from raw text.

    TODO: Implement semantic chunking and metadata enrichment.
    """
    return [line.strip() for line in raw_text.splitlines() if line.strip()]


def _slug(value: str) -> str:
    """Return a stable identifier slug for extracted entities."""
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "entity"


def _dataset_name(source: Path) -> str:
    """Return dataset name derived from a file path."""
    normalized = re.sub(r"[^a-zA-Z0-9._-]+", "-", source.stem).strip("-._")
    return normalized or "dataset"


# ---------------------------------------------------------------------------
# Input loading
# ---------------------------------------------------------------------------

def _read_text_file(path: Path) -> str:
    """Read a UTF-8 text file into memory."""
    return path.read_text(encoding="utf-8", errors="ignore")


def _read_pdf_file(path: Path) -> str:
    """Extract plain text from a PDF file."""
    global PdfReader

    if PdfReader is None:
        try:
            PdfReader = importlib.import_module("pypdf").PdfReader
        except ImportError as exc:
            raise RuntimeError(
                "PDF support requires the optional dependency `pypdf`. "
                "Install project dependencies before extracting from PDFs."
            ) from exc

    reader = PdfReader(path)
    pages = [(page.extract_text() or "").strip() for page in reader.pages]
    text = "\n\n".join(page for page in pages if page)
    if not text.strip():
        raise ValueError(f"No extractable text found in PDF: {path}")
    return text


def load_text_source(source: str | Path) -> tuple[str, dict[str, str]]:
    """Read a supported source file and return plain text plus source metadata.

    Supported inputs currently include:
    - GCS files at ``gs://bucket/path/to/file``
    """
    source_str = str(source)
    
    # Handle GCS URIs
    if source_str.startswith("gs://"):
        try:
            file_content = download_file_from_gcs(source_str)
            suffix = Path(source_str).suffix.lower()
            if suffix == ".pdf":
                global PdfReader
                if PdfReader is None:
                    try:
                        PdfReader = importlib.import_module("pypdf").PdfReader
                    except ImportError as exc:
                        raise RuntimeError(
                            "PDF support requires the optional dependency `pypdf`. "
                            "Install project dependencies before extracting from PDFs."
                        ) from exc
                reader = PdfReader(BytesIO(file_content))
                pages = [(page.extract_text() or "").strip() for page in reader.pages]
                text = "\n\n".join(page for page in pages if page).strip()
                source_type = "pdf"
            else:
                text = file_content.decode("utf-8", errors="ignore").strip()
                source_type = "text"
            if not text:
                raise ValueError(f"No readable text found in GCS file: {source_str}")
            
            source_name = Path(source_str).stem  # Extract filename from gs:// path
            metadata = {
                "source_name": source_name,
                "source_path": source_str,
                "source_type": source_type,
                "source_location": "gcs",
            }
            return text, metadata
        except Exception as exc:
            raise ValueError(f"Failed to read GCS file {source_str}: {exc}") from exc

    raise ValueError("Only GCS sources are supported in GCP-only mode (expected gs:// URI).")


# ---------------------------------------------------------------------------
# Offline extraction (no API key required)
# ---------------------------------------------------------------------------

_REL_PATTERN = re.compile(
    r"([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*)"
    r"\s+(is|was|founded|works at|worked at|leads|acquired)\s+"
    r"([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*)",
)


def extract_from_text_offline(text: str) -> dict:
    """Extract entities and relationships using regex heuristics.

    No external API or ML model required. Suitable for demos and tests.
    Returns the same shape as extract_from_text:
        {"entities": [...], "relationships": [...]} 

    TODO: Improve NER patterns; add co-reference resolution.
    """
    raw_entities = re.findall(r"\b([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*)\b", text)
    seen: set[str] = set()
    entities: list[dict] = []
    for match in raw_entities:
        slug = match.lower().replace(" ", "-")
        if slug not in seen:
            seen.add(slug)
            entities.append({"id": slug, "label": match, "type": "concept"})

    relationships: list[dict] = []
    for m in _REL_PATTERN.finditer(text):
        src = m.group(1).lower().replace(" ", "-")
        tgt = m.group(3).lower().replace(" ", "-")
        rel = m.group(2)
        relationships.append({"source": src, "target": tgt, "relation": rel})

    return {"entities": entities, "relationships": relationships}


# ---------------------------------------------------------------------------
# LLM-backed extraction (requires OPENAI_API_KEY)
# ---------------------------------------------------------------------------

_EXTRACTION_PROMPT = (
    "Extract all named entities and relationships from the text below.\n"
    "Return ONLY valid JSON with this exact structure:\n"
    '{{"entities": [{{"id": "<slug>", "label": "<name>", "type": "<person|org|place|concept>", "properties": {{}}}}], '
    '"relationships": [{{"source": "<id>", "target": "<id>", "relation": "<verb>", "properties": {{}}}}]}}\n'
    'If nothing is found, return {{"entities": [], "relationships": []}}.\n'
    "Do not include markdown fences or explanatory text.\n"
    "Chunk {chunk_index} of {total_chunks}:\n{text}"
)


def _chunk_text(
    text: str,
    *,
    max_chunk_chars: int = _DEFAULT_CHUNK_SIZE,
    overlap_chars: int = _DEFAULT_CHUNK_OVERLAP,
) -> list[str]:
    """Split long input into overlapping chunks for safe LLM processing."""
    clean = text.strip()
    if not clean:
        return []
    if max_chunk_chars <= 0:
        raise ValueError("max_chunk_chars must be positive.")
    if overlap_chars < 0:
        raise ValueError("overlap_chars must be non-negative.")
    if overlap_chars >= max_chunk_chars:
        overlap_chars = max(0, max_chunk_chars // 5)

    chunks: list[str] = []
    start = 0
    while start < len(clean):
        end = min(start + max_chunk_chars, len(clean))
        if end < len(clean):
            split_candidates = (
                clean.rfind("\n\n", start, end),
                clean.rfind(". ", start, end),
                clean.rfind(" ", start, end),
            )
            split_at = max(split_candidates)
            if split_at > start + max_chunk_chars // 2:
                end = split_at + 1

        if end <= start:
            end = min(start + max_chunk_chars, len(clean))

        chunk = clean[start:end].strip()
        if chunk:
            chunks.append(chunk)

        if end >= len(clean):
            break
        start = max(0, end - overlap_chars)

    return chunks


def _strip_code_fences(raw: str) -> str:
    """Strip markdown code fences that models may wrap around JSON."""
    clean = re.sub(r"^```(?:json)?\s*", "", raw.strip(), flags=re.MULTILINE)
    return re.sub(r"\s*```$", "", clean.strip(), flags=re.MULTILINE)


def _parse_llm_json(raw: str) -> dict[str, Any]:
    """Parse and validate the LLM JSON response."""
    clean = _strip_code_fences(raw)

    try:
        result = json.loads(clean)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"LLM returned non-JSON output: {exc}\nRaw response:\n{raw}"
        ) from exc

    if not isinstance(result, dict):
        raise ValueError("LLM response must be a JSON object.")
    if "entities" not in result or "relationships" not in result:
        raise ValueError(
            "LLM response missing required keys 'entities' or 'relationships'."
        )
    if not isinstance(result["entities"], list) or not isinstance(result["relationships"], list):
        raise ValueError("LLM response keys 'entities' and 'relationships' must be lists.")

    return result


def _normalize_entity(entity: dict[str, Any]) -> dict[str, Any] | None:
    """Normalize an entity payload returned by the model."""
    label = str(entity.get("label") or entity.get("id") or "").strip()
    entity_id = str(entity.get("id") or _slug(label)).strip()
    if not entity_id and not label:
        return None

    properties = dict(entity.get("properties", {}))
    for key, value in entity.items():
        if key not in {"id", "label", "type", "properties"}:
            properties[key] = value

    normalized = {
        "id": entity_id or _slug(label),
        "label": label or entity_id,
        "type": str(entity.get("type") or "concept"),
    }
    if properties:
        normalized["properties"] = properties
    return normalized


def _normalize_relationship(relationship: dict[str, Any]) -> dict[str, Any] | None:
    """Normalize a relationship payload returned by the model."""
    source = str(relationship.get("source") or "").strip()
    target = str(relationship.get("target") or "").strip()
    relation = str(relationship.get("relation") or "related_to").strip()
    if not source or not target:
        return None

    properties = dict(relationship.get("properties", {}))
    for key, value in relationship.items():
        if key not in {"source", "target", "relation", "properties"}:
            properties[key] = value

    normalized = {
        "source": source,
        "target": target,
        "relation": relation or "related_to",
    }
    if properties:
        normalized["properties"] = properties
    return normalized


def _merge_extractions(partials: list[dict[str, Any]], *, metadata: dict[str, Any]) -> dict[str, Any]:
    """Merge and de-duplicate chunk-level extractions into one result."""
    entities_by_id: dict[str, dict[str, Any]] = {}
    relationships_by_key: dict[tuple[str, str, str], dict[str, Any]] = {}

    for partial in partials:
        for entity in partial.get("entities", []):
            if not isinstance(entity, dict):
                continue
            normalized_entity = _normalize_entity(entity)
            if normalized_entity is None:
                continue

            existing = entities_by_id.get(normalized_entity["id"])
            if existing is None:
                entities_by_id[normalized_entity["id"]] = normalized_entity
                continue

            merged_properties = dict(existing.get("properties", {}))
            merged_properties.update(normalized_entity.get("properties", {}))
            if merged_properties:
                existing["properties"] = merged_properties
            if existing.get("label") == existing.get("id") and normalized_entity.get("label"):
                existing["label"] = normalized_entity["label"]
            if existing.get("type") in {"", "concept"} and normalized_entity.get("type"):
                existing["type"] = normalized_entity["type"]

        for relationship in partial.get("relationships", []):
            if not isinstance(relationship, dict):
                continue
            normalized_relationship = _normalize_relationship(relationship)
            if normalized_relationship is None:
                continue

            key = (
                normalized_relationship["source"],
                normalized_relationship["target"],
                normalized_relationship["relation"],
            )
            existing_relationship = relationships_by_key.get(key)
            if existing_relationship is None:
                relationships_by_key[key] = normalized_relationship
                continue

            merged_properties = dict(existing_relationship.get("properties", {}))
            merged_properties.update(normalized_relationship.get("properties", {}))
            if merged_properties:
                existing_relationship["properties"] = merged_properties

    final_metadata = dict(metadata)
    final_metadata["entity_count"] = len(entities_by_id)
    final_metadata["relationship_count"] = len(relationships_by_key)

    return {
        "entities": sorted(entities_by_id.values(), key=lambda item: item["id"]),
        "relationships": sorted(
            relationships_by_key.values(),
            key=lambda item: (item["source"], item["target"], item["relation"]),
        ),
        "metadata": final_metadata,
    }


def _call_extraction_llm(
    prompt: str,
    *,
    llm_caller: Callable[..., str] | None = None,
    max_retries: int = _DEFAULT_MAX_RETRIES,
) -> dict[str, Any]:
    """Call the configured LLM and return a validated JSON payload."""
    caller = llm_caller or call_llm

    try:
        raw = caller(
            prompt,
            response_format={"type": "json_object"},
            max_retries=max_retries,
        )
    except TypeError:
        # Backward compatibility for older callables used in tests or local scripts.
        raw = caller(prompt)

    return _parse_llm_json(raw)


def extract_from_text(
    text: str,
    *,
    source_metadata: dict[str, str] | None = None,
    max_chunk_chars: int = _DEFAULT_CHUNK_SIZE,
    overlap_chars: int = _DEFAULT_CHUNK_OVERLAP,
    max_retries: int = _DEFAULT_MAX_RETRIES,
    llm_caller: Callable[..., str] | None = None,
) -> dict[str, Any]:
    """Extract entities and relationships from free text via the configured LLM.

    The pipeline supports long inputs by chunking the text into bounded windows,
    invoking the model per chunk, and merging results into a structured JSON payload
    with entities, relationships, and run metadata.
    """
    cleaned_text = text.strip()
    metadata: dict[str, Any] = dict(source_metadata or {})
    metadata.setdefault("source_name", "inline-text")
    metadata.setdefault("source_type", "text")
    metadata["extraction_mode"] = "llm"
    metadata["input_characters"] = len(cleaned_text)
    metadata["llm_model"] = get_optional_env("OPENAI_MODEL", "gpt-4o-mini") or "gpt-4o-mini"

    if not cleaned_text:
        metadata["chunk_count"] = 0
        metadata["entity_count"] = 0
        metadata["relationship_count"] = 0
        return {"entities": [], "relationships": [], "metadata": metadata}

    chunks = _chunk_text(
        cleaned_text,
        max_chunk_chars=max_chunk_chars,
        overlap_chars=overlap_chars,
    )
    metadata["chunk_count"] = len(chunks)

    partial_results: list[dict[str, Any]] = []
    for index, chunk in enumerate(chunks, start=1):
        logger.info("Processing text chunk %s/%s", index, len(chunks))
        prompt = _EXTRACTION_PROMPT.format(
            text=chunk,
            chunk_index=index,
            total_chunks=len(chunks),
        )
        partial_results.append(
            _call_extraction_llm(
                prompt,
                llm_caller=llm_caller,
                max_retries=max_retries,
            )
        )

    return _merge_extractions(partial_results, metadata=metadata)


def write_extraction_artifacts(
    extraction: dict[str, Any],
    *,
    source: str | Path | None = None,
    output_gcs_uri: str,
    title: str | None = None,
) -> dict[str, str | Path]:
    """Persist extraction JSON and rendered graph image.

    GCP-only mode:
    - Writes JSON and PNG artifacts to GCS and returns gs:// URIs.
    """
    source_path = Path(source) if source is not None else None
    payload = dict(extraction)
    payload.setdefault("metadata", {})
    
    if source_path is not None:
        payload["metadata"].setdefault("source_name", _dataset_name(source_path))
        payload["metadata"].setdefault("source_path", str(source_path))
        payload["metadata"].setdefault(
            "source_type",
            "pdf" if source_path.suffix.lower() == ".pdf" else "text",
        )

    import os
    import tempfile
    from engine.upload.gcp import upload_file_content_to_gcs
        
    # Prepare JSON content
    json_content = json.dumps(payload, indent=2).encode("utf-8")
        
    # Build GCS paths for JSON and PNG
    gcs_json_uri = output_gcs_uri.rstrip("/") + "/graph.json"
    gcs_png_uri = output_gcs_uri.rstrip("/") + "/graph.png"
        
    # Extract bucket and blob names from GCS URIs
    def parse_gcs_uri(uri: str) -> tuple[str, str]:
        if not uri.startswith("gs://"):
            raise ValueError(f"Invalid GCS URI: {uri}")
        path_part = uri[5:]
        bucket, _, blob = path_part.partition("/")
        return bucket, blob
        
    bucket, json_blob = parse_gcs_uri(gcs_json_uri)
    project_id = os.environ.get("GCP_PROJECT_ID")
        
    # Upload JSON to GCS
    upload_file_content_to_gcs(
        json_content,
        filename="graph.json",
        bucket_name=bucket,
        blob_name=json_blob,
        project_id=project_id,
    )
        
    # Create graph and save PNG temporarily
    graph = build_graph_from_extraction(payload)
    with tempfile.NamedTemporaryFile(mode="wb", suffix=".png", delete=False) as tmp:
        tmp_png_path = Path(tmp.name)
        
    try:
        saved_graph_path = visualize_graph(
            graph,
            str(tmp_png_path),
            title=title or f"{payload['metadata'].get('source_name', 'Text').title()} Graph",
        )

        # Read PNG and upload to GCS
        png_content = saved_graph_path.read_bytes()
        _, png_blob = parse_gcs_uri(gcs_png_uri)
        upload_file_content_to_gcs(
            png_content,
            filename="graph.png",
            bucket_name=bucket,
            blob_name=png_blob,
            project_id=project_id,
        )
    finally:
        if tmp_png_path.exists():
            tmp_png_path.unlink()

    return {
        "json_path": gcs_json_uri,
        "graph_path": gcs_png_uri,
    }
