"""Tests for opengraph_text.schema — node models and validate_extraction."""

import pytest
from pydantic import ValidationError

from opengraph_text.schema import (
    AboutTopicEdge,
    AttributeNode,
    ClaimNode,
    ContainsEdge,
    DocumentExtraction,
    DocumentNode,
    EntityNode,
    HasAttributeEdge,
    RelatesToEdge,
    StatesEdge,
    TopicNode,
    validate_extraction,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _valid_extraction() -> DocumentExtraction:
    """Build a small but complete DocumentExtraction that should pass validation."""
    document = DocumentNode(id="doc_acme_memo", path="/docs/acme_memo.md", word_count=842, format="md")
    acme = EntityNode(id="acme_corp", label="Acme Corp", entity_type="organization", confidence=0.95)
    jane = EntityNode(id="jane_doe_1", label="Jane Doe", entity_type="person", confidence=0.9)
    topic = TopicNode(id="venture_capital", label="venture capital", confidence=0.85)
    attr_role = AttributeNode(id="attr_jane_role", key="role", value="CEO", confidence=0.8)
    claim = ClaimNode(id="claim_funding", text="Acme Corp raised a $10M Series A in 2024.", confidence=0.92)

    return DocumentExtraction(
        document=document,
        entities=[acme, jane],
        topics=[topic],
        attributes=[attr_role],
        claims=[claim],
        contains_edges=[
            ContainsEdge(source="doc_acme_memo", target="acme_corp", confidence=0.95),
            ContainsEdge(source="doc_acme_memo", target="jane_doe_1", confidence=0.9),
        ],
        about_topic_edges=[
            AboutTopicEdge(source="doc_acme_memo", target="venture_capital", confidence=0.85)
        ],
        has_attribute_edges=[
            HasAttributeEdge(source="jane_doe_1", target="attr_jane_role", confidence=0.8)
        ],
        states_edges=[StatesEdge(source="doc_acme_memo", target="claim_funding", confidence=0.92)],
        relates_to_edges=[
            RelatesToEdge(
                source="jane_doe_1",
                target="acme_corp",
                relation="works_at",
                confidence=0.88,
            )
        ],
    )


# ---------------------------------------------------------------------------
# Valid extraction
# ---------------------------------------------------------------------------

class TestValidExtraction:
    def test_no_errors(self) -> None:
        extraction = _valid_extraction()
        errors = validate_extraction(extraction)
        assert errors == [], f"Expected no errors, got: {errors}"

    def test_document_node_fields(self) -> None:
        ext = _valid_extraction()
        assert ext.document.id == "doc_acme_memo"
        assert ext.document.word_count == 842
        assert ext.document.format == "md"

    def test_entity_type(self) -> None:
        ext = _valid_extraction()
        acme = next(e for e in ext.entities if e.id == "acme_corp")
        assert acme.entity_type == "organization"

    def test_attribute_key(self) -> None:
        ext = _valid_extraction()
        assert ext.attributes[0].key == "role"

    def test_relates_to_edge_relation(self) -> None:
        ext = _valid_extraction()
        assert ext.relates_to_edges[0].relation == "works_at"


# ---------------------------------------------------------------------------
# Invalid extractions
# ---------------------------------------------------------------------------

class TestInvalidExtraction:
    def test_duplicate_id_and_dangling_edge(self) -> None:
        """A malformed extraction with a duplicate node ID and a dangling edge

        reference should fail validation with both errors reported.
        """
        ext = _valid_extraction()

        # Duplicate ID: reuse "acme_corp" for a new entity node.
        ext.entities.append(
            EntityNode(id="acme_corp", label="Acme Corp Duplicate", entity_type="organization", confidence=0.5)
        )

        # Dangling edge: reference a topic ID that does not exist.
        ext.about_topic_edges.append(
            AboutTopicEdge(source="doc_acme_memo", target="ghost_topic", confidence=0.5)
        )

        errors = validate_extraction(ext)
        assert any("acme_corp" in e for e in errors), errors
        assert any("ghost_topic" in e for e in errors), errors
        assert len(errors) >= 2

    def test_unknown_edge_source(self) -> None:
        ext = _valid_extraction()
        ext.states_edges.append(
            StatesEdge(source="nonexistent_doc", target="claim_funding", confidence=0.9)
        )
        errors = validate_extraction(ext)
        assert any("nonexistent_doc" in e for e in errors), errors

    def test_invalid_entity_type_raises(self) -> None:
        with pytest.raises(ValidationError):
            EntityNode(id="e1", label="Thing", entity_type="animal", confidence=0.5)  # type: ignore[arg-type]

    def test_invalid_attribute_key_raises(self) -> None:
        with pytest.raises(ValidationError):
            AttributeNode(id="a1", key="color", value="blue", confidence=0.6)  # type: ignore[arg-type]

    def test_confidence_out_of_range_raises(self) -> None:
        with pytest.raises(ValidationError):
            TopicNode(id="t1", label="ai", confidence=1.5)

    def test_claim_text_too_long_raises(self) -> None:
        with pytest.raises(ValidationError):
            ClaimNode(id="c1", text="x" * 201, confidence=0.9)

    def test_document_zero_word_count_raises(self) -> None:
        with pytest.raises(ValidationError):
            DocumentNode(id="doc1", path="/a.txt", word_count=0, format="txt")

    def test_invalid_document_format_raises(self) -> None:
        with pytest.raises(ValidationError):
            DocumentNode(id="doc1", path="/a.docx", word_count=10, format="docx")  # type: ignore[arg-type]

    def test_invalid_relation_type_raises(self) -> None:
        with pytest.raises(ValidationError):
            RelatesToEdge(source="e1", target="e2", relation="knows", confidence=0.5)  # type: ignore[arg-type]
