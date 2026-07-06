"""Pydantic models for text knowledge graph nodes, edges, and MCP tool I/O."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class DocumentNode(BaseModel):
    """Root node representing one text document."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(description="Unique snake_case document identifier.")
    path: str = Field(description="Absolute or relative filesystem path to the document.")
    title: str | None = Field(default=None, description="Optional document title.")
    language: str = Field(default="en", description="BCP-47 language code, e.g. 'en'.")
    source: str | None = Field(default=None, description="Optional source or origin of the document.")


EntityType = Literal[
    "person",
    "organization",
    "location",
    "event",
    "product",
    "work",
    "concept",
    "date",
    "other",
]


class EntityNode(BaseModel):
    """A named entity or important concept mentioned in a document."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(description="Unique snake_case entity identifier.")
    label: str = Field(description="Human-readable entity label.")
    type: EntityType = Field(default="other", description="Controlled entity type.")
    description: str | None = Field(default=None, description="Brief description from document context.")
    confidence: Annotated[float, Field(ge=0.0, le=1.0)] = Field(
        description="Extraction confidence in the range [0, 1]."
    )


class TextChunkNode(BaseModel):
    """A meaningful passage or section of text from the document."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(description="Unique snake_case text chunk identifier.")
    text: str = Field(description="Original text chunk.")
    start_char: int | None = Field(default=None, ge=0, description="Optional start character offset.")
    end_char: int | None = Field(default=None, ge=0, description="Optional end character offset.")
    confidence: Annotated[float, Field(ge=0.0, le=1.0)] = Field(
        default=1.0,
        description="Confidence in chunk extraction.",
    )

    @field_validator("text")
    @classmethod
    def _text_not_empty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("text chunk cannot be empty")
        return value


AttributeKey = Literal["topic", "tone", "sentiment", "genre", "claim", "keyword"]


class AttributeNode(BaseModel):
    """A key/value attribute attached to a document, entity, or text chunk."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(description="Unique snake_case attribute identifier.")
    key: AttributeKey = Field(description="Controlled attribute key.")
    value: str = Field(description="Attribute value.")
    confidence: Annotated[float, Field(ge=0.0, le=1.0)] = Field(
        description="Attribute confidence in the range [0, 1]."
    )


class MentionsEdge(BaseModel):
    """Connects a TextChunkNode to an EntityNode mentioned in that chunk."""

    model_config = ConfigDict(extra="forbid")

    source: str = Field(description="ID of the source TextChunkNode.")
    target: str = Field(description="ID of the target EntityNode.")
    confidence: Annotated[float, Field(ge=0.0, le=1.0)] = Field(
        description="Edge confidence in the range [0, 1]."
    )


class ContainsEdge(BaseModel):
    """Connects a DocumentNode to a TextChunkNode it contains."""

    model_config = ConfigDict(extra="forbid")

    source: str = Field(description="ID of the source DocumentNode.")
    target: str = Field(description="ID of the target TextChunkNode.")
    confidence: Annotated[float, Field(ge=0.0, le=1.0)] = Field(
        default=1.0,
        description="Edge confidence in the range [0, 1].",
    )


class HasAttributeEdge(BaseModel):
    """Connects a document, entity, or text chunk to an AttributeNode."""

    model_config = ConfigDict(extra="forbid")

    source: str = Field(description="ID of the source node.")
    target: str = Field(description="ID of the target AttributeNode.")
    confidence: Annotated[float, Field(ge=0.0, le=1.0)] = Field(
        description="Edge confidence in the range [0, 1]."
    )


RelationType = Literal[
    "related_to",
    "part_of",
    "causes",
    "supports",
    "contradicts",
    "located_in",
    "works_for",
    "created_by",
    "mentions",
    "describes",
]


class RelationEdge(BaseModel):
    """Expresses a semantic relationship between two EntityNodes."""

    model_config = ConfigDict(extra="forbid")

    source: str = Field(description="ID of the source EntityNode.")
    target: str = Field(description="ID of the target EntityNode.")
    relation: RelationType = Field(description="Controlled semantic relationship type.")
    evidence: str | None = Field(default=None, description="Short supporting evidence from the document.")
    confidence: Annotated[float, Field(ge=0.0, le=1.0)] = Field(
        description="Edge confidence in the range [0, 1]."
    )


class DocumentExtraction(BaseModel):
    """Complete knowledge-graph extraction for one text document."""

    model_config = ConfigDict(extra="forbid")

    document: DocumentNode
    entities: list[EntityNode] = Field(default_factory=list)
    text_chunks: list[TextChunkNode] = Field(default_factory=list)
    attributes: list[AttributeNode] = Field(default_factory=list)
    contains_edges: list[ContainsEdge] = Field(default_factory=list)
    mentions_edges: list[MentionsEdge] = Field(default_factory=list)
    has_attribute_edges: list[HasAttributeEdge] = Field(default_factory=list)
    relation_edges: list[RelationEdge] = Field(default_factory=list)


def validate_extraction(extraction: DocumentExtraction) -> list[str]:
    """Validate referential integrity of a DocumentExtraction."""

    errors: list[str] = []
    all_nodes: dict[str, str] = {}

    def _register(node_id: str, node_type: str) -> None:
        if node_id in all_nodes:
            errors.append(
                f"Duplicate node ID '{node_id}': appears as both "
                f"{all_nodes[node_id]} and {node_type}."
            )
        else:
            all_nodes[node_id] = node_type

    _register(extraction.document.id, "DocumentNode")

    for entity in extraction.entities:
        _register(entity.id, "EntityNode")
    for chunk in extraction.text_chunks:
        _register(chunk.id, "TextChunkNode")
    for attr in extraction.attributes:
        _register(attr.id, "AttributeNode")

    known_ids = set(all_nodes)

    def _check_edge(edge_type: str, source: str, target: str) -> None:
        if source not in known_ids:
            errors.append(f"{edge_type} references unknown source '{source}'.")
        if target not in known_ids:
            errors.append(f"{edge_type} references unknown target '{target}'.")

    for edge in extraction.contains_edges:
        _check_edge("ContainsEdge", edge.source, edge.target)
    for edge in extraction.mentions_edges:
        _check_edge("MentionsEdge", edge.source, edge.target)
    for edge in extraction.has_attribute_edges:
        _check_edge("HasAttributeEdge", edge.source, edge.target)
    for edge in extraction.relation_edges:
        _check_edge("RelationEdge", edge.source, edge.target)

    return errors


class QueryResult(BaseModel):
    """Result of answering a natural-language question over a text graph."""

    model_config = ConfigDict(extra="forbid")

    matched_node_ids: list[str] = Field(
        default_factory=list,
        description="IDs of graph nodes relevant to the question.",
    )
    matched_subgraph: dict = Field(
        default_factory=dict,
        description="JSON-serializable subgraph induced by matched_node_ids.",
    )
    summary: str = Field(description="Natural-language answer citing documents and entities.")
    primitives_used: list[dict] = Field(
        default_factory=list,
        description="Log of tool calls or graph operations used.",
    )