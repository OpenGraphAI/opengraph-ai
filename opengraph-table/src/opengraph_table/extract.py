"""Extract structured data from a single table using Anthropic's vision API."""

from __future__ import annotations

import base64
import io
import json
from datetime import datetime
from pathlib import Path

import anthropic
from PIL import Image

from opengraph_table.schema import (
    CellLocation,
    CellValue,
    ColumnMetadata,
    Row,
    TableEntity,
    TableExtraction,
    TableNote,
    TableRelationship,
    TableSource,
    validate_extraction,
)

_MAX_LONG_EDGE = 1568

_SYSTEM_PROMPT = """\
You are a precise table knowledge-graph extractor. Analyze the provided table image and \
extract complete, structured data.

Guidelines:
- **Columns**: Identify column headers, infer data types (text/numeric/date/boolean).
- **Rows**: Extract all cell values accurately, preserving structure.
- **Entities**: Identify and extract distinct entities mentioned in the table (e.g., products, \
people, locations). Assign unique snake_case IDs.
- **Relationships**: Identify relationships between entities (e.g., product belongs to category, \
person manages department).
- **Metrics**: Identify computed aggregates (sums, averages, counts, percentages).
- **Notes**: Extract any footnotes, legends, or important context notes.
- **Confidence**: Rate 0.0-1.0 for each extraction; prefer 0.8-0.95 for clear data.

Return a complete JSON response matching the TableExtraction schema.
"""

_GRAPH_JSON_PROMPT = """\
You are a precise table-to-knowledge-graph extractor.

You will be given MANY tables at once. Merge them into one coherent knowledge graph.

Return a CONCISE graph. Do not emit one node per row or cell. Prefer canonical entities,
files/filings, reports, summary metrics, and the most important relationships.
Collapse repeated concepts across tables into shared nodes.
Keep strings short and single-line.

Return ONLY valid JSON in NetworkX node-link style with this exact top-level shape:
{
    "graph": {
        "directed": true,
        "multigraph": false,
        "graph": {},
        "nodes": [{"id": "...", "type": "...", ...}],
        "links": [{"source": "...", "target": "...", "relation": "...", ...}]
    },
    "sources": {
        "<source_id>": {
            "id": "<source_id>",
            "filename": "...",
            "sheet_name": null,
            "page_index": null,
            "table_index": 0,
            "title": null,
            "extracted_at": "..."
        }
    },
    "metadata": {
        "total_nodes": <int>,
        "total_edges": <int>,
        "node_count_by_type": {"entity": <int>},
        "relation_count": {"related_to": <int>},
        "top_nodes": [],
        "sources": 1
    }
}

Rules:
- Use stable IDs.
- Include table/entity/metric relationships as links.
- No markdown, no explanation, JSON only.
"""

_TABLE_PREVIEW_ROWS = 5


def _resize_if_needed(img: Image.Image) -> Image.Image:
    """Resize image if it exceeds max long edge."""
    long_edge = max(img.width, img.height)
    if long_edge <= _MAX_LONG_EDGE:
        return img
    scale = _MAX_LONG_EDGE / long_edge
    return img.resize((int(img.width * scale), int(img.height * scale)), Image.LANCZOS)


def _extract_json_object(response_text: str) -> dict:
    """Extract first JSON object from model text response."""
    json_start = response_text.find("{")
    json_end = response_text.rfind("}") + 1
    if json_start < 0 or json_end <= json_start:
        raise ValueError("No JSON found in response")
    json_str = response_text[json_start:json_end]
    return json.loads(json_str)


def _read_table_preview(table_path: Path, max_rows: int = _TABLE_PREVIEW_ROWS) -> str:
    """Read a compact preview for a tabular file."""
    suffix = table_path.suffix.lower()

    if suffix in {".tsv", ".csv"}:
        import pandas as pd

        sep = "\t" if suffix == ".tsv" else ","
        df = pd.read_csv(table_path, sep=sep, dtype=str).fillna("")
        preview = df.head(max_rows)
        return (
            f"rows={len(df)}, columns={len(df.columns)}\n"
            f"columns={list(df.columns)}\n"
            f"preview:\n{preview.to_csv(sep=sep, index=False)}"
        )

    if suffix in {".xlsx", ".xls"}:
        import pandas as pd

        sheets = pd.read_excel(table_path, sheet_name=None, dtype=str)
        blocks: list[str] = []
        for sheet_name, df in sheets.items():
            df = df.fillna("")
            preview = df.head(max_rows)
            blocks.append(
                f"sheet={sheet_name}, rows={len(df)}, columns={len(df.columns)}\n"
                f"columns={list(df.columns)}\n"
                f"preview:\n{preview.to_csv(index=False)}"
            )
        return "\n\n".join(blocks)

    # Fallback to plain text for other table-like files
    return table_path.read_text(errors="replace")


def _build_llm_table_bundle(table_paths: list[Path]) -> str:
    """Build one prompt bundle containing all tables."""
    sections: list[str] = []
    for i, table_path in enumerate(table_paths):
        sections.append(
            f"## TABLE {i + 1}\n"
            f"filename={table_path.name}\n"
            f"path={table_path}\n"
            f"suffix={table_path.suffix.lower()}\n"
            f"{_read_table_preview(table_path)}"
        )
    return "\n\n".join(sections)


def extract_table(
    table_path: Path,
    client: anthropic.Anthropic,
    table_index: int = 0,
    sheet_name: str | None = None,
    page_index: int | None = None,
) -> TableExtraction:
    """Extract structured data from a single table image.

    Args:
        table_path: Path to table image file.
        client: Anthropic client.
        table_index: Index of this table (for source tracking).
        sheet_name: Sheet name if from Excel.
        page_index: Page index if from PDF.

    Returns:
        TableExtraction with all extracted table data.

    Raises:
        ValueError: If extraction fails validation.
    """
    img = Image.open(table_path)
    original_format = img.format or "PNG"
    orig_width, orig_height = img.width, img.height

    img = _resize_if_needed(img.convert("RGB"))

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=90)
    image_b64 = base64.standard_b64encode(buf.getvalue()).decode()

    # Create source metadata
    source = TableSource(
        id=table_path.stem.replace(" ", "_").replace("-", "_").lower(),
        filename=str(table_path),
        sheet_name=sheet_name,
        page_index=page_index,
        table_index=table_index,
        title=None,  # Will be populated from extraction if available
        extracted_at=datetime.utcnow().isoformat(),
    )

    # Call Claude vision API
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4096,
        system=_SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/jpeg",
                            "data": image_b64,
                        },
                    },
                    {
                        "type": "text",
                        "text": (
                            f"Extract this table completely and return JSON.\n"
                            f"File: {table_path.name}, width={orig_width}, height={orig_height}, format={original_format}."
                        ),
                    },
                ],
            }
        ],
    )

    # Parse response
    response_text = response.content[0].text
    try:
        # Try to extract JSON from response
        json_start = response_text.find("{")
        json_end = response_text.rfind("}") + 1
        if json_start >= 0 and json_end > json_start:
            json_str = response_text[json_start:json_end]
            data = json.loads(json_str)
        else:
            raise ValueError("No JSON found in response")
    except (json.JSONDecodeError, ValueError) as e:
        raise ValueError(f"Failed to parse Claude response as JSON: {e}\n{response_text}")

    # Reconstruct TableExtraction from response
    # The response should follow the schema structure
    columns = [
        ColumnMetadata(
            name=col.get("name", f"Column {i}"),
            index=i,
            data_type=col.get("data_type", "text"),
            is_key=col.get("is_key", False),
            nullable=col.get("nullable", True),
        )
        for i, col in enumerate(data.get("columns", []))
    ]

    rows = [
        Row(
            index=i,
            cells=[
                CellValue(
                    location=CellLocation(row_index=i, col_index=j),
                    raw_value=cell.get("raw_value", ""),
                    normalized_value=cell.get("normalized_value"),
                    data_type=cell.get("data_type", "text"),
                    confidence=cell.get("confidence", 0.9),
                )
                for j, cell in enumerate(row.get("cells", []))
            ],
            is_header=row.get("is_header", False),
        )
        for i, row in enumerate(data.get("rows", []))
    ]

    entities = [
        TableEntity(
            id=e.get("id", f"entity_{i}"),
            name=e.get("name", ""),
            entity_type=e.get("entity_type", "unknown"),
            source_cells=[
                CellLocation(row_index=c.get("row_index", 0), col_index=c.get("col_index", 0))
                for c in e.get("source_cells", [])
            ],
            attributes=e.get("attributes", {}),
            confidence=e.get("confidence", 0.85),
        )
        for i, e in enumerate(data.get("entities", []))
    ]

    relationships = [
        TableRelationship(
            source_entity_id=r.get("source_entity_id", ""),
            target_entity_id=r.get("target_entity_id", ""),
            relation_type=r.get("relation_type", ""),
            source_cells=[
                CellLocation(row_index=c.get("row_index", 0), col_index=c.get("col_index", 0))
                for c in r.get("source_cells", [])
            ],
            confidence=r.get("confidence", 0.8),
        )
        for r in data.get("relationships", [])
    ]

    metrics = [
        # Metrics are optional in the current version
    ]

    notes = [
        TableNote(
            id=n.get("id", f"note_{i}"),
            content=n.get("content", ""),
            note_type=n.get("note_type", "context"),
            related_cells=[
                CellLocation(row_index=c.get("row_index", 0), col_index=c.get("col_index", 0))
                for c in n.get("related_cells", [])
            ],
        )
        for i, n in enumerate(data.get("notes", []))
    ]

    # Update source title if provided
    if "title" in data:
        source.title = data["title"]

    extraction = TableExtraction(
        source=source,
        columns=columns,
        rows=rows,
        entities=entities,
        relationships=relationships,
        metrics=metrics,
        notes=notes,
    )

    errors = validate_extraction(extraction)
    if errors:
        raise ValueError("Extraction failed validation:\n" + "\n".join(errors))

    return extraction


def extract_table_llm_graph_json(
    table_path: Path,
    client: anthropic.Anthropic,
    table_index: int = 0,
    sheet_name: str | None = None,
    page_index: int | None = None,
) -> dict:
    """Ask Claude to return knowledge-graph JSON directly.

    This returns LLM-produced JSON as-is (after JSON parsing), instead of
    reconstructing `TableExtraction` first.
    """
    img = Image.open(table_path)
    original_format = img.format or "PNG"
    orig_width, orig_height = img.width, img.height
    img = _resize_if_needed(img.convert("RGB"))

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=90)
    image_b64 = base64.standard_b64encode(buf.getvalue()).decode()

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=12000,
        system=_GRAPH_JSON_PROMPT,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/jpeg",
                            "data": image_b64,
                        },
                    },
                    {
                        "type": "text",
                        "text": (
                            "Return the complete knowledge graph JSON for this table.\n"
                            f"File: {table_path.name}, width={orig_width}, height={orig_height}, format={original_format}.\n"
                            f"table_index={table_index}, sheet_name={sheet_name}, page_index={page_index}."
                        ),
                    },
                ],
            }
        ],
    )

    response_text = response.content[0].text
    try:
        return _extract_json_object(response_text)
    except (json.JSONDecodeError, ValueError) as e:
        raise ValueError(f"Failed to parse Claude graph JSON response: {e}\n{response_text}")


def _build_llm_table_bundle_from_content(tables: list[dict]) -> str:
    """Build one prompt bundle from raw table content strings.

    Each dict must have ``filename`` and ``content`` keys.
    """
    sections: list[str] = []
    for i, t in enumerate(tables):
        filename = t.get("filename", f"table_{i}.csv")
        content = t.get("content", "")
        suffix = Path(filename).suffix.lower()
        sections.append(
            f"## TABLE {i + 1}\n"
            f"filename={filename}\n"
            f"suffix={suffix}\n"
            f"{content}"
        )
    return "\n\n".join(sections)


def extract_tables_from_content(
    tables: list[dict],
    client: anthropic.Anthropic,
) -> dict:
    """Ask Claude to merge raw table content strings into one graph JSON.

    Args:
        tables: List of dicts with ``filename`` and ``content`` keys.
        client: Anthropic client.

    Returns:
        Graph JSON dict (NetworkX node-link format with metadata).
    """
    if not tables:
        raise ValueError("No tables provided")

    bundle = _build_llm_table_bundle_from_content(tables)
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=12000,
        system=_GRAPH_JSON_PROMPT,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": (
                            "Analyze all of these tables together. Merge overlapping rows, "
                            "entities, and concepts into a single knowledge graph JSON.\n\n"
                            f"{bundle}"
                        ),
                    }
                ],
            }
        ],
    )

    response_text = response.content[0].text
    try:
        return _extract_json_object(response_text)
    except (json.JSONDecodeError, ValueError) as e:
        raise ValueError(f"Failed to parse Claude batch graph JSON response: {e}\n{response_text}")


def extract_tables_llm_graph_json(
    table_paths: list[Path],
    client: anthropic.Anthropic,
) -> dict:
    """Ask Claude to merge all tables at once and return one graph JSON."""
    if not table_paths:
        raise ValueError("No table files provided")

    bundle = _build_llm_table_bundle(table_paths)
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=12000,
        system=_GRAPH_JSON_PROMPT,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": (
                            "Analyze all of these tables together. Merge overlapping rows, "
                            "entities, and concepts into a single knowledge graph JSON.\n\n"
                            f"{bundle}"
                        ),
                    }
                ],
            }
        ],
    )

    response_text = response.content[0].text
    try:
        return _extract_json_object(response_text)
    except (json.JSONDecodeError, ValueError) as e:
        raise ValueError(f"Failed to parse Claude batch graph JSON response: {e}\n{response_text}")
