"""Tests for opengraph_image.graph."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from opengraph_image.graph import ImageGraph
from opengraph_image.schema import (
    AttributeNode,
    ContainsEdge,
    HasAttributeEdge,
    ImageExtraction,
    ImageNode,
    InSceneEdge,
    ObjectNode,
    RelatedToEdge,
    SceneNode,
)


@pytest.fixture
def two_extractions() -> tuple[ImageExtraction, ImageExtraction]:
    """Two ImageExtractions that share a golden_retriever object and outdoor scene."""
    ext1 = ImageExtraction(
        image=ImageNode(id="img1", path="/photos/img1.jpg", width=800, height=600, format="JPEG"),
        objects=[
            ObjectNode(id="golden_retriever_1", label="golden_retriever", confidence=0.9),
            ObjectNode(id="tennis_ball_1", label="tennis_ball", confidence=0.85),
        ],
        scenes=[
            SceneNode(id="scene_outdoor_1", label="outdoor", confidence=0.88),
        ],
        attributes=[
            AttributeNode(id="attr_warm_1", key="mood", value="warm", confidence=0.7),
        ],
        contains_edges=[
            ContainsEdge(source="img1", target="golden_retriever_1", confidence=0.9),
            ContainsEdge(source="img1", target="tennis_ball_1", confidence=0.85),
        ],
        in_scene_edges=[
            InSceneEdge(source="img1", target="scene_outdoor_1", confidence=0.88),
        ],
        has_attribute_edges=[
            HasAttributeEdge(source="img1", target="attr_warm_1", confidence=0.7),
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

    ext2 = ImageExtraction(
        image=ImageNode(id="img2", path="/photos/img2.jpg", width=1024, height=768, format="JPEG"),
        objects=[
            ObjectNode(id="golden_retriever_1", label="golden_retriever", confidence=0.7),
        ],
        scenes=[
            SceneNode(id="scene_outdoor_1", label="outdoor", confidence=0.82),
        ],
        attributes=[
            AttributeNode(id="attr_warm_1", key="mood", value="warm", confidence=0.65),
        ],
        contains_edges=[
            ContainsEdge(source="img2", target="golden_retriever_1", confidence=0.7),
        ],
        in_scene_edges=[
            InSceneEdge(source="img2", target="scene_outdoor_1", confidence=0.82),
        ],
        has_attribute_edges=[
            HasAttributeEdge(source="img2", target="attr_warm_1", confidence=0.65),
        ],
    )

    return ext1, ext2


def test_add_extraction_creates_scoped_nodes(two_extractions):
    ext1, _ = two_extractions
    g = ImageGraph()
    g.add_extraction(ext1)

    # Image node is not scoped.
    assert "img1" in g._g.nodes
    # Non-image nodes are scoped with the image ID prefix.
    assert "img1__golden_retriever_1" in g._g.nodes
    assert "img1__tennis_ball_1" in g._g.nodes
    assert "img1__scene_outdoor_1" in g._g.nodes

    assert g._g.nodes["img1"]["type"] == "image"
    assert g._g.nodes["img1__golden_retriever_1"]["type"] == "object"
    assert g._g.nodes["img1__scene_outdoor_1"]["type"] == "scene"


def test_add_extraction_edges(two_extractions):
    ext1, _ = two_extractions
    g = ImageGraph()
    g.add_extraction(ext1)

    assert g._g.has_edge("img1", "img1__golden_retriever_1")
    assert g._g.has_edge("img1", "img1__scene_outdoor_1")
    assert g._g.has_edge("img1__golden_retriever_1", "img1__tennis_ball_1")


def test_seen_in_set_on_add(two_extractions):
    ext1, _ = two_extractions
    g = ImageGraph()
    g.add_extraction(ext1)

    assert g._g.nodes["img1"]["seen_in"] == ["img1"]
    assert g._g.nodes["img1__golden_retriever_1"]["seen_in"] == ["img1"]


def test_link_merges_objects(two_extractions):
    ext1, ext2 = two_extractions
    g = ImageGraph()
    g.add_extraction(ext1)
    g.add_extraction(ext2)

    stats = g.link_across_images()

    assert stats["objects_merged"] == 1
    # Canonical is img1 node (confidence 0.9 > 0.7).
    assert "img1__golden_retriever_1" in g._g.nodes
    assert "img2__golden_retriever_1" not in g._g.nodes


def test_link_unions_seen_in(two_extractions):
    ext1, ext2 = two_extractions
    g = ImageGraph()
    g.add_extraction(ext1)
    g.add_extraction(ext2)
    g.link_across_images()

    seen_in = g._g.nodes["img1__golden_retriever_1"]["seen_in"]
    assert set(seen_in) == {"img1", "img2"}


def test_link_repoints_edges(two_extractions):
    ext1, ext2 = two_extractions
    g = ImageGraph()
    g.add_extraction(ext1)
    g.add_extraction(ext2)
    g.link_across_images()

    # img2's contains edge must now point to the canonical node.
    assert g._g.has_edge("img2", "img1__golden_retriever_1")


def test_link_merges_scenes(two_extractions):
    ext1, ext2 = two_extractions
    g = ImageGraph()
    g.add_extraction(ext1)
    g.add_extraction(ext2)

    stats = g.link_across_images()

    assert stats["scenes_merged"] == 1
    outdoor_nodes = [
        n for n, a in g._g.nodes(data=True)
        if a.get("type") == "scene" and a.get("label") == "outdoor"
    ]
    assert len(outdoor_nodes) == 1


def test_link_merges_attributes(two_extractions):
    ext1, ext2 = two_extractions
    g = ImageGraph()
    g.add_extraction(ext1)
    g.add_extraction(ext2)

    stats = g.link_across_images()

    assert stats["attributes_merged"] == 1
    warm_nodes = [
        n for n, a in g._g.nodes(data=True)
        if a.get("type") == "attribute" and a.get("key") == "mood" and a.get("value") == "warm"
    ]
    assert len(warm_nodes) == 1


def test_summary_shape(two_extractions):
    ext1, ext2 = two_extractions
    g = ImageGraph()
    g.add_extraction(ext1)
    g.add_extraction(ext2)
    g.link_across_images()

    s = g.summary()
    assert "total_nodes" in s
    assert "total_edges" in s
    assert "node_count_by_type" in s
    assert "edge_count_by_relation" in s
    assert "god_nodes" in s
    assert "images" in s
    assert set(s["images"]) == {"img1.jpg", "img2.jpg"}
    assert s["node_count_by_type"]["image"] == 2


def test_to_json_and_from_json(two_extractions):
    ext1, ext2 = two_extractions
    g = ImageGraph()
    g.add_extraction(ext1)
    g.add_extraction(ext2)
    g.link_across_images()

    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "graph.json"
        g.to_json(path)

        assert path.exists()
        raw = json.loads(path.read_text())
        assert "nodes" in raw

        g2 = ImageGraph.from_json(path)
        assert g2._g.number_of_nodes() == g._g.number_of_nodes()
        assert g2._g.number_of_edges() == g._g.number_of_edges()
