"""Tests for opengraph_text.schema."""

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


def _valid_extraction() -> DocumentExtraction:
    document = DocumentNode(
        id="acme_pitch_deck",
        path="/docs/acme_pitch_deck.pdf",
        word_count=1200,
        format="pdf",
    )
    entities = [
        EntityNode(
            id="entity_jane_doe_1",
            label="Jane Doe",
            entity_type="person",
            confidence=0.95,
        ),
        EntityNode(
            id="entity_acme_corp_1",
            label="Acme Corp",
            entity_type="organization",
            confidence=0.9,
        ),
    ]
    topics = [
        TopicNode(id="concept_venture_capital", label="Venture Capital", confidence=0.8),
    ]
    attributes = [
        AttributeNode(
            id="attr_jane_doe_role",
            key="role",
            value="CEO",
            confidence=0.85,
        ),
    ]
    claims = [
        ClaimNode(
            id="claim_1",
            text="Acme Corp raised a $10M Series A led by Jane Doe.",
            confidence=0.7,
        ),
    ]

    return DocumentExtraction(
        document=document,
        entities=entities,
        topics=topics,
        attributes=attributes,
        claims=claims,
        contains_edges=[
            ContainsEdge(source="acme_pitch_deck", target="entity_jane_doe_1", confidence=0.9),
            ContainsEdge(source="acme_pitch_deck", target="entity_acme_corp_1", confidence=0.9),
        ],
        about_topic_edges=[
            AboutTopicEdge(source="acme_pitch_deck", target="concept_venture_capital", confidence=0.8),
        ],
        has_attribute_edges=[
            HasAttributeEdge(source="entity_jane_doe_1", target="attr_jane_doe_role", confidence=0.85),
        ],
        states_edges=[
            StatesEdge(source="acme_pitch_deck", target="claim_1", confidence=0.7),
        ],
        relates_to_edges=[
            RelatesToEdge(
                source="entity_jane_doe_1",
                target="entity_acme_corp_1",
                relation="works_at",
                confidence=0.9,
            ),
        ],
    )


def test_valid_extraction_passes_validation():
    extraction = _valid_extraction()
    errors = validate_extraction(extraction)
    assert errors == []


def test_malformed_extraction_fails_validation():
    extraction = _valid_extraction()

    # Introduce a duplicate node id: reuse an existing topic's id for another topic.
    extraction.topics.append(
        TopicNode(id="concept_venture_capital", label="Duplicate", confidence=0.5)
    )

    # Introduce a dangling edge reference to a node id that doesn't exist.
    extraction.contains_edges.append(
        ContainsEdge(source="acme_pitch_deck", target="entity_nonexistent", confidence=0.5)
    )

    errors = validate_extraction(extraction)

    assert len(errors) == 2
    assert any("Duplicate node id" in e and "concept_venture_capital" in e for e in errors)
    assert any("entity_nonexistent" in e for e in errors)


def test_entity_id_must_be_snake_case():
    with pytest.raises(ValidationError):
        EntityNode(
            id="entity_Jane Doe",
            label="Jane Doe",
            entity_type="person",
            confidence=0.9,
        )


def test_entity_id_must_have_entity_prefix():
    with pytest.raises(ValidationError):
        EntityNode(
            id="jane_doe_1",
            label="Jane Doe",
            entity_type="person",
            confidence=0.9,
        )


def test_topic_id_must_have_concept_prefix():
    with pytest.raises(ValidationError):
        TopicNode(id="ai", label="AI", confidence=0.9)


def test_confidence_out_of_range_rejected():
    with pytest.raises(ValidationError):
        TopicNode(id="concept_ai", label="AI", confidence=1.5)
