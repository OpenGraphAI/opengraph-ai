"""Query the knowledge graph and answer questions over extracted image data.

The approach is server-side query primitives that the LLM composes via tool
calls, then writes a natural-language summary citing the evidence it found.
"""

from __future__ import annotations

import itertools
import json
from pathlib import Path
from typing import Any

import anthropic
import networkx as nx
from dotenv import load_dotenv

from opengraph_image.graph import ImageGraph
from opengraph_image.schema import QueryResult

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
load_dotenv(_PROJECT_ROOT / ".env", override=True)

_MODEL = "claude-sonnet-4-6"
_MAX_TURNS = 8

_NODE_TYPES = ["image", "object", "scene", "attribute", "text_span"]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _display_label(node_id: str, attrs: dict) -> str:
    """Return the best human-readable label for a node, regardless of type."""
    if attrs.get("type") == "text_span":
        return attrs.get("text", node_id)
    if attrs.get("type") == "attribute":
        return attrs.get("value", node_id)
    return attrs.get("label", node_id)


def _node_dict(node_id: str, attrs: dict) -> dict:
    return {"id": node_id, **attrs}


def _resolve_node_id(graph: ImageGraph, ref: str) -> str:
    """Resolve a node ID or label fragment to an actual node ID in the graph."""
    if ref in graph._g.nodes:
        return ref
    candidates = find_nodes_by_label(graph, ref)
    if candidates:
        return candidates[0]["id"]
    raise ValueError(f"No node found matching '{ref}'.")


# ---------------------------------------------------------------------------
# Query primitives
# ---------------------------------------------------------------------------

def find_nodes_by_label(graph: ImageGraph, pattern: str, node_type: str | None = None) -> list[dict]:
    """Fuzzy (case-insensitive substring) match on node labels, optionally filtered by type."""
    pattern_lower = pattern.lower()
    results = []
    for node_id, attrs in graph._g.nodes(data=True):
        if node_type and attrs.get("type") != node_type:
            continue
        label = _display_label(node_id, attrs)
        if pattern_lower in label.lower() or pattern_lower in node_id.lower():
            results.append(_node_dict(node_id, attrs))
    return results


def find_nodes_by_type(graph: ImageGraph, node_type: str) -> list[dict]:
    """Return all nodes of the given type."""
    return [
        _node_dict(node_id, attrs)
        for node_id, attrs in graph._g.nodes(data=True)
        if attrs.get("type") == node_type
    ]


def get_neighbors(graph: ImageGraph, node_id: str, depth: int = 1) -> dict:
    """Return the nodes and edges within `depth` hops of node_id (treated as undirected)."""
    resolved = _resolve_node_id(graph, node_id)
    ego = nx.ego_graph(graph._g, resolved, radius=depth, undirected=True)
    nodes = [_node_dict(n, ego.nodes[n]) for n in ego.nodes]
    edges = [{"source": u, "target": v, **data} for u, v, data in ego.edges(data=True)]
    return {"nodes": nodes, "edges": edges}


def find_images_containing(graph: ImageGraph, object_labels: list[str]) -> list[str]:
    """Return image IDs whose contained objects fuzzy-match ALL of object_labels."""
    image_ids = []
    for node_id, attrs in graph._g.nodes(data=True):
        if attrs.get("type") != "image":
            continue
        contained_labels = {
            graph._g.nodes[tgt].get("label", "").lower()
            for _, tgt, edata in graph._g.out_edges(node_id, data=True)
            if edata.get("relation") == "contains"
        }
        if all(
            any(lbl.lower() in cl or cl in lbl.lower() for cl in contained_labels)
            for lbl in object_labels
        ):
            image_ids.append(node_id)
    return image_ids


def find_path(graph: ImageGraph, node_a: str, node_b: str, max_hops: int = 4) -> list[list[str]]:
    """Return up to 5 simple paths (as lists of node IDs) between node_a and node_b."""
    a = _resolve_node_id(graph, node_a)
    b = _resolve_node_id(graph, node_b)
    undirected = graph._g.to_undirected(as_view=True)
    paths = nx.all_simple_paths(undirected, source=a, target=b, cutoff=max_hops)
    return list(itertools.islice(paths, 5))


def filter_images_by_attribute(graph: ImageGraph, key: str, value: str) -> list[str]:
    """Return image IDs that (directly or via a contained object) have an attribute matching key/value."""
    value_lower = value.lower()
    matching_attr_nodes = [
        node_id
        for node_id, attrs in graph._g.nodes(data=True)
        if attrs.get("type") == "attribute"
        and attrs.get("key") == key
        and value_lower in attrs.get("value", "").lower()
    ]

    image_ids: set[str] = set()
    for attr_node in matching_attr_nodes:
        for src, _, edata in graph._g.in_edges(attr_node, data=True):
            if edata.get("relation") != "has_attribute":
                continue
            if graph._g.nodes[src].get("type") == "image":
                image_ids.add(src)
                continue
            for owner, _, owner_edata in graph._g.in_edges(src, data=True):
                if owner_edata.get("relation") == "contains" and graph._g.nodes[owner].get("type") == "image":
                    image_ids.add(owner)

    return sorted(image_ids)


_PRIMITIVES: dict[str, Any] = {
    "find_nodes_by_label": find_nodes_by_label,
    "find_nodes_by_type": find_nodes_by_type,
    "get_neighbors": get_neighbors,
    "find_images_containing": find_images_containing,
    "find_path": find_path,
    "filter_images_by_attribute": filter_images_by_attribute,
}

_TOOLS = [
    {
        "name": "find_nodes_by_label",
        "description": "Fuzzy substring match (case-insensitive) on node labels, optionally filtered by node type.",
        "input_schema": {
            "type": "object",
            "properties": {
                "pattern": {"type": "string", "description": "Substring to search for in node labels."},
                "node_type": {"type": "string", "enum": _NODE_TYPES, "description": "Restrict to this node type."},
            },
            "required": ["pattern"],
        },
    },
    {
        "name": "find_nodes_by_type",
        "description": "Return all nodes of a given type (image, object, scene, attribute, text_span).",
        "input_schema": {
            "type": "object",
            "properties": {"node_type": {"type": "string", "enum": _NODE_TYPES}},
            "required": ["node_type"],
        },
    },
    {
        "name": "get_neighbors",
        "description": "Return the nodes and edges within `depth` hops of a node (by ID or label).",
        "input_schema": {
            "type": "object",
            "properties": {
                "node_id": {"type": "string", "description": "Node ID or label fragment."},
                "depth": {"type": "integer", "default": 1, "description": "Number of hops to traverse."},
            },
            "required": ["node_id"],
        },
    },
    {
        "name": "find_images_containing",
        "description": "Return image IDs whose contained objects fuzzy-match ALL of the given labels.",
        "input_schema": {
            "type": "object",
            "properties": {
                "object_labels": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["object_labels"],
        },
    },
    {
        "name": "find_path",
        "description": "Return up to 5 simple paths between two nodes (by ID or label), up to max_hops.",
        "input_schema": {
            "type": "object",
            "properties": {
                "node_a": {"type": "string"},
                "node_b": {"type": "string"},
                "max_hops": {"type": "integer", "default": 4},
            },
            "required": ["node_a", "node_b"],
        },
    },
    {
        "name": "filter_images_by_attribute",
        "description": "Return image IDs that have a matching attribute (e.g. key='mood', value='warm'), "
        "either on the image itself or on a contained object.",
        "input_schema": {
            "type": "object",
            "properties": {
                "key": {"type": "string", "enum": ["color", "material", "mood", "lighting", "style", "size"]},
                "value": {"type": "string"},
            },
            "required": ["key", "value"],
        },
    },
]

_SYSTEM_PROMPT = (
    "You are answering questions about an image knowledge graph. Use the provided tools "
    "to find relevant nodes and subgraphs. Then write a natural-language summary citing "
    "image filenames and entity labels. Be specific."
)


def _build_context(graph: ImageGraph) -> str:
    """Build a compact (<2k token) summary of the graph for the model's first message."""
    s = graph.summary()
    object_labels = sorted(
        {attrs.get("label") for _, attrs in graph._g.nodes(data=True) if attrs.get("type") == "object" and attrs.get("label")}
    )
    god_node_labels = [g["label"] for g in s["god_nodes"][:10]]
    lines = [
        f"Graph summary: {s['total_nodes']} nodes, {s['total_edges']} edges.",
        f"Node counts by type: {s['node_count_by_type']}",
        f"Top connected nodes: {', '.join(god_node_labels)}",
        f"Images ({len(s['images'])}): {', '.join(s['images'])}",
        f"Sample object labels: {', '.join(object_labels[:40])}",
    ]
    return "\n".join(lines)


def _extract_node_ids(result: Any) -> set[str]:
    """Pull plausible node IDs out of a primitive's return value for subgraph assembly."""
    ids: set[str] = set()
    if isinstance(result, dict) and "nodes" in result:
        for n in result["nodes"]:
            if isinstance(n, dict) and "id" in n:
                ids.add(n["id"])
    elif isinstance(result, list):
        for item in result:
            if isinstance(item, dict) and "id" in item:
                ids.add(item["id"])
            elif isinstance(item, str):
                ids.add(item)
            elif isinstance(item, list):
                ids.update(x for x in item if isinstance(x, str))
    return ids


def _build_subgraph(graph: ImageGraph, node_ids: set[str]) -> dict:
    """Build a JSON-serializable subgraph induced by node_ids."""
    nodes = [_node_dict(n, graph._g.nodes[n]) for n in node_ids if n in graph._g.nodes]
    edges = [
        {"source": u, "target": v, **data}
        for u, v, data in graph._g.edges(data=True)
        if u in node_ids and v in node_ids
    ]
    return {"nodes": nodes, "edges": edges}


def _execute_tool(graph: ImageGraph, name: str, tool_input: dict) -> Any:
    func = _PRIMITIVES.get(name)
    if func is None:
        raise ValueError(f"Unknown tool: {name}")
    return func(graph, **tool_input)


def query_graph(graph: ImageGraph, question: str, client: anthropic.Anthropic) -> QueryResult:
    """Answer a natural-language question over the graph by letting Claude compose query primitives."""
    context = _build_context(graph)
    messages: list[dict] = [
        {"role": "user", "content": f"{context}\n\nQuestion: {question}"}
    ]
    primitives_used: list[dict] = []
    matched_node_ids: set[str] = set()
    final_text = ""

    for _ in range(_MAX_TURNS):
        response = client.messages.create(
            model=_MODEL,
            max_tokens=2048,
            system=_SYSTEM_PROMPT,
            tools=_TOOLS,
            messages=messages,
        )

        if response.stop_reason != "tool_use":
            final_text = "".join(block.text for block in response.content if block.type == "text")
            break

        messages.append({"role": "assistant", "content": response.content})

        tool_results = []
        for block in response.content:
            if block.type != "tool_use":
                continue
            try:
                result = _execute_tool(graph, block.name, block.input)
                matched_node_ids.update(_extract_node_ids(result))
                primitives_used.append({"name": block.name, "input": block.input, "result": result})
                tool_results.append(
                    {"type": "tool_result", "tool_use_id": block.id, "content": json.dumps(result, default=str)}
                )
            except Exception as e:
                primitives_used.append({"name": block.name, "input": block.input, "error": str(e)})
                tool_results.append(
                    {"type": "tool_result", "tool_use_id": block.id, "content": str(e), "is_error": True}
                )

        messages.append({"role": "user", "content": tool_results})
    else:
        final_text = "Unable to fully answer within the tool-call budget."

    subgraph = _build_subgraph(graph, matched_node_ids)

    return QueryResult(
        matched_node_ids=sorted(matched_node_ids),
        matched_subgraph=subgraph,
        summary=final_text,
        primitives_used=primitives_used,
    )
