"""Tests for opengraph_text.graph."""

from pathlib import Path

import pytest

from opengraph_text.graph import DocumentGraph
from opengraph_text.schema import (
    AboutTopicEdge,
    AttributeNode,
    ContainsEdge,
    DocumentExtraction,
    DocumentNode,
    EntityNode,
    HasAttributeEdge,
    RelatesToEdge,
    TopicNode,
)


def _acme_pitch_extraction() -> DocumentExtraction:
    return DocumentExtraction(
        document=DocumentNode(
            id="acme_pitch",
            path="/docs/acme_pitch.txt",
            word_count=500,
            format="txt",
        ),
        entities=[
            EntityNode(
                id="entity_acme_corp_1", label="Acme Corp", entity_type="organization", confidence=0.9
            ),
            EntityNode(
                id="entity_jane_doe_1", label="Jane Doe", entity_type="person", confidence=0.85
            ),
        ],
        topics=[
            TopicNode(id="concept_venture_capital", label="Venture Capital", confidence=0.8),
        ],
        attributes=[
            AttributeNode(id="attr_acme_industry", key="industry", value="Software", confidence=0.7),
        ],
        contains_edges=[
            ContainsEdge(source="acme_pitch", target="entity_acme_corp_1", confidence=0.9),
            ContainsEdge(source="acme_pitch", target="entity_jane_doe_1", confidence=0.9),
        ],
        about_topic_edges=[
            AboutTopicEdge(source="acme_pitch", target="concept_venture_capital", confidence=0.8),
        ],
        has_attribute_edges=[
            HasAttributeEdge(source="entity_acme_corp_1", target="attr_acme_industry", confidence=0.7),
        ],
        relates_to_edges=[
            RelatesToEdge(
                source="entity_jane_doe_1", target="entity_acme_corp_1", relation="works_at", confidence=0.9
            ),
        ],
    )


def _acme_news_extraction() -> DocumentExtraction:
    return DocumentExtraction(
        document=DocumentNode(
            id="acme_news",
            path="/docs/acme_news.txt",
            word_count=300,
            format="txt",
        ),
        entities=[
            # Same real-world entity as "Acme Corp" above, but with a
            # different id and a trailing "_2" disambiguator + higher confidence.
            EntityNode(
                id="entity_acme_corp_inc_2",
                label="Acme Corp Inc",
                entity_type="organization",
                confidence=0.95,
            ),
        ],
        topics=[
            # Same topic, different id/label casing.
            TopicNode(id="concept_vc", label="venture capital", confidence=0.6),
        ],
        contains_edges=[
            ContainsEdge(source="acme_news", target="entity_acme_corp_inc_2", confidence=0.95),
        ],
        about_topic_edges=[
            AboutTopicEdge(source="acme_news", target="concept_vc", confidence=0.6),
        ],
    )


def test_link_across_documents_merges_shared_entity_and_topic():
    graph = DocumentGraph()
    graph.add_extraction(_acme_pitch_extraction())
    graph.add_extraction(_acme_news_extraction())

    stats = graph.link_across_documents()

    assert stats == {"entities_merged": 1, "topics_merged": 1, "attributes_merged": 0}

    entity_nodes = [
        (n, d) for n, d in graph.graph.nodes(data=True) if d.get("type") == "entity"
    ]
    assert len(entity_nodes) == 2  # acme_corp (merged) + jane_doe

    acme_node_id, acme_data = next(
        (n, d) for n, d in entity_nodes if d["entity_type"] == "organization"
    )
    # The higher-confidence extraction (0.95) should have won as canonical.
    assert acme_data["confidence"] == 0.95
    assert sorted(acme_data["seen_in"]) == ["acme_news", "acme_pitch"]

    topic_nodes = [
        (n, d) for n, d in graph.graph.nodes(data=True) if d.get("type") == "topic"
    ]
    assert len(topic_nodes) == 1
    topic_id, topic_data = topic_nodes[0]
    assert sorted(topic_data["seen_in"]) == ["acme_news", "acme_pitch"]

    # Edges from both documents should now point at the merged canonical node.
    assert graph.graph.has_edge("acme_pitch", acme_node_id)
    assert graph.graph.has_edge("acme_news", acme_node_id)
    assert graph.graph.has_edge("acme_pitch", topic_id)
    assert graph.graph.has_edge("acme_news", topic_id)

    # relates_to and has_attribute edges should be re-pointed to the canonical entity.
    jane_id = next(n for n, d in entity_nodes if d["entity_type"] == "person")
    assert graph.graph.has_edge(jane_id, acme_node_id)
    edge_data = graph.graph.get_edge_data(jane_id, acme_node_id)
    assert any(d["relation"] == "works_at" for d in edge_data.values())


def test_summary_excludes_documents_from_god_nodes():
    graph = DocumentGraph()
    graph.add_extraction(_acme_pitch_extraction())
    graph.add_extraction(_acme_news_extraction())
    graph.link_across_documents()

    summary = graph.summary()

    assert summary["total_nodes"] == graph.graph.number_of_nodes()
    assert summary["total_edges"] == graph.graph.number_of_edges()
    assert sorted(summary["documents"]) == ["acme_news", "acme_pitch"]
    assert all(node["type"] != "document" for node in summary["god_nodes"])
    assert summary["node_count_by_type"]["document"] == 2


def test_to_json_and_from_json_round_trip(tmp_path: Path):
    graph = DocumentGraph()
    graph.add_extraction(_acme_pitch_extraction())
    graph.add_extraction(_acme_news_extraction())
    graph.link_across_documents()

    out_path = tmp_path / "graph.json"
    graph.to_json(out_path)

    loaded = DocumentGraph.from_json(out_path)

    assert loaded.graph.number_of_nodes() == graph.graph.number_of_nodes()
    assert loaded.graph.number_of_edges() == graph.graph.number_of_edges()
    assert loaded.summary() == graph.summary()


def test_link_across_documents_no_merge_needed_returns_zero_stats():
    graph = DocumentGraph()
    graph.add_extraction(_acme_pitch_extraction())

    stats = graph.link_across_documents()

    assert stats == {"entities_merged": 0, "topics_merged": 0, "attributes_merged": 0}
