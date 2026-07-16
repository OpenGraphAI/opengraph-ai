"""Tests for opengraph_text.query."""

from __future__ import annotations

import os

import anthropic
import pytest

from opengraph_text.graph import DocumentGraph
from opengraph_text.query import (
    filter_documents_by_topic,
    find_documents_mentioning,
    find_nodes_by_label,
    find_nodes_by_type,
    find_path,
    get_neighbors,
    query_graph,
)
from opengraph_text.schema import (
    AboutTopicEdge,
    AttributeNode,
    ClaimNode,
    ContainsEdge,
    DocumentExtraction,
    DocumentNode,
    EntityNode,
    HasAttributeEdge,
    QueryResult,
    RelatesToEdge,
    StatesEdge,
    TopicNode,
)


@pytest.fixture
def small_graph() -> DocumentGraph:
    """A tiny hand-built graph: one document mentioning Acme Corp and Jane Doe."""
    extraction = DocumentExtraction(
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
    g = DocumentGraph()
    g.add_extraction(extraction)
    g.link_across_documents()
    return g


def test_find_nodes_by_label(small_graph: DocumentGraph) -> None:
    matches = find_nodes_by_label(small_graph, "jane")
    assert len(matches) == 1
    assert matches[0]["label"] == "Jane Doe"


def test_find_nodes_by_label_filtered_by_type(small_graph: DocumentGraph) -> None:
    matches = find_nodes_by_label(small_graph, "ceo", node_type="attribute")
    assert len(matches) == 1
    assert matches[0]["value"] == "CEO"

    no_matches = find_nodes_by_label(small_graph, "ceo", node_type="entity")
    assert no_matches == []


def test_find_nodes_by_type(small_graph: DocumentGraph) -> None:
    entities = find_nodes_by_type(small_graph, "entity")
    labels = {n["label"] for n in entities}
    assert labels == {"Acme Corp", "Jane Doe"}


def test_get_neighbors(small_graph: DocumentGraph) -> None:
    result = get_neighbors(small_graph, "Jane Doe", depth=1)
    node_ids = {n["id"] for n in result["nodes"]}
    assert "doc1__jane_doe_1" in node_ids
    assert "doc1__acme_corp" in node_ids
    assert "doc1" in node_ids


def test_find_documents_mentioning(small_graph: DocumentGraph) -> None:
    docs = find_documents_mentioning(small_graph, ["Acme Corp", "Jane Doe"])
    assert docs == ["doc1"]

    no_docs = find_documents_mentioning(small_graph, ["Acme Corp", "Fintaro"])
    assert no_docs == []


def test_find_path(small_graph: DocumentGraph) -> None:
    paths = find_path(small_graph, "Jane Doe", "Acme Corp", max_hops=4)
    assert len(paths) > 0
    assert paths[0][0] == "doc1__jane_doe_1"
    assert paths[0][-1] == "doc1__acme_corp"


def test_filter_documents_by_topic(small_graph: DocumentGraph) -> None:
    docs = filter_documents_by_topic(small_graph, "venture")
    assert docs == ["doc1"]

    no_docs = filter_documents_by_topic(small_graph, "climate")
    assert no_docs == []


@pytest.fixture(scope="module")
def client() -> anthropic.Anthropic:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        pytest.skip("ANTHROPIC_API_KEY not set")
    return anthropic.Anthropic(api_key=api_key)


def test_query_graph_simple_question(small_graph: DocumentGraph, client: anthropic.Anthropic) -> None:
    """An end-to-end query against the real model should mention Acme Corp or doc1."""
    result = query_graph(small_graph, "What entities are mentioned in doc1?", client)

    assert isinstance(result, QueryResult)
    assert result.summary
    assert "doc1" in result.summary or "acme corp" in result.summary.lower()
    assert len(result.primitives_used) > 0
    assert len(result.matched_node_ids) > 0
