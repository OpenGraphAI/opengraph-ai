"""Tests for opengraph_text.graph."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from opengraph_text.graph import DocumentGraph
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
)


@pytest.fixture
def two_extractions() -> tuple[DocumentExtraction, DocumentExtraction]:
    """Two DocumentExtractions that share an 'Acme Corp' entity and a topic."""
    ext1 = DocumentExtraction(
        document=DocumentNode(id="doc1", path="/docs/doc1.md", word_count=500, format="md"),
        entities=[
            EntityNode(id="acme_corp", label="Acme Corp", entity_type="organization", confidence=0.9),
            EntityNode(id="jane_doe_1", label="Jane Doe", entity_type="person", confidence=0.85),
        ],
        topics=[
            TopicNode(id="venture_capital", label="venture capital", confidence=0.8),
        ],
        attributes=[
            AttributeNode(id="attr_role_1", key="role", value="CEO", confidence=0.75),
        ],
        claims=[
            ClaimNode(id="claim_funding", text="Acme Corp raised a $10M Series A.", confidence=0.9),
        ],
        contains_edges=[
            ContainsEdge(source="doc1", target="acme_corp", confidence=0.9),
            ContainsEdge(source="doc1", target="jane_doe_1", confidence=0.85),
        ],
        about_topic_edges=[
            AboutTopicEdge(source="doc1", target="venture_capital", confidence=0.8),
        ],
        has_attribute_edges=[
            HasAttributeEdge(source="jane_doe_1", target="attr_role_1", confidence=0.75),
        ],
        states_edges=[
            StatesEdge(source="doc1", target="claim_funding", confidence=0.9),
        ],
        relates_to_edges=[
            RelatesToEdge(source="jane_doe_1", target="acme_corp", relation="works_at", confidence=0.88),
        ],
    )

    ext2 = DocumentExtraction(
        document=DocumentNode(id="doc2", path="/docs/doc2.md", word_count=300, format="md"),
        entities=[
            EntityNode(id="acme_corp_inc_1", label="Acme Corp Inc", entity_type="organization", confidence=0.65),
        ],
        topics=[
            TopicNode(id="venture_capital_2", label="venture capital", confidence=0.7),
        ],
        attributes=[
            AttributeNode(id="attr_role_2", key="role", value="CEO", confidence=0.55),
            AttributeNode(id="attr_industry_1", key="industry", value="fintech", confidence=0.6),
        ],
        contains_edges=[
            ContainsEdge(source="doc2", target="acme_corp_inc_1", confidence=0.65),
        ],
        about_topic_edges=[
            AboutTopicEdge(source="doc2", target="venture_capital_2", confidence=0.7),
        ],
        has_attribute_edges=[
            HasAttributeEdge(source="doc2", target="attr_role_2", confidence=0.55),
            HasAttributeEdge(source="doc2", target="attr_industry_1", confidence=0.6),
        ],
    )

    return ext1, ext2


def test_add_extraction_creates_scoped_nodes(two_extractions):
    ext1, _ = two_extractions
    g = DocumentGraph()
    g.add_extraction(ext1)

    # Document node is not scoped.
    assert "doc1" in g._g.nodes
    # Non-document nodes are scoped with the document ID prefix.
    assert "doc1__acme_corp" in g._g.nodes
    assert "doc1__jane_doe_1" in g._g.nodes
    assert "doc1__venture_capital" in g._g.nodes
    assert "doc1__attr_role_1" in g._g.nodes
    assert "doc1__claim_funding" in g._g.nodes

    assert g._g.nodes["doc1"]["type"] == "document"
    assert g._g.nodes["doc1__acme_corp"]["type"] == "entity"
    assert g._g.nodes["doc1__venture_capital"]["type"] == "topic"
    assert g._g.nodes["doc1__attr_role_1"]["type"] == "attribute"
    assert g._g.nodes["doc1__claim_funding"]["type"] == "claim"


def test_add_extraction_edges(two_extractions):
    ext1, _ = two_extractions
    g = DocumentGraph()
    g.add_extraction(ext1)

    assert g._g.has_edge("doc1", "doc1__acme_corp")
    assert g._g.has_edge("doc1", "doc1__venture_capital")
    assert g._g.has_edge("doc1", "doc1__claim_funding")
    assert g._g.has_edge("doc1__jane_doe_1", "doc1__attr_role_1")
    assert g._g.has_edge("doc1__jane_doe_1", "doc1__acme_corp")


def test_seen_in_set_on_add(two_extractions):
    ext1, _ = two_extractions
    g = DocumentGraph()
    g.add_extraction(ext1)

    assert g._g.nodes["doc1"]["seen_in"] == ["doc1"]
    assert g._g.nodes["doc1__acme_corp"]["seen_in"] == ["doc1"]


def test_link_merges_entities(two_extractions):
    ext1, ext2 = two_extractions
    g = DocumentGraph()
    g.add_extraction(ext1)
    g.add_extraction(ext2)

    stats = g.link_across_documents()

    assert stats["entities_merged"] == 1
    # Canonical is the doc1 node (confidence 0.9 > 0.65).
    assert "doc1__acme_corp" in g._g.nodes
    assert "doc2__acme_corp_inc_1" not in g._g.nodes


def test_link_unions_seen_in(two_extractions):
    ext1, ext2 = two_extractions
    g = DocumentGraph()
    g.add_extraction(ext1)
    g.add_extraction(ext2)
    g.link_across_documents()

    seen_in = g._g.nodes["doc1__acme_corp"]["seen_in"]
    assert set(seen_in) == {"doc1", "doc2"}


def test_link_repoints_edges(two_extractions):
    ext1, ext2 = two_extractions
    g = DocumentGraph()
    g.add_extraction(ext1)
    g.add_extraction(ext2)
    g.link_across_documents()

    # doc2's contains edge must now point to the canonical node.
    assert g._g.has_edge("doc2", "doc1__acme_corp")


def test_link_merges_topics(two_extractions):
    ext1, ext2 = two_extractions
    g = DocumentGraph()
    g.add_extraction(ext1)
    g.add_extraction(ext2)

    stats = g.link_across_documents()

    assert stats["topics_merged"] == 1
    topic_nodes = [
        n for n, a in g._g.nodes(data=True) if a.get("type") == "topic" and a.get("label") == "venture capital"
    ]
    assert len(topic_nodes) == 1


def test_link_merges_attributes(two_extractions):
    ext1, ext2 = two_extractions
    g = DocumentGraph()
    g.add_extraction(ext1)
    g.add_extraction(ext2)

    stats = g.link_across_documents()

    assert stats["attributes_merged"] == 1
    role_nodes = [
        n for n, a in g._g.nodes(data=True) if a.get("type") == "attribute" and a.get("key") == "role"
    ]
    assert len(role_nodes) == 1


def test_summary_shape(two_extractions):
    ext1, ext2 = two_extractions
    g = DocumentGraph()
    g.add_extraction(ext1)
    g.add_extraction(ext2)
    g.link_across_documents()

    s = g.summary()
    assert "total_nodes" in s
    assert "total_edges" in s
    assert "node_count_by_type" in s
    assert "edge_count_by_relation" in s
    assert "god_nodes" in s
    assert "documents" in s
    assert set(s["documents"]) == {"doc1.md", "doc2.md"}
    assert s["node_count_by_type"]["document"] == 2

    # Document nodes must be excluded from the god_nodes ranking.
    god_node_ids = {node["id"] for node in s["god_nodes"]}
    assert "doc1" not in god_node_ids
    assert "doc2" not in god_node_ids


def test_to_json_and_from_json(two_extractions):
    ext1, ext2 = two_extractions
    g = DocumentGraph()
    g.add_extraction(ext1)
    g.add_extraction(ext2)
    g.link_across_documents()

    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "graph.json"
        g.to_json(path)

        assert path.exists()
        raw = json.loads(path.read_text())
        assert "nodes" in raw

        g2 = DocumentGraph.from_json(path)
        assert g2._g.number_of_nodes() == g._g.number_of_nodes()
        assert g2._g.number_of_edges() == g._g.number_of_edges()
