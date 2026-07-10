"""Pydantic models for text-based knowledge graphs."""

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

_SNAKE_CASE_RE = re.compile(r"^[a-z0-9]+(_[a-z0-9]+)*$")

# ---------------------------------------------------------------------------
# Nodes
# ---------------------------------------------------------------------------


class DocumentNode(BaseModel):
    """A source document ingested into the knowledge graph."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(..., description="Identifier derived from the source filename")
    path: str = Field(..., description="Filesystem path to the source document")
    word_count: int = Field(..., ge=0, description="Number of words in the document")
    format: Literal["txt", "md", "pdf"] = Field(..., description="Source document format")


class EntityNode(BaseModel):
    """A named entity (person, organization, place, etc.) mentioned in a document."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(
        ...,
        description="Snake_case label with a disambiguating suffix, e.g. 'john_smith_1'",
    )
    label: str = Field(..., description="Human-readable name of the entity")
    entity_type: Literal["person", "organization", "place", "product", "concept", "event"] = Field(
        ..., description="Category of the entity"
    )
    confidence: float = Field(..., ge=0.0, le=1.0, description="Extraction confidence score")

    @field_validator("id")
    @classmethod
    def id_must_be_snake_case(cls, value: str) -> str:
        if not _SNAKE_CASE_RE.match(value):
            raise ValueError(f"id must be snake_case, got {value!r}")
        return value


class TopicNode(BaseModel):
    """A high-level subject discussed in a document.

    Topics are not drawn from a closed vocabulary; the extractor proposes
    them freely (e.g. "machine_learning", "venture_capital", "climate_policy").
    """

    model_config = ConfigDict(frozen=True)

    id: str = Field(..., description="Identifier for the topic")
    label: str = Field(..., description="Human-readable topic name")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Extraction confidence score")


class AttributeNode(BaseModel):
    """A key/value fact attached to a document or entity."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(..., description="Identifier for the attribute")
    key: Literal["role", "industry", "location", "size", "founded", "status", "description"] = Field(
        ..., description="Controlled-vocabulary attribute key"
    )
    value: str = Field(..., description="Attribute value")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Extraction confidence score")


class ClaimNode(BaseModel):
    """A literal assertion extracted verbatim from a document."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(..., description="Identifier for the claim")
    text: str = Field(..., max_length=200, description="The literal assertion text")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Extraction confidence score")

    @field_validator("text")
    @classmethod
    def text_must_not_be_blank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("text must not be blank")
        return stripped


# ---------------------------------------------------------------------------
# Edges
# ---------------------------------------------------------------------------


class ContainsEdge(BaseModel):
    """Links a document to an entity it mentions."""

    model_config = ConfigDict(frozen=True)

    source: str = Field(..., description="document_id")
    target: str = Field(..., description="entity_id")
    confidence: float = Field(..., ge=0.0, le=1.0)


class AboutTopicEdge(BaseModel):
    """Links a document to a topic it discusses."""

    model_config = ConfigDict(frozen=True)

    source: str = Field(..., description="document_id")
    target: str = Field(..., description="topic_id")
    confidence: float = Field(..., ge=0.0, le=1.0)


class HasAttributeEdge(BaseModel):
    """Links a document or entity to an attribute describing it."""

    model_config = ConfigDict(frozen=True)

    source: str = Field(..., description="document_id | entity_id")
    target: str = Field(..., description="attribute_id")
    confidence: float = Field(..., ge=0.0, le=1.0)


class StatesEdge(BaseModel):
    """Links a document to a claim it makes."""

    model_config = ConfigDict(frozen=True)

    source: str = Field(..., description="document_id")
    target: str = Field(..., description="claim_id")
    confidence: float = Field(..., ge=0.0, le=1.0)


class RelatesToEdge(BaseModel):
    """Links two entities via a typed relation."""

    model_config = ConfigDict(frozen=True)

    source: str = Field(..., description="entity_id")
    target: str = Field(..., description="entity_id")
    relation: Literal[
        "works_at",
        "founded",
        "invested_in",
        "acquired",
        "located_in",
        "part_of",
        "competitor_of",
        "collaborates_with",
        "mentions",
    ] = Field(..., description="Type of relation between the two entities")
    confidence: float = Field(..., ge=0.0, le=1.0)


# ---------------------------------------------------------------------------
# Container
# ---------------------------------------------------------------------------


class DocumentExtraction(BaseModel):
    """The full set of nodes and edges extracted from a single document."""

    document: DocumentNode
    entities: list[EntityNode] = Field(default_factory=list)
    topics: list[TopicNode] = Field(default_factory=list)
    attributes: list[AttributeNode] = Field(default_factory=list)
    claims: list[ClaimNode] = Field(default_factory=list)

    contains_edges: list[ContainsEdge] = Field(default_factory=list)
    about_topic_edges: list[AboutTopicEdge] = Field(default_factory=list)
    has_attribute_edges: list[HasAttributeEdge] = Field(default_factory=list)
    states_edges: list[StatesEdge] = Field(default_factory=list)
    relates_to_edges: list[RelatesToEdge] = Field(default_factory=list)


def validate_extraction(extraction: DocumentExtraction) -> list[str]:
    """Validate the structural integrity of a DocumentExtraction.

    Checks that every node id is unique within the extraction and that
    every edge's source/target references a node id that actually exists.

    Returns a list of human-readable error messages; empty if the
    extraction is structurally valid.
    """

    errors: list[str] = []

    all_ids = (
        [extraction.document.id]
        + [n.id for n in extraction.entities]
        + [n.id for n in extraction.topics]
        + [n.id for n in extraction.attributes]
        + [n.id for n in extraction.claims]
    )

    seen: set[str] = set()
    duplicates: set[str] = set()
    for node_id in all_ids:
        if node_id in seen:
            duplicates.add(node_id)
        seen.add(node_id)

    for dup in sorted(duplicates):
        errors.append(f"Duplicate node id: {dup!r}")

    known_ids = set(all_ids)

    edge_groups: list[tuple[str, list[BaseModel]]] = [
        ("contains_edges", extraction.contains_edges),
        ("about_topic_edges", extraction.about_topic_edges),
        ("has_attribute_edges", extraction.has_attribute_edges),
        ("states_edges", extraction.states_edges),
        ("relates_to_edges", extraction.relates_to_edges),
    ]

    for group_name, edges in edge_groups:
        for i, edge in enumerate(edges):
            source = getattr(edge, "source")
            target = getattr(edge, "target")
            if source not in known_ids:
                errors.append(
                    f"{group_name}[{i}]: source {source!r} does not reference an existing node"
                )
            if target not in known_ids:
                errors.append(
                    f"{group_name}[{i}]: target {target!r} does not reference an existing node"
                )

    return errors
