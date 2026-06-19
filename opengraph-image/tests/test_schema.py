"""Tests for opengraph_image.schema — node models and validate_extraction."""

import pytest
from pydantic import ValidationError

from opengraph_image.schema import (
    AttributeNode,
    ContainsEdge,
    HasAttributeEdge,
    HasTextEdge,
    ImageExtraction,
    ImageNode,
    InSceneEdge,
    ObjectNode,
    RelatedToEdge,
    SceneNode,
    TextSpanNode,
    validate_extraction,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _valid_extraction() -> ImageExtraction:
    """Build a small but complete ImageExtraction that should pass validation."""
    image = ImageNode(id="img_park", path="/photos/park.jpg", width=1920, height=1080, format="JPEG")
    dog = ObjectNode(id="golden_retriever_1", label="golden retriever", confidence=0.97)
    person = ObjectNode(
        id="person_1",
        label="person",
        confidence=0.91,
        bounding_box=[0.1, 0.05, 0.3, 0.6],
    )
    scene = SceneNode(id="scene_outdoor", label="outdoor", confidence=0.88)
    attr_warm = AttributeNode(id="attr_warm_lighting", key="lighting", value="warm", confidence=0.75)
    span = TextSpanNode(id="text_no_dogs", text="No Dogs Allowed", confidence=0.99)

    return ImageExtraction(
        image=image,
        objects=[dog, person],
        scenes=[scene],
        attributes=[attr_warm],
        text_spans=[span],
        contains_edges=[
            ContainsEdge(source="img_park", target="golden_retriever_1", confidence=0.97),
            ContainsEdge(source="img_park", target="person_1", confidence=0.91),
        ],
        in_scene_edges=[InSceneEdge(source="img_park", target="scene_outdoor", confidence=0.88)],
        has_attribute_edges=[
            HasAttributeEdge(source="img_park", target="attr_warm_lighting", confidence=0.75)
        ],
        has_text_edges=[HasTextEdge(source="img_park", target="text_no_dogs", confidence=0.99)],
        related_to_edges=[
            RelatedToEdge(
                source="person_1",
                target="golden_retriever_1",
                relation="next_to",
                confidence=0.80,
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

    def test_image_node_fields(self) -> None:
        ext = _valid_extraction()
        assert ext.image.id == "img_park"
        assert ext.image.width == 1920
        assert ext.image.format == "JPEG"

    def test_object_bounding_box(self) -> None:
        ext = _valid_extraction()
        person = next(o for o in ext.objects if o.id == "person_1")
        assert person.bounding_box == [0.1, 0.05, 0.3, 0.6]

    def test_object_no_bounding_box(self) -> None:
        ext = _valid_extraction()
        dog = next(o for o in ext.objects if o.id == "golden_retriever_1")
        assert dog.bounding_box is None

    def test_scene_label(self) -> None:
        ext = _valid_extraction()
        assert ext.scenes[0].label == "outdoor"

    def test_attribute_key(self) -> None:
        ext = _valid_extraction()
        assert ext.attributes[0].key == "lighting"

    def test_related_to_edge_relation(self) -> None:
        ext = _valid_extraction()
        assert ext.related_to_edges[0].relation == "next_to"


# ---------------------------------------------------------------------------
# Invalid extractions
# ---------------------------------------------------------------------------

class TestInvalidExtraction:
    def test_unknown_edge_target(self) -> None:
        ext = _valid_extraction()
        ext.contains_edges.append(
            ContainsEdge(source="img_park", target="ghost_node", confidence=0.5)
        )
        errors = validate_extraction(ext)
        assert any("ghost_node" in e for e in errors), errors

    def test_unknown_edge_source(self) -> None:
        ext = _valid_extraction()
        ext.has_text_edges.append(
            HasTextEdge(source="nonexistent_image", target="text_no_dogs", confidence=0.9)
        )
        errors = validate_extraction(ext)
        assert any("nonexistent_image" in e for e in errors), errors

    def test_duplicate_node_ids(self) -> None:
        ext = _valid_extraction()
        # Add an ObjectNode with the same id as the image node.
        ext.objects.append(
            ObjectNode(id="img_park", label="duplicate", confidence=0.5)
        )
        errors = validate_extraction(ext)
        assert any("img_park" in e for e in errors), errors

    def test_multiple_errors_collected(self) -> None:
        ext = _valid_extraction()
        ext.contains_edges.append(
            ContainsEdge(source="bad_src", target="bad_tgt", confidence=0.5)
        )
        errors = validate_extraction(ext)
        assert len(errors) >= 2

    def test_invalid_scene_label_raises(self) -> None:
        with pytest.raises(ValidationError):
            SceneNode(id="s1", label="space", confidence=0.5)  # type: ignore[arg-type]

    def test_invalid_attribute_key_raises(self) -> None:
        with pytest.raises(ValidationError):
            AttributeNode(id="a1", key="texture", value="rough", confidence=0.6)  # type: ignore[arg-type]

    def test_confidence_out_of_range_raises(self) -> None:
        with pytest.raises(ValidationError):
            ObjectNode(id="obj1", label="cat", confidence=1.5)

    def test_bounding_box_wrong_length_raises(self) -> None:
        with pytest.raises(ValidationError):
            ObjectNode(id="obj1", label="cat", confidence=0.9, bounding_box=[0.1, 0.2])

    def test_bounding_box_out_of_range_raises(self) -> None:
        with pytest.raises(ValidationError):
            ObjectNode(id="obj1", label="cat", confidence=0.9, bounding_box=[0.1, 0.2, 1.5, 0.3])

    def test_image_zero_width_raises(self) -> None:
        with pytest.raises(ValidationError):
            ImageNode(id="img1", path="/a.jpg", width=0, height=100, format="PNG")
