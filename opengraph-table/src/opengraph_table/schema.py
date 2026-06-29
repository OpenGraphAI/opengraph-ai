"""Pydantic models for table-based knowledge graphs."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, Field, field_validator


# ---------------------------------------------------------------------------
# Source & Provenance
# ---------------------------------------------------------------------------

class CellLocation(BaseModel):
    """Position of a cell within a table."""

    row_index: int = Field(ge=0, description="Zero-based row index.")
    col_index: int = Field(ge=0, description="Zero-based column index.")


class TableSource(BaseModel):
    """Source information for a table."""

    id: str = Field(description="Unique identifier for this source (filename, sheet name, etc.).")
    filename: str = Field(description="Original filename or source path.")
    sheet_name: str | None = Field(default=None, description="Excel sheet name, if applicable.")
    page_index: int | None = Field(default=None, ge=0, description="Page index if from PDF.")
    table_index: int = Field(ge=0, description="Index of this table within the source.")
    title: str | None = Field(default=None, description="Table title or caption, if present.")
    extracted_at: str = Field(description="ISO 8601 timestamp of extraction.")


# ---------------------------------------------------------------------------
# Structural Elements
# ---------------------------------------------------------------------------

class ColumnMetadata(BaseModel):
    """Metadata about a column."""

    name: str = Field(description="Column header/name.")
    index: int = Field(ge=0, description="Zero-based column index.")
    data_type: Literal["text", "numeric", "date", "boolean", "unknown"] = Field(
        description="Inferred data type."
    )
    is_key: bool = Field(default=False, description="Whether this column is a primary/foreign key.")
    nullable: bool = Field(default=True, description="Whether column can contain null values.")


class CellValue(BaseModel):
    """A single cell with metadata."""

    location: CellLocation = Field(description="Position in the table.")
    raw_value: str = Field(description="Raw text value of the cell.")
    normalized_value: str | None = Field(
        default=None, description="Normalized/parsed value (e.g. parsed date)."
    )
    data_type: Literal["text", "numeric", "date", "boolean", "unknown"] = Field(
        default="text", description="Detected data type."
    )
    confidence: Annotated[float, Field(ge=0.0, le=1.0)] = Field(
        default=0.9, description="Confidence in the extracted value."
    )


class Row(BaseModel):
    """A row in the table."""

    index: int = Field(ge=0, description="Zero-based row index.")
    cells: list[CellValue] = Field(description="Cell values in this row.")
    is_header: bool = Field(default=False, description="Whether this is a header row.")


# ---------------------------------------------------------------------------
# Entities & Relationships
# ---------------------------------------------------------------------------

class TableEntity(BaseModel):
    """An entity extracted from table data."""

    id: str = Field(description="Unique entity ID (snake_case).")
    name: str = Field(description="Entity name or label.")
    entity_type: str = Field(description="Type of entity (e.g., 'person', 'product', 'location').")
    source_cells: list[CellLocation] = Field(
        description="Cell locations where this entity appears."
    )
    attributes: dict[str, str] = Field(
        default_factory=dict, description="Key-value attributes extracted from cells."
    )
    confidence: Annotated[float, Field(ge=0.0, le=1.0)] = Field(
        description="Extraction confidence."
    )


class TableRelationship(BaseModel):
    """A relationship between entities in the table."""

    source_entity_id: str = Field(description="ID of the source entity.")
    target_entity_id: str = Field(description="ID of the target entity.")
    relation_type: str = Field(
        description="Type of relationship (e.g., 'parent_of', 'contains', 'links_to')."
    )
    source_cells: list[CellLocation] = Field(description="Cells supporting this relationship.")
    confidence: Annotated[float, Field(ge=0.0, le=1.0)] = Field(
        description="Relationship confidence."
    )


# ---------------------------------------------------------------------------
# Metrics & Aggregations
# ---------------------------------------------------------------------------

class Metric(BaseModel):
    """A computed metric from table data."""

    id: str = Field(description="Unique metric ID.")
    name: str = Field(description="Metric name.")
    metric_type: Literal["sum", "average", "count", "min", "max", "percentage", "custom"] = Field(
        description="Type of metric."
    )
    column_names: list[str] = Field(description="Column(s) involved in calculation.")
    value: str | float = Field(description="Computed value.")
    row_range: tuple[int, int] | None = Field(
        default=None, description="Row range included in metric (start_idx, end_idx)."
    )
    confidence: Annotated[float, Field(ge=0.0, le=1.0)] = Field(
        default=0.85, description="Confidence in the metric."
    )


# ---------------------------------------------------------------------------
# Annotations & Notes
# ---------------------------------------------------------------------------

class TableNote(BaseModel):
    """Human-readable note or insight about the table."""

    id: str = Field(description="Unique note ID.")
    content: str = Field(description="Note text.")
    note_type: Literal["insight", "anomaly", "validation", "context"] = Field(
        description="Type of note."
    )
    related_cells: list[CellLocation] | None = Field(
        default=None, description="Cells this note refers to."
    )


# ---------------------------------------------------------------------------
# Complete Table Extraction
# ---------------------------------------------------------------------------

class TableExtraction(BaseModel):
    """Complete extraction from a single table."""

    source: TableSource
    columns: list[ColumnMetadata] = Field(description="Column definitions.")
    rows: list[Row] = Field(description="All rows in the table.")
    entities: list[TableEntity] = Field(default_factory=list, description="Extracted entities.")
    relationships: list[TableRelationship] = Field(
        default_factory=list, description="Relationships between entities."
    )
    metrics: list[Metric] = Field(default_factory=list, description="Computed metrics.")
    notes: list[TableNote] = Field(default_factory=list, description="Annotations and insights.")

    @field_validator("rows")
    @classmethod
    def _validate_rows_have_matching_columns(cls, rows: list[Row], info) -> list[Row]:
        """Validate that rows have cells matching column count."""
        columns = info.data.get("columns", [])
        if not columns:
            return rows
        col_count = len(columns)
        for i, row in enumerate(rows):
            if len(row.cells) != col_count:
                raise ValueError(
                    f"Row {i} has {len(row.cells)} cells, "
                    f"but expected {col_count} columns."
                )
        return rows


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate_extraction(extraction: TableExtraction) -> list[str]:
    """Validate referential integrity of a TableExtraction.

    Checks:
    - All entity IDs are unique.
    - All relationship source/target IDs reference existing entities.
    - All cell locations are within table bounds.

    Returns a list of error strings; empty list means valid.
    """
    errors: list[str] = []

    # Check entity ID uniqueness
    entity_ids = {e.id for e in extraction.entities}
    if len(entity_ids) != len(extraction.entities):
        errors.append("Duplicate entity IDs found.")

    # Check relationship references
    for rel in extraction.relationships:
        if rel.source_entity_id not in entity_ids:
            errors.append(f"Relationship references unknown source entity: {rel.source_entity_id}")
        if rel.target_entity_id not in entity_ids:
            errors.append(f"Relationship references unknown target entity: {rel.target_entity_id}")

    # Check cell location bounds
    max_rows = len(extraction.rows)
    max_cols = len(extraction.columns)

    for entity in extraction.entities:
        for cell in entity.source_cells:
            if cell.row_index >= max_rows:
                errors.append(
                    f"Entity {entity.id} references row {cell.row_index}, "
                    f"but table only has {max_rows} rows."
                )
            if cell.col_index >= max_cols:
                errors.append(
                    f"Entity {entity.id} references column {cell.col_index}, "
                    f"but table only has {max_cols} columns."
                )

    return errors
