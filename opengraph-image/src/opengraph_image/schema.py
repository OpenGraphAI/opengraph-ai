"""Pydantic models for image metadata, graph nodes, and MCP tool I/O."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, Field, field_validator


# ---------------------------------------------------------------------------
# Node models
# ---------------------------------------------------------------------------

class ImageNode(BaseModel):
    """Root node representing a single image file in the knowledge graph.

    Acts as the anchor to which all extracted objects, scenes, attributes,
    and text spans are connected via edges.
    """

    id: str = Field(description="Unique identifier derived from the image filename.")
    path: str = Field(description="Absolute or relative filesystem path to the image.")
    width: int = Field(gt=0, description="Image width in pixels.")
    height: int = Field(gt=0, description="Image height in pixels.")
    format: str = Field(description="Image format string, e.g. 'JPEG', 'PNG'.")


class ObjectNode(BaseModel):
    """A detected physical object within an image.

    The ``id`` uses snake_case of the label with a numeric suffix when the
    same label appears more than once in an extraction, e.g.
    ``golden_retriever_1``, ``golden_retriever_2``.
    """

    id: str = Field(description="Unique snake_case label, disambiguated with a numeric suffix when duplicated.")
    label: str = Field(description="Human-readable object class, e.g. 'golden_retriever'.")
    confidence: Annotated[float, Field(ge=0.0, le=1.0)] = Field(
        description="Detection confidence in the range [0, 1]."
    )
    bounding_box: list[float] | None = Field(
        default=None,
        description="Normalized [x, y, w, h] bounding box in the range [0, 1], or None if unavailable.",
    )

    @field_validator("bounding_box")
    @classmethod
    def _validate_bbox(cls, v: list[float] | None) -> list[float] | None:
        if v is None:
            return v
        if len(v) != 4:
            raise ValueError("bounding_box must have exactly 4 elements [x, y, w, h]")
        if not all(0.0 <= c <= 1.0 for c in v):
            raise ValueError("bounding_box coordinates must be normalized to [0, 1]")
        return v


SceneLabel = Literal[
    "outdoor",
    "indoor_residential",
    "indoor_commercial",
    "indoor_other",
    "vehicle",
    "mixed",
]


class SceneNode(BaseModel):
    """The dominant scene context of the image.

    Only one of the controlled ``SceneLabel`` values is permitted so that
    scene nodes remain comparable across extractions.
    """

    id: str = Field(description="Unique identifier for this scene node.")
    label: SceneLabel = Field(description="Controlled-vocabulary scene category.")
    confidence: Annotated[float, Field(ge=0.0, le=1.0)] = Field(
        description="Classification confidence in the range [0, 1]."
    )


AttributeKey = Literal["color", "material", "mood", "lighting", "style", "size"]


class AttributeNode(BaseModel):
    """A key/value visual attribute that can be attached to an image or object.

    Keys are restricted to a controlled vocabulary so attributes remain
    query-able without free-text search.
    """

    id: str = Field(description="Unique identifier for this attribute node.")
    key: AttributeKey = Field(description="Controlled-vocabulary attribute key.")
    value: str = Field(description="Free-text attribute value, e.g. 'warm', 'red', 'minimalist'.")
    confidence: Annotated[float, Field(ge=0.0, le=1.0)] = Field(
        description="Confidence in the range [0, 1]."
    )


class TextSpanNode(BaseModel):
    """A span of text detected inside the image (OCR output).

    Multiple text spans may exist for a single image; each is a separate node
    so that individual spans can carry independent confidence scores.
    """

    id: str = Field(description="Unique identifier for this text span node.")
    text: str = Field(description="The raw OCR-detected text string.")
    confidence: Annotated[float, Field(ge=0.0, le=1.0)] = Field(
        description="OCR confidence in the range [0, 1]."
    )


# ---------------------------------------------------------------------------
# Edge models
# ---------------------------------------------------------------------------

class ContainsEdge(BaseModel):
    """Connects an ImageNode to an ObjectNode it contains.

    Represents the spatial relationship: this image *contains* this object.
    """

    source: str = Field(description="ID of the source ImageNode.")
    target: str = Field(description="ID of the target ObjectNode.")
    confidence: Annotated[float, Field(ge=0.0, le=1.0)] = Field(
        description="Edge confidence in the range [0, 1]."
    )


class InSceneEdge(BaseModel):
    """Connects an ImageNode to the SceneNode describing its context.

    Each image should have at most one InSceneEdge in a well-formed extraction.
    """

    source: str = Field(description="ID of the source ImageNode.")
    target: str = Field(description="ID of the target SceneNode.")
    confidence: Annotated[float, Field(ge=0.0, le=1.0)] = Field(
        description="Edge confidence in the range [0, 1]."
    )


class HasAttributeEdge(BaseModel):
    """Connects an ImageNode or ObjectNode to an AttributeNode.

    The ``source`` may be either an image ID or an object ID, allowing
    attributes to describe the whole image or a specific detected object.
    """

    source: str = Field(description="ID of the source ImageNode or ObjectNode.")
    target: str = Field(description="ID of the target AttributeNode.")
    confidence: Annotated[float, Field(ge=0.0, le=1.0)] = Field(
        description="Edge confidence in the range [0, 1]."
    )


class HasTextEdge(BaseModel):
    """Connects an ImageNode to a TextSpanNode found within it."""

    source: str = Field(description="ID of the source ImageNode.")
    target: str = Field(description="ID of the target TextSpanNode.")
    confidence: Annotated[float, Field(ge=0.0, le=1.0)] = Field(
        description="Edge confidence in the range [0, 1]."
    )


RelationType = Literal[
    "next_to",
    "holding",
    "wearing",
    "on_top_of",
    "inside",
    "behind",
    "in_front_of",
]


class RelatedToEdge(BaseModel):
    """Expresses a spatial or semantic relationship between two ObjectNodes.

    Both ``source`` and ``target`` must be object IDs.  The ``relation``
    field is a controlled vocabulary so that relationships are machine-readable.
    """

    source: str = Field(description="ID of the source ObjectNode.")
    target: str = Field(description="ID of the target ObjectNode.")
    relation: RelationType = Field(description="Controlled-vocabulary relationship type.")
    confidence: Annotated[float, Field(ge=0.0, le=1.0)] = Field(
        description="Edge confidence in the range [0, 1]."
    )


# ---------------------------------------------------------------------------
# Container model
# ---------------------------------------------------------------------------

class ImageExtraction(BaseModel):
    """Complete knowledge-graph extraction for a single image.

    Bundles all nodes and edges produced by the extraction pipeline so that
    they can be serialised, stored, and validated as a self-contained unit.
    """

    image: ImageNode
    objects: list[ObjectNode] = Field(default_factory=list)
    scenes: list[SceneNode] = Field(default_factory=list)
    attributes: list[AttributeNode] = Field(default_factory=list)
    text_spans: list[TextSpanNode] = Field(default_factory=list)
    contains_edges: list[ContainsEdge] = Field(default_factory=list)
    in_scene_edges: list[InSceneEdge] = Field(default_factory=list)
    has_attribute_edges: list[HasAttributeEdge] = Field(default_factory=list)
    has_text_edges: list[HasTextEdge] = Field(default_factory=list)
    related_to_edges: list[RelatedToEdge] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate_extraction(extraction: ImageExtraction) -> list[str]:
    """Validate referential integrity of an ImageExtraction.

    Checks:
    - All node IDs are unique across the extraction.
    - Every edge source/target references an existing node ID.

    Returns a list of human-readable error strings; the list is empty when
    the extraction is valid.
    """
    errors: list[str] = []

    # Collect all node IDs and detect duplicates.
    all_nodes: dict[str, str] = {}  # id -> node type

    def _register(node_id: str, node_type: str) -> None:
        if node_id in all_nodes:
            errors.append(
                f"Duplicate node ID '{node_id}': appears as both "
                f"{all_nodes[node_id]} and {node_type}."
            )
        else:
            all_nodes[node_id] = node_type

    _register(extraction.image.id, "ImageNode")
    for obj in extraction.objects:
        _register(obj.id, "ObjectNode")
    for scene in extraction.scenes:
        _register(scene.id, "SceneNode")
    for attr in extraction.attributes:
        _register(attr.id, "AttributeNode")
    for span in extraction.text_spans:
        _register(span.id, "TextSpanNode")

    known_ids = set(all_nodes)

    def _check_edge(edge_type: str, source: str, target: str) -> None:
        if source not in known_ids:
            errors.append(
                f"{edge_type} references unknown source '{source}'."
            )
        if target not in known_ids:
            errors.append(
                f"{edge_type} references unknown target '{target}'."
            )

    for edge in extraction.contains_edges:
        _check_edge("ContainsEdge", edge.source, edge.target)
    for edge in extraction.in_scene_edges:
        _check_edge("InSceneEdge", edge.source, edge.target)
    for edge in extraction.has_attribute_edges:
        _check_edge("HasAttributeEdge", edge.source, edge.target)
    for edge in extraction.has_text_edges:
        _check_edge("HasTextEdge", edge.source, edge.target)
    for edge in extraction.related_to_edges:
        _check_edge("RelatedToEdge", edge.source, edge.target)

    return errors
