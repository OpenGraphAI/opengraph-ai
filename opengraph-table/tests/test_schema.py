"""Tests for opengraph-table schema and extraction."""

import pytest
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
    Metric,
    validate_extraction,
)


class TestSchemaModels:
    """Test Pydantic models."""

    def test_cell_location(self) -> None:
        """Test CellLocation model."""
        cell = CellLocation(row_index=0, col_index=1)
        assert cell.row_index == 0
        assert cell.col_index == 1

    def test_table_source(self) -> None:
        """Test TableSource provenance tracking."""
        source = TableSource(
            id="source_001",
            filename="test.csv",
            sheet_name="Sheet1",
            page_index=None,
            table_index=0,
            title="Test Table",
            extracted_at="2024-01-01T00:00:00Z",
        )
        assert source.id == "source_001"
        assert source.filename == "test.csv"

    def test_column_metadata(self) -> None:
        """Test ColumnMetadata model."""
        col = ColumnMetadata(
            name="Product ID",
            index=0,
            data_type="numeric",
            is_key=True,
            nullable=False,
        )
        assert col.name == "Product ID"
        assert col.is_key is True
        assert col.data_type == "numeric"

    def test_cell_value(self) -> None:
        """Test CellValue model."""
        location = CellLocation(row_index=1, col_index=0)
        cell = CellValue(
            location=location,
            raw_value="123",
            normalized_value="123",
            data_type="numeric",
            confidence=0.95,
        )
        assert cell.normalized_value == "123"
        assert cell.data_type == "numeric"

    def test_row(self) -> None:
        """Test Row model."""
        location = CellLocation(row_index=0, col_index=0)
        cell = CellValue(
            location=location,
            raw_value="value",
            normalized_value="value",
            data_type="text",
            confidence=0.9,
        )
        row = Row(index=0, cells=[cell], is_header=False)
        assert row.index == 0
        assert len(row.cells) == 1

    def test_table_entity(self) -> None:
        """Test TableEntity model."""
        location = CellLocation(row_index=1, col_index=0)
        entity = TableEntity(
            id="entity_001",
            name="Apple Inc",
            entity_type="company",
            source_cells=[location],
            attributes={"stock_ticker": "AAPL"},
            confidence=0.95,
        )
        assert entity.name == "Apple Inc"
        assert entity.entity_type == "company"
        assert entity.attributes["stock_ticker"] == "AAPL"

    def test_table_relationship(self) -> None:
        """Test TableRelationship model."""
        location = CellLocation(row_index=2, col_index=1)
        rel = TableRelationship(
            source_entity_id="entity_001",
            target_entity_id="entity_002",
            relation_type="founded_by",
            source_cells=[location],
            confidence=0.85,
        )
        assert rel.source_entity_id == "entity_001"
        assert rel.relation_type == "founded_by"

    def test_metric(self) -> None:
        """Test Metric model."""
        metric = Metric(
            id="metric_001",
            name="Total Revenue",
            metric_type="sum",
            column_names=["revenue"],
            value="1000000",
            row_range=(0, 10),
            confidence=0.9,
        )
        assert metric.metric_type == "sum"
        assert metric.value == "1000000"

    def test_table_note(self) -> None:
        """Test TableNote model."""
        location = CellLocation(row_index=5, col_index=2)
        note = TableNote(
            id="note_001",
            content="This value seems anomalous",
            note_type="anomaly",
            related_cells=[location],
        )
        assert note.note_type == "anomaly"
        assert len(note.related_cells) == 1

    def test_table_extraction(self) -> None:
        """Test TableExtraction container."""
        source = TableSource(
            id="source_001",
            filename="test.csv",
            sheet_name=None,
            page_index=None,
            table_index=0,
            title=None,
            extracted_at="2024-01-01T00:00:00Z",
        )
        col = ColumnMetadata(
            name="ID",
            index=0,
            data_type="numeric",
            is_key=True,
            nullable=False,
        )
        extraction = TableExtraction(
            source=source,
            columns=[col],
            rows=[],
            entities=[],
            relationships=[],
            metrics=[],
            notes=[],
        )
        assert extraction.source.id == "source_001"
        assert len(extraction.columns) == 1


class TestValidation:
    """Test extraction validation."""

    def test_validate_extraction_valid(self) -> None:
        """Test basic extraction validation passes."""
        source = TableSource(
            id="source_001",
            filename="test.csv",
            sheet_name=None,
            page_index=None,
            table_index=0,
            title=None,
            extracted_at="2024-01-01T00:00:00Z",
        )
        entity = TableEntity(
            id="entity_001",
            name="Test",
            entity_type="test",
            source_cells=[],
            attributes={},
            confidence=0.9,
        )
        extraction = TableExtraction(
            source=source,
            columns=[],
            rows=[],
            entities=[entity],
            relationships=[],
            metrics=[],
            notes=[],
        )
        # Should validate without errors
        errors = validate_extraction(extraction)
        assert len(errors) == 0

    def test_validate_extraction_duplicate_entity_ids(self) -> None:
        """Test that duplicate entity IDs are detected."""
        source = TableSource(
            id="source_001",
            filename="test.csv",
            sheet_name=None,
            page_index=None,
            table_index=0,
            title=None,
            extracted_at="2024-01-01T00:00:00Z",
        )
        entity = TableEntity(
            id="entity_001",
            name="Test",
            entity_type="test",
            source_cells=[],
            attributes={},
            confidence=0.9,
        )
        extraction = TableExtraction(
            source=source,
            columns=[],
            rows=[],
            entities=[entity, entity],  # Duplicate ID
            relationships=[],
            metrics=[],
            notes=[],
        )
        # validate_extraction should detect duplicate IDs
        errors = validate_extraction(extraction)
        assert any("Duplicate entity IDs" in e for e in errors)

    def test_validate_extraction_relationship_references(self) -> None:
        """Test that relationships to non-existent entities are detected."""
        source = TableSource(
            id="source_001",
            filename="test.csv",
            sheet_name=None,
            page_index=None,
            table_index=0,
            title=None,
            extracted_at="2024-01-01T00:00:00Z",
        )
        entity = TableEntity(
            id="entity_001",
            name="Test",
            entity_type="test",
            source_cells=[],
            attributes={},
            confidence=0.9,
        )
        rel = TableRelationship(
            source_entity_id="entity_001",
            target_entity_id="entity_999",  # Non-existent
            relation_type="relates_to",
            source_cells=[],
            confidence=0.9,
        )
        extraction = TableExtraction(
            source=source,
            columns=[],
            rows=[],
            entities=[entity],
            relationships=[rel],
            metrics=[],
            notes=[],
        )
        # validate_extraction should detect missing entity reference
        errors = validate_extraction(extraction)
        assert any("unknown target entity" in e for e in errors)

    def test_pydantic_validates_cell_bounds(self) -> None:
        """Test that Pydantic validates cell location bounds."""
        from pydantic import ValidationError

        # Negative indices should fail at Pydantic level
        with pytest.raises(ValidationError):
            CellLocation(row_index=-1, col_index=0)

        with pytest.raises(ValidationError):
            CellLocation(row_index=0, col_index=-1)
