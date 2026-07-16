"""Pydantic models for a text knowledge graph: documents, entities, topics,

attributes, and claims extracted from text documents, plus the edges
connecting them.
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Node models
# ---------------------------------------------------------------------------

class DocumentNode(BaseModel):
    """Root node representing a single text document in the knowledge graph.

    Acts as the anchor to which all extracted entities, topics, attributes,
    and claims are connected via edges.
    """

    id: str = Field(description="Unique identifier derived from the document filename.")
    path: str = Field(description="Absolute or relative filesystem path to the document.")
    word_count: int = Field(gt=0, description="Total number of words in the document.")
    format: Literal["txt", "md", "pdf"] = Field(description="Document file format.")


class EntityNode(BaseModel):
    """A named entity (person, organization, place, product, concept, or event)

    mentioned in a document. The ``id`` uses snake_case of the label with a
    disambiguating suffix when the same label could otherwise collide, e.g.
    ``john_smith_1``, ``john_smith_2``.
    """

    id: str = Field(description="Unique snake_case label, disambiguated with a suffix when duplicated.")
    label: str = Field(description="Human-readable entity name, e.g. 'John Smith'.")
    entity_type: Literal["person", "organization", "place", "product", "concept", "event"] = Field(
        description="Controlled-vocabulary category of the entity."
    )
    confidence: Annotated[float, Field(ge=0.0, le=1.0)] = Field(
        description="Extraction confidence in the range [0, 1]."
    )


class TopicNode(BaseModel):
    """A high-level subject that a document discusses, e.g. 'machine_learning',

    'venture_capital', 'climate_policy'. Topics are not a closed vocabulary;
    the extractor proposes them freely based on document content.
    """

    id: str = Field(description="Unique identifier for this topic node.")
    label: str = Field(description="Human-readable topic name.")
    confidence: Annotated[float, Field(ge=0.0, le=1.0)] = Field(
        description="Extraction confidence in the range [0, 1]."
    )


AttributeKey = Literal["role", "industry", "location", "size", "founded", "status", "description"]


class AttributeNode(BaseModel):
    """A key/value attribute that can be attached to a document or entity.

    Keys are restricted to a controlled vocabulary so attributes remain
    query-able without free-text search.
    """

    id: str = Field(description="Unique identifier for this attribute node.")
    key: AttributeKey = Field(description="Controlled-vocabulary attribute key.")
    value: str = Field(description="Free-text attribute value, e.g. 'CEO', 'fintech'.")
    confidence: Annotated[float, Field(ge=0.0, le=1.0)] = Field(
        description="Extraction confidence in the range [0, 1]."
    )


class ClaimNode(BaseModel):
    """A literal assertion extracted verbatim (or near-verbatim) from a document.

    Kept short and quoted so claims remain traceable back to their source
    sentence rather than becoming paraphrased summaries.
    """

    id: str = Field(description="Unique identifier for this claim node.")
    text: str = Field(max_length=200, description="The literal assertion from the document, at most 200 characters.")
    confidence: Annotated[float, Field(ge=0.0, le=1.0)] = Field(
        description="Extraction confidence in the range [0, 1]."
    )


# ---------------------------------------------------------------------------
# Edge models
# ---------------------------------------------------------------------------

class ContainsEdge(BaseModel):
    """Connects a DocumentNode to an EntityNode it mentions.

    Represents: this document *contains* (mentions) this entity.
    """

    source: str = Field(description="ID of the source DocumentNode.")
    target: str = Field(description="ID of the target EntityNode.")
    confidence: Annotated[float, Field(ge=0.0, le=1.0)] = Field(
        description="Edge confidence in the range [0, 1]."
    )


class AboutTopicEdge(BaseModel):
    """Connects a DocumentNode to a TopicNode it discusses."""

    source: str = Field(description="ID of the source DocumentNode.")
    target: str = Field(description="ID of the target TopicNode.")
    confidence: Annotated[float, Field(ge=0.0, le=1.0)] = Field(
        description="Edge confidence in the range [0, 1]."
    )


class HasAttributeEdge(BaseModel):
    """Connects a DocumentNode or EntityNode to an AttributeNode.

    The ``source`` may be either a document ID or an entity ID, allowing
    attributes to describe the whole document or a specific entity.
    """

    source: str = Field(description="ID of the source DocumentNode or EntityNode.")
    target: str = Field(description="ID of the target AttributeNode.")
    confidence: Annotated[float, Field(ge=0.0, le=1.0)] = Field(
        description="Edge confidence in the range [0, 1]."
    )


class StatesEdge(BaseModel):
    """Connects a DocumentNode to a ClaimNode it asserts."""

    source: str = Field(description="ID of the source DocumentNode.")
    target: str = Field(description="ID of the target ClaimNode.")
    confidence: Annotated[float, Field(ge=0.0, le=1.0)] = Field(
        description="Edge confidence in the range [0, 1]."
    )


RelationType = Literal[
    "works_at",
    "founded",
    "invested_in",
    "acquired",
    "located_in",
    "part_of",
    "competitor_of",
    "collaborates_with",
    "mentions",
]


class RelatesToEdge(BaseModel):
    """Expresses a semantic relationship between two EntityNodes.

    Both ``source`` and ``target`` must be entity IDs. The ``relation``
    field is a controlled vocabulary so that relationships are machine-readable.
    """

    source: str = Field(description="ID of the source EntityNode.")
    target: str = Field(description="ID of the target EntityNode.")
    relation: RelationType = Field(description="Controlled-vocabulary relationship type.")
    confidence: Annotated[float, Field(ge=0.0, le=1.0)] = Field(
        description="Edge confidence in the range [0, 1]."
    )


# ---------------------------------------------------------------------------
# Container model
# ---------------------------------------------------------------------------

class DocumentExtraction(BaseModel):
    """Complete knowledge-graph extraction for a single document.

    Bundles all nodes and edges produced by the extraction pipeline so that
    they can be serialised, stored, and validated as a self-contained unit.
    """

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


# ---------------------------------------------------------------------------
# Query result
# ---------------------------------------------------------------------------

class QueryResult(BaseModel):
    """Result of answering a natural-language question over a DocumentGraph."""

    matched_node_ids: list[str] = Field(
        default_factory=list,
        description="IDs of graph nodes the model identified as relevant to the question.",
    )
    matched_subgraph: dict = Field(
        default_factory=dict,
        description="JSON-serializable subgraph ({'nodes': [...], 'edges': [...]}) induced by matched_node_ids.",
    )
    summary: str = Field(description="Natural-language answer citing document filenames and entity labels.")
    primitives_used: list[dict] = Field(
        default_factory=list,
        description="Log of tool calls the model issued, e.g. [{'name': ..., 'input': ..., 'result': ...}].",
    )


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate_extraction(extraction: DocumentExtraction) -> list[str]:
    """Validate referential integrity of a DocumentExtraction.

    Checks:
    - All node IDs are unique across the extraction.
    - Every edge source/target references an existing node ID.

    Returns a list of human-readable error strings; the list is empty when
    the extraction is valid.
    """
    errors: list[str] = []

    all_nodes: dict[str, str] = {}  # id -> node type

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
    for topic in extraction.topics:
        _register(topic.id, "TopicNode")
    for attr in extraction.attributes:
        _register(attr.id, "AttributeNode")
    for claim in extraction.claims:
        _register(claim.id, "ClaimNode")

    known_ids = set(all_nodes)

    def _check_edge(edge_type: str, source: str, target: str) -> None:
        if source not in known_ids:
            errors.append(f"{edge_type} references unknown source '{source}'.")
        if target not in known_ids:
            errors.append(f"{edge_type} references unknown target '{target}'.")

    for edge in extraction.contains_edges:
        _check_edge("ContainsEdge", edge.source, edge.target)
    for edge in extraction.about_topic_edges:
        _check_edge("AboutTopicEdge", edge.source, edge.target)
    for edge in extraction.has_attribute_edges:
        _check_edge("HasAttributeEdge", edge.source, edge.target)
    for edge in extraction.states_edges:
        _check_edge("StatesEdge", edge.source, edge.target)
    for edge in extraction.relates_to_edges:
        _check_edge("RelatesToEdge", edge.source, edge.target)

    return errors
