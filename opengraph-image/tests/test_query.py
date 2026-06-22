"""Tests for opengraph_image.query."""

from __future__ import annotations

import os

import anthropic
import pytest

from opengraph_image.graph import ImageGraph
from opengraph_image.query import (
    filter_images_by_attribute,
    find_images_containing,
    find_nodes_by_label,
    find_nodes_by_type,
    find_path,
    get_neighbors,
    query_graph,
)
from opengraph_image.schema import (
    AttributeNode,
    ContainsEdge,
    HasAttributeEdge,
    ImageExtraction,
    ImageNode,
    InSceneEdge,
    ObjectNode,
    QueryResult,
    RelatedToEdge,
    SceneNode,
)


@pytest.fixture
def small_graph() -> ImageGraph:
    """A tiny hand-built graph: one image with a dog and a ball, outdoors, warm mood."""
    extraction = ImageExtraction(
        image=ImageNode(id="park_photo", path="/photos/park_photo.jpg", width=800, height=600, format="JPEG"),
        objects=[
            ObjectNode(id="golden_retriever_1", label="golden_retriever", confidence=0.9),
            ObjectNode(id="tennis_ball_1", label="tennis_ball", confidence=0.85),
        ],
        scenes=[
            SceneNode(id="scene_outdoor_1", label="outdoor", confidence=0.9),
        ],
        attributes=[
            AttributeNode(id="attr_warm_1", key="mood", value="warm", confidence=0.7),
        ],
        contains_edges=[
            ContainsEdge(source="park_photo", target="golden_retriever_1", confidence=0.9),
            ContainsEdge(source="park_photo", target="tennis_ball_1", confidence=0.85),
        ],
        in_scene_edges=[
            InSceneEdge(source="park_photo", target="scene_outdoor_1", confidence=0.9),
        ],
        has_attribute_edges=[
            HasAttributeEdge(source="park_photo", target="attr_warm_1", confidence=0.7),
        ],
        related_to_edges=[
            RelatedToEdge(
                source="golden_retriever_1",
                target="tennis_ball_1",
                relation="next_to",
                confidence=0.75,
            ),
        ],
    )
    g = ImageGraph()
    g.add_extraction(extraction)
    g.link_across_images()
    return g


def test_find_nodes_by_label(small_graph: ImageGraph) -> None:
    matches = find_nodes_by_label(small_graph, "retriever")
    assert len(matches) == 1
    assert matches[0]["label"] == "golden_retriever"


def test_find_nodes_by_label_filtered_by_type(small_graph: ImageGraph) -> None:
    matches = find_nodes_by_label(small_graph, "warm", node_type="attribute")
    assert len(matches) == 1
    assert matches[0]["value"] == "warm"

    no_matches = find_nodes_by_label(small_graph, "warm", node_type="object")
    assert no_matches == []


def test_find_nodes_by_type(small_graph: ImageGraph) -> None:
    objects = find_nodes_by_type(small_graph, "object")
    labels = {n["label"] for n in objects}
    assert labels == {"golden_retriever", "tennis_ball"}


def test_get_neighbors(small_graph: ImageGraph) -> None:
    result = get_neighbors(small_graph, "golden_retriever", depth=1)
    node_ids = {n["id"] for n in result["nodes"]}
    assert "park_photo__golden_retriever_1" in node_ids
    assert "park_photo__tennis_ball_1" in node_ids
    assert "park_photo" in node_ids


def test_find_images_containing(small_graph: ImageGraph) -> None:
    images = find_images_containing(small_graph, ["golden_retriever", "tennis_ball"])
    assert images == ["park_photo"]

    no_images = find_images_containing(small_graph, ["golden_retriever", "skateboard"])
    assert no_images == []


def test_find_path(small_graph: ImageGraph) -> None:
    paths = find_path(small_graph, "golden_retriever", "tennis_ball", max_hops=4)
    assert len(paths) > 0
    assert paths[0][0] == "park_photo__golden_retriever_1"
    assert paths[0][-1] == "park_photo__tennis_ball_1"


def test_filter_images_by_attribute(small_graph: ImageGraph) -> None:
    images = filter_images_by_attribute(small_graph, "mood", "warm")
    assert images == ["park_photo"]

    no_images = filter_images_by_attribute(small_graph, "mood", "gloomy")
    assert no_images == []


@pytest.fixture(scope="module")
def client() -> anthropic.Anthropic:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        pytest.skip("ANTHROPIC_API_KEY not set")
    return anthropic.Anthropic(api_key=api_key)


def test_query_graph_simple_question(small_graph: ImageGraph, client: anthropic.Anthropic) -> None:
    """An end-to-end query against the real model should mention the dog and the image."""
    result = query_graph(small_graph, "What objects are in park_photo?", client)

    assert isinstance(result, QueryResult)
    assert result.summary
    assert "park_photo" in result.summary or "golden_retriever" in result.summary.lower()
    assert len(result.primitives_used) > 0
    assert len(result.matched_node_ids) > 0
