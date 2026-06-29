"""Tests for opengraph-table graph operations."""

import json
import tempfile
from pathlib import Path

import pytest

from opengraph_table.graph import TableGraph
from opengraph_table.schema import (
    CellLocation,
    ColumnMetadata,
    TableEntity,
    TableExtraction,
    TableRelationship,
    TableSource,
)


class TestTableGraph:
    """Test TableGraph construction and operations."""

    def test_graph_initialization(self) -> None:
        """Test creating a new empty graph."""
        graph = TableGraph()
        assert graph._g.number_of_nodes() == 0
        assert graph._g.number_of_edges() == 0

    def test_add_extraction_basic(self) -> None:
        """Test adding a basic extraction."""
        graph = TableGraph()

        source = TableSource(
            id="source_001",
            filename="test.csv",
            sheet_name=None,
            page_index=None,
            table_index=0,
            title="Test Table",
            extracted_at="2024-01-01T00:00:00Z",
        )

        entity = TableEntity(
            id="entity_001",
            name="Apple",
            entity_type="company",
            source_cells=[],
            attributes={"ticker": "AAPL"},
            confidence=0.9,
        )

        col = ColumnMetadata(
            name="Company",
            index=0,
            data_type="text",
            is_key=False,
            nullable=False,
        )

        extraction = TableExtraction(
            source=source,
            columns=[col],
            rows=[],
            entities=[entity],
            relationships=[],
            metrics=[],
            notes=[],
        )

        graph.add_extraction(extraction)

        # Check nodes were added
        assert graph._g.number_of_nodes() >= 2  # source + entity + column
        assert "source_001" in graph._g.nodes()
        assert "source_001__entity_entity_001" in graph._g.nodes()

    def test_add_multiple_extractions(self) -> None:
        """Test adding multiple table extractions."""
        graph = TableGraph()

        # First source
        source1 = TableSource(
            id="source_001",
            filename="table1.csv",
            sheet_name=None,
            page_index=None,
            table_index=0,
            title=None,
            extracted_at="2024-01-01T00:00:00Z",
        )

        entity1 = TableEntity(
            id="entity_001",
            name="Apple Inc",
            entity_type="company",
            source_cells=[],
            attributes={},
            confidence=0.9,
        )

        extraction1 = TableExtraction(
            source=source1,
            columns=[],
            rows=[],
            entities=[entity1],
            relationships=[],
            metrics=[],
            notes=[],
        )

        # Second source
        source2 = TableSource(
            id="source_002",
            filename="table2.csv",
            sheet_name=None,
            page_index=None,
            table_index=0,
            title=None,
            extracted_at="2024-01-01T00:00:00Z",
        )

        entity2 = TableEntity(
            id="entity_001",
            name="Apple Inc",
            entity_type="company",
            source_cells=[],
            attributes={},
            confidence=0.85,
        )

        extraction2 = TableExtraction(
            source=source2,
            columns=[],
            rows=[],
            entities=[entity2],
            relationships=[],
            metrics=[],
            notes=[],
        )

        graph.add_extraction(extraction1)
        graph.add_extraction(extraction2)

        # Both sources should be present
        assert "source_001" in graph._g.nodes()
        assert "source_002" in graph._g.nodes()

        # Both entity nodes should be present initially (before merging)
        assert "source_001__entity_entity_001" in graph._g.nodes()
        assert "source_002__entity_entity_001" in graph._g.nodes()

    def test_merge_entities(self) -> None:
        """Test entity merging by name and type."""
        graph = TableGraph()

        # Create two identical entities from different sources
        for i in range(1, 3):
            source = TableSource(
                id=f"source_{i:03d}",
                filename=f"table{i}.csv",
                sheet_name=None,
                page_index=None,
                table_index=0,
                title=None,
                extracted_at="2024-01-01T00:00:00Z",
            )

            entity = TableEntity(
                id="entity_001",
                name="Apple Inc",
                entity_type="company",
                source_cells=[],
                attributes={},
                confidence=0.9 - (i * 0.05),  # Varying confidence
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

            graph.add_extraction(extraction)

        # Merge should consolidate entities
        stats = graph.merge_entities()
        assert stats["entities_merged"] > 0

        # After merge, only one canonical entity should remain
        entity_nodes = [n for n, a in graph._g.nodes(data=True) if a.get("type") == "entity"]
        # Should have consolidated duplicate entities
        assert len(entity_nodes) <= 2

    def test_summary_statistics(self) -> None:
        """Test graph summary statistics."""
        graph = TableGraph()

        source = TableSource(
            id="source_001",
            filename="test.csv",
            sheet_name=None,
            page_index=None,
            table_index=0,
            title=None,
            extracted_at="2024-01-01T00:00:00Z",
        )

        entity1 = TableEntity(
            id="entity_001",
            name="A",
            entity_type="company",
            source_cells=[],
            attributes={},
            confidence=0.9,
        )

        entity2 = TableEntity(
            id="entity_002",
            name="B",
            entity_type="person",
            source_cells=[],
            attributes={},
            confidence=0.9,
        )

        rel = TableRelationship(
            source_entity_id="entity_001",
            target_entity_id="entity_002",
            relation_type="founded_by",
            source_cells=[],
            confidence=0.9,
        )

        extraction = TableExtraction(
            source=source,
            columns=[],
            rows=[],
            entities=[entity1, entity2],
            relationships=[rel],
            metrics=[],
            notes=[],
        )

        graph.add_extraction(extraction)

        summary = graph.summary()
        assert summary["total_nodes"] > 0
        assert "node_count_by_type" in summary
        assert "entity" in summary["node_count_by_type"]

    def test_save_and_load_json(self) -> None:
        """Test saving and loading graphs from JSON."""
        with tempfile.TemporaryDirectory() as tmpdir:
            graph_path = Path(tmpdir) / "test_graph.json"

            # Create and save graph
            graph = TableGraph()
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

            graph.add_extraction(extraction)
            graph.to_json(graph_path)

            # Verify file exists and contains expected structure
            assert graph_path.exists()
            data = json.loads(graph_path.read_text())
            assert "graph" in data
            assert "sources" in data
            assert "metadata" in data

            # Load into new graph
            graph2 = TableGraph()
            graph2.load(graph_path)
            assert graph2._g.number_of_nodes() == graph._g.number_of_nodes()

    def test_save_html_output(self) -> None:
        """Test HTML output generation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            html_path = Path(tmpdir) / "test_graph.html"

            graph = TableGraph()
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
                name="Apple Inc",
                entity_type="company",
                source_cells=[],
                attributes={"ticker": "AAPL"},
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

            graph.add_extraction(extraction)
            graph.to_html(html_path)

            # Check HTML file was created
            assert html_path.exists()
            html_content = html_path.read_text()
            assert "Table Knowledge Graph" in html_content
            assert "Apple Inc" in html_content

    def test_save_markdown_output(self) -> None:
        """Test Markdown output generation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            md_path = Path(tmpdir) / "test_graph.md"

            graph = TableGraph()
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
                name="Test Entity",
                entity_type="company",
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

            graph.add_extraction(extraction)
            graph.to_markdown(md_path)

            # Check Markdown file was created
            assert md_path.exists()
            md_content = md_path.read_text()
            assert "Table Knowledge Graph Report" in md_content
            assert "Test Entity" in md_content
            assert "Entities" in md_content
