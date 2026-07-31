"""Natural-language query interface for text knowledge graphs.

The approach is server-side query primitives that the LLM composes via tool
calls: Claude is given a compact textual summary of the graph plus a set of
tools (`find_nodes_by_label`, `find_nodes_by_type`, `get_neighbors`,
`find_documents_mentioning`, `find_path`, `filter_documents_by_topic`), and
loops calling them until it has enough information to write a
natural-language summary.
"""

from __future__ import annotations

import itertools
import json
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

load_dotenv(override=True)  # .env wins over shell env vars

import anthropic
import networkx as nx

from .graph import DocumentGraph
from .schema import QueryResult

MODEL = "claude-sonnet-4-6"
MAX_TOOL_ITERATIONS = 8
MAX_PATHS = 5

SYSTEM_PROMPT = """\
You are answering questions about a text knowledge graph. Use the provided \
tools to find relevant nodes and subgraphs. Then write a natural-language \
summary citing document filenames and entity labels. Be specific.

When you have enough information, respond with ONLY the final \
natural-language summary and do not call any more tools.
"""


# ---------------------------------------------------------------------------
# Node helpers
# ---------------------------------------------------------------------------


def _node_label(node_id: str, attrs: dict[str, Any]) -> str:
    if attrs.get("type") == "document":
        return Path(attrs.get("path", "")).name or node_id
    return attrs.get("label") or attrs.get("value") or attrs.get("text") or node_id


def _node_dict(graph: DocumentGraph, node_id: str) -> dict[str, Any]:
    attrs = graph.graph.nodes[node_id]
    return {"id": node_id, "label": _node_label(node_id, attrs), **attrs}


# ---------------------------------------------------------------------------
# Query primitives
# ---------------------------------------------------------------------------


def find_nodes_by_label(
    graph: DocumentGraph, pattern: str, node_type: str | None = None
) -> list[dict[str, Any]]:
    """Fuzzy, case-insensitive substring match against node labels."""

    needle = pattern.strip().lower()
    matches = []
    for node_id, attrs in graph.graph.nodes(data=True):
        if node_type and attrs.get("type") != node_type:
            continue
        if needle in _node_label(node_id, attrs).lower():
            matches.append(_node_dict(graph, node_id))
    return matches


def find_nodes_by_type(graph: DocumentGraph, node_type: str) -> list[dict[str, Any]]:
    """Return all nodes of the given type."""

    return [
        _node_dict(graph, node_id)
        for node_id, attrs in graph.graph.nodes(data=True)
        if attrs.get("type") == node_type
    ]


def get_neighbors(graph: DocumentGraph, node_id: str, depth: int = 1) -> dict[str, Any]:
    """Return the nodes and edges within `depth` hops of `node_id`."""

    if node_id not in graph.graph:
        return {"nodes": [], "edges": []}

    ego = nx.ego_graph(graph.graph, node_id, radius=depth, undirected=True)
    nodes = [_node_dict(graph, n) for n in ego.nodes()]
    edges = [{"source": u, "target": v, **data} for u, v, data in ego.edges(data=True)]
    return {"nodes": nodes, "edges": edges}


def find_documents_mentioning(graph: DocumentGraph, entity_labels: list[str]) -> list[str]:
    """Return document IDs whose entities fuzzy-match ALL of `entity_labels`."""

    doc_sets: list[set[str]] = []
    for label in entity_labels:
        needle = label.strip().lower()
        docs: set[str] = set()
        for node_id, attrs in graph.graph.nodes(data=True):
            if attrs.get("type") != "entity":
                continue
            if needle in _node_label(node_id, attrs).lower():
                docs.update(attrs.get("seen_in", []))
        doc_sets.append(docs)

    if not doc_sets:
        return []
    return sorted(set.intersection(*doc_sets))


def find_path(graph: DocumentGraph, node_a: str, node_b: str, max_hops: int = 4) -> list[list[str]]:
    """Return up to 5 simple paths between two node IDs, up to `max_hops` edges."""

    if node_a not in graph.graph or node_b not in graph.graph:
        return []

    undirected = graph.graph.to_undirected(as_view=True)
    try:
        paths_iter = nx.all_simple_paths(undirected, node_a, node_b, cutoff=max_hops)
    except nx.NodeNotFound:
        return []
    return list(itertools.islice(paths_iter, MAX_PATHS))


def filter_documents_by_topic(graph: DocumentGraph, topic_label: str) -> list[str]:
    """Return document IDs about a topic fuzzy-matching `topic_label`."""

    needle = topic_label.strip().lower()
    docs: set[str] = set()
    for node_id, attrs in graph.graph.nodes(data=True):
        if attrs.get("type") != "topic":
            continue
        if needle in _node_label(node_id, attrs).lower():
            docs.update(attrs.get("seen_in", []))
    return sorted(docs)


_PRIMITIVES = {
    "find_nodes_by_label": find_nodes_by_label,
    "find_nodes_by_type": find_nodes_by_type,
    "get_neighbors": get_neighbors,
    "find_documents_mentioning": find_documents_mentioning,
    "find_path": find_path,
    "filter_documents_by_topic": filter_documents_by_topic,
}

TOOLS = [
    {
        "name": "find_nodes_by_label",
        "description": (
            "Fuzzy, case-insensitive substring search for nodes by their label "
            "(entity/topic label, attribute value, claim text, or document filename). "
            "Optionally filter by node_type."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "pattern": {"type": "string", "description": "Substring to search for, case-insensitive"},
                "node_type": {
                    "type": "string",
                    "enum": ["document", "entity", "topic", "attribute", "claim"],
                    "description": "Optional node type filter",
                },
            },
            "required": ["pattern"],
        },
    },
    {
        "name": "find_nodes_by_type",
        "description": "Return all nodes of a given type (document, entity, topic, attribute, or claim).",
        "input_schema": {
            "type": "object",
            "properties": {
                "node_type": {
                    "type": "string",
                    "enum": ["document", "entity", "topic", "attribute", "claim"],
                },
            },
            "required": ["node_type"],
        },
    },
    {
        "name": "get_neighbors",
        "description": "Return the nodes and edges within `depth` hops of a node (direction-agnostic).",
        "input_schema": {
            "type": "object",
            "properties": {
                "node_id": {"type": "string"},
                "depth": {"type": "integer", "minimum": 1, "default": 1},
            },
            "required": ["node_id"],
        },
    },
    {
        "name": "find_documents_mentioning",
        "description": "Return document IDs that mention ALL of the given entity labels (fuzzy match).",
        "input_schema": {
            "type": "object",
            "properties": {
                "entity_labels": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["entity_labels"],
        },
    },
    {
        "name": "find_path",
        "description": "Find up to 5 simple paths between two node IDs, each at most max_hops edges long.",
        "input_schema": {
            "type": "object",
            "properties": {
                "node_a": {"type": "string"},
                "node_b": {"type": "string"},
                "max_hops": {"type": "integer", "minimum": 1, "default": 4},
            },
            "required": ["node_a", "node_b"],
        },
    },
    {
        "name": "filter_documents_by_topic",
        "description": "Return document IDs about a topic matching topic_label (fuzzy match).",
        "input_schema": {
            "type": "object",
            "properties": {
                "topic_label": {"type": "string"},
            },
            "required": ["topic_label"],
        },
    },
]


def _execute_primitive(graph: DocumentGraph, name: str, tool_input: dict[str, Any]) -> Any:
    func = _PRIMITIVES.get(name)
    if func is None:
        return {"error": f"Unknown tool: {name}"}
    try:
        return func(graph, **tool_input)
    except Exception as e:
        return {"error": str(e)}


def _extract_node_ids(name: str, result: Any) -> set[str]:
    try:
        if name in ("find_nodes_by_label", "find_nodes_by_type"):
            return {n["id"] for n in result}
        if name == "get_neighbors":
            return {n["id"] for n in result["nodes"]}
        if name in ("find_documents_mentioning", "filter_documents_by_topic"):
            return set(result)
        if name == "find_path":
            return {node for path in result for node in path}
    except (TypeError, KeyError):
        return set()
    return set()


# ---------------------------------------------------------------------------
# Graph context
# ---------------------------------------------------------------------------


def _build_graph_context(graph: DocumentGraph) -> str:
    """Build a compact (<2k token) textual summary of the graph."""

    summary = graph.summary()

    document_filenames = sorted(
        Path(attrs.get("path", "")).name or node_id
        for node_id, attrs in graph.graph.nodes(data=True)
        if attrs.get("type") == "document"
    )

    entity_labels = sorted(
        {
            _node_label(node_id, attrs)
            for node_id, attrs in graph.graph.nodes(data=True)
            if attrs.get("type") == "entity"
        }
    )

    god_node_lines = [
        f"- {n['id']} ({n['type']}, degree {n['degree']}): {n['label']}" for n in summary["god_nodes"]
    ]

    lines = [
        "## Graph overview",
        f"{summary['total_nodes']} nodes, {summary['total_edges']} edges.",
        f"Node counts by type: {json.dumps(summary['node_count_by_type'])}",
        f"Edge counts by relation: {json.dumps(summary['edge_count_by_relation'])}",
        "",
        f"## Documents ({len(document_filenames)})",
        ", ".join(document_filenames) or "(none)",
        "",
        "## Top god nodes (most connected)",
        "\n".join(god_node_lines) or "(none)",
        "",
        f"## Sample entity labels ({len(entity_labels)} total, showing up to 60)",
        ", ".join(entity_labels[:60]) or "(none)",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def query_graph(graph: DocumentGraph, question: str, client: anthropic.Anthropic) -> QueryResult:
    """Answer a natural-language `question` about `graph` using tool-calling Claude."""

    context = _build_graph_context(graph)
    messages: list[dict[str, Any]] = [
        {"role": "user", "content": f"{context}\n\n## Question\n{question}"}
    ]

    matched_node_ids: set[str] = set()
    primitives_used: list[dict[str, Any]] = []
    summary_text = "I was unable to complete the analysis within the allotted number of tool calls."

    for _ in range(MAX_TOOL_ITERATIONS):
        response = client.messages.create(
            model=MODEL,
            max_tokens=2048,
            system=SYSTEM_PROMPT,
            tools=TOOLS,
            messages=messages,
        )
        messages.append({"role": "assistant", "content": response.content})

        tool_use_blocks = [block for block in response.content if block.type == "tool_use"]
        if not tool_use_blocks:
            summary_text = "".join(
                block.text for block in response.content if block.type == "text"
            ).strip()
            break

        tool_results = []
        for block in tool_use_blocks:
            result = _execute_primitive(graph, block.name, block.input)
            primitives_used.append({"name": block.name, "input": block.input})
            matched_node_ids.update(_extract_node_ids(block.name, result))
            tool_results.append(
                {
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": json.dumps(result),
                }
            )
        messages.append({"role": "user", "content": tool_results})

    matched_node_ids_list = sorted(matched_node_ids)
    subgraph = graph.graph.subgraph(matched_node_ids_list)
    matched_subgraph = (
        nx.node_link_data(subgraph, edges="edges") if matched_node_ids_list else {"nodes": [], "edges": []}
    )

    return QueryResult(
        matched_node_ids=matched_node_ids_list,
        matched_subgraph=matched_subgraph,
        summary=summary_text,
        primitives_used=primitives_used,
    )
