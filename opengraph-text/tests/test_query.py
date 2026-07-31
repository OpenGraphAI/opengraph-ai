"""Tests for opengraph_text.query."""

import anthropic

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
    ContainsEdge,
    DocumentExtraction,
    DocumentNode,
    EntityNode,
    HasAttributeEdge,
    QueryResult,
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
            EntityNode(
                id="entity_acme_corp_inc_2",
                label="Acme Corp Inc",
                entity_type="organization",
                confidence=0.95,
            ),
        ],
        topics=[
            TopicNode(id="concept_vc", label="venture capital", confidence=0.6),
        ],
        contains_edges=[
            ContainsEdge(source="acme_news", target="entity_acme_corp_inc_2", confidence=0.95),
        ],
        about_topic_edges=[
            AboutTopicEdge(source="acme_news", target="concept_vc", confidence=0.6),
        ],
    )


def _build_graph() -> DocumentGraph:
    graph = DocumentGraph()
    graph.add_extraction(_acme_pitch_extraction())
    graph.add_extraction(_acme_news_extraction())
    graph.link_across_documents()
    return graph


def test_find_nodes_by_label_is_fuzzy_and_case_insensitive():
    graph = _build_graph()

    matches = find_nodes_by_label(graph, "jane")

    assert any(m["label"] == "Jane Doe" for m in matches)


def test_find_nodes_by_label_respects_node_type_filter():
    graph = _build_graph()

    matches = find_nodes_by_label(graph, "venture", node_type="topic")

    assert matches
    assert all(m["type"] == "topic" for m in matches)


def test_find_nodes_by_type_returns_all_entities():
    graph = _build_graph()

    matches = find_nodes_by_type(graph, "entity")

    assert {m["label"] for m in matches} == {"Jane Doe", "Acme Corp Inc"}


def test_get_neighbors_includes_connected_nodes():
    graph = _build_graph()
    jane_id = next(
        n for n, d in graph.graph.nodes(data=True) if d.get("label") == "Jane Doe"
    )

    result = get_neighbors(graph, jane_id, depth=1)

    node_ids = {n["id"] for n in result["nodes"]}
    assert jane_id in node_ids
    assert "acme_pitch" in node_ids


def test_find_documents_mentioning_requires_all_labels():
    graph = _build_graph()

    both = find_documents_mentioning(graph, ["Acme", "Jane"])
    assert both == ["acme_pitch"]

    acme_only = find_documents_mentioning(graph, ["Acme"])
    assert sorted(acme_only) == ["acme_news", "acme_pitch"]


def test_find_path_between_document_and_entity():
    graph = _build_graph()
    jane_id = next(
        n for n, d in graph.graph.nodes(data=True) if d.get("label") == "Jane Doe"
    )

    paths = find_path(graph, "acme_pitch", jane_id)

    assert paths
    assert all(path[0] == "acme_pitch" and path[-1] == jane_id for path in paths)


def test_filter_documents_by_topic_merges_across_documents():
    graph = _build_graph()

    docs = filter_documents_by_topic(graph, "venture capital")

    assert sorted(docs) == ["acme_news", "acme_pitch"]


def test_query_graph_answers_simple_question():
    graph = _build_graph()
    client = anthropic.Anthropic()

    result = query_graph(graph, "Which documents mention Acme Corp?", client)

    assert isinstance(result, QueryResult)
    assert result.summary
    assert result.primitives_used
    assert result.matched_node_ids
    assert "acme" in result.summary.lower()
