"""Natural-language query interface for table knowledge graphs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import anthropic
import networkx as nx

_MODEL = "claude-sonnet-4-6"
_MAX_TURNS = 8

_NODE_TYPES = [
    "dataset",
    "filing",
    "entity",
    "taxonomy",
    "xbrl_tag",
    "dimension",
    "report_section",
    "fact",
    "text_fact",
]


def _display_label(node_id: str, attrs: dict[str, Any]) -> str:
    return (
        attrs.get("name")
        or attrs.get("tag")
        or attrs.get("shortname")
        or attrs.get("filename")
        or attrs.get("adsh")
        or node_id
    )


def _node_dict(node_id: str, attrs: dict[str, Any]) -> dict[str, Any]:
    return {"id": node_id, **attrs}


def _find_nodes_by_label(g: nx.DiGraph, pattern: str, node_type: str | None = None) -> list[dict[str, Any]]:
    p = pattern.lower()
    out: list[dict[str, Any]] = []
    for node_id, attrs in g.nodes(data=True):
        if node_type and attrs.get("type") != node_type:
            continue
        label = _display_label(node_id, attrs)
        if p in label.lower() or p in node_id.lower():
            out.append(_node_dict(node_id, attrs))
    return out


def _find_nodes_by_type(g: nx.DiGraph, node_type: str) -> list[dict[str, Any]]:
    return [
        _node_dict(node_id, attrs)
        for node_id, attrs in g.nodes(data=True)
        if attrs.get("type") == node_type
    ]


def _get_neighbors(g: nx.DiGraph, node_id: str, depth: int = 1) -> dict[str, Any]:
    if node_id not in g.nodes:
        matches = _find_nodes_by_label(g, node_id)
        if not matches:
            raise ValueError(f"No node found matching '{node_id}'.")
        node_id = matches[0]["id"]

    ego = nx.ego_graph(g, node_id, radius=depth, undirected=True)
    nodes = [_node_dict(n, ego.nodes[n]) for n in ego.nodes]
    edges = [{"source": u, "target": v, **data} for u, v, data in ego.edges(data=True)]
    return {"nodes": nodes, "edges": edges}


def _find_path(g: nx.DiGraph, node_a: str, node_b: str, max_hops: int = 4) -> list[list[str]]:
    def resolve(ref: str) -> str:
        if ref in g.nodes:
            return ref
        m = _find_nodes_by_label(g, ref)
        if m:
            return m[0]["id"]
        raise ValueError(f"No node found matching '{ref}'.")

    a = resolve(node_a)
    b = resolve(node_b)
    paths = nx.all_simple_paths(g.to_undirected(as_view=True), source=a, target=b, cutoff=max_hops)
    return [list(p) for p in list(paths)[:5]]


def _count_by_type(g: nx.DiGraph) -> dict[str, int]:
    counts: dict[str, int] = {}
    for _, attrs in g.nodes(data=True):
        t = attrs.get("type", "unknown")
        counts[t] = counts.get(t, 0) + 1
    return counts


_PRIMITIVES: dict[str, Any] = {
    "find_nodes_by_label": _find_nodes_by_label,
    "find_nodes_by_type": _find_nodes_by_type,
    "get_neighbors": _get_neighbors,
    "find_path": _find_path,
    "count_by_type": _count_by_type,
}

_TOOLS = [
    {
        "name": "find_nodes_by_label",
        "description": "Fuzzy substring match on node labels/IDs, optional type filter.",
        "input_schema": {
            "type": "object",
            "properties": {
                "pattern": {"type": "string"},
                "node_type": {"type": "string", "enum": _NODE_TYPES},
            },
            "required": ["pattern"],
        },
    },
    {
        "name": "find_nodes_by_type",
        "description": "Return all nodes of a given type.",
        "input_schema": {
            "type": "object",
            "properties": {"node_type": {"type": "string", "enum": _NODE_TYPES}},
            "required": ["node_type"],
        },
    },
    {
        "name": "get_neighbors",
        "description": "Return nodes and edges within N hops of a node.",
        "input_schema": {
            "type": "object",
            "properties": {
                "node_id": {"type": "string"},
                "depth": {"type": "integer", "default": 1},
            },
            "required": ["node_id"],
        },
    },
    {
        "name": "find_path",
        "description": "Find up to 5 simple paths between two nodes.",
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
        "name": "count_by_type",
        "description": "Return node counts grouped by type.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
]

_SYSTEM_PROMPT = (
    "You are answering questions about a table-derived knowledge graph. "
    "Use tools to inspect nodes/edges, then provide a concise answer citing "
    "specific node IDs and relationship labels as evidence."
)


def _extract_node_ids(result: Any) -> set[str]:
    ids: set[str] = set()
    if isinstance(result, dict):
        if "nodes" in result and isinstance(result["nodes"], list):
            for n in result["nodes"]:
                if isinstance(n, dict) and "id" in n:
                    ids.add(n["id"])
        if "id" in result and isinstance(result["id"], str):
            ids.add(result["id"])
    elif isinstance(result, list):
        for item in result:
            if isinstance(item, dict) and "id" in item:
                ids.add(item["id"])
            elif isinstance(item, str):
                ids.add(item)
            elif isinstance(item, list):
                ids.update(x for x in item if isinstance(x, str))
    return ids


def _build_subgraph(g: nx.DiGraph, node_ids: set[str]) -> dict[str, Any]:
    nodes = [_node_dict(n, g.nodes[n]) for n in node_ids if n in g.nodes]
    edges = [
        {"source": u, "target": v, **data}
        for u, v, data in g.edges(data=True)
        if u in node_ids and v in node_ids
    ]
    return {"nodes": nodes, "edges": edges}


def _execute_tool(g: nx.DiGraph, name: str, tool_input: dict[str, Any]) -> Any:
    func = _PRIMITIVES.get(name)
    if func is None:
        raise ValueError(f"Unknown tool: {name}")
    return func(g, **tool_input)


def _build_context(g: nx.DiGraph, sources_meta: dict[str, Any]) -> str:
    counts = _count_by_type(g)
    sample_tags = [
        attrs.get("tag")
        for _, attrs in g.nodes(data=True)
        if attrs.get("type") == "xbrl_tag" and attrs.get("tag")
    ][:30]
    files = [src.get("filename", sid) for sid, src in sources_meta.items()]
    return (
        f"Graph summary: {g.number_of_nodes()} nodes, {g.number_of_edges()} edges.\n"
        f"Node counts by type: {counts}\n"
        f"Sources ({len(files)}): {files}\n"
        f"Sample XBRL tags: {sample_tags}"
    )


async def query_graph(
    question: str,
    graph_path: Path,
    client: anthropic.Anthropic | None = None,
) -> dict[str, Any]:
    """Answer a natural-language question about a table knowledge graph.

    Args:
        question: User's natural-language question.
        graph_path: Path to graph.json file.
        client: Anthropic client (created if not provided).

    Returns:
        Dict with 'answer', 'reasoning', and 'sources' keys.
    """
    if client is None:
        client = anthropic.Anthropic()

    # Load graph data
    graph_data = json.loads(graph_path.read_text())
    g: nx.DiGraph = nx.node_link_graph(graph_data.get("graph", {}), directed=True)
    sources_meta = graph_data.get("sources", {})

    context = _build_context(g, sources_meta)
    messages: list[dict[str, Any]] = [
        {"role": "user", "content": f"{context}\n\nQuestion: {question}"}
    ]
    primitives_used: list[dict[str, Any]] = []
    matched_node_ids: set[str] = set()
    answer_text = ""

    for _ in range(_MAX_TURNS):
        response = client.messages.create(
            model=_MODEL,
            max_tokens=2048,
            system=_SYSTEM_PROMPT,
            tools=_TOOLS,
            messages=messages,
        )

        if response.stop_reason != "tool_use":
            answer_text = "".join(block.text for block in response.content if block.type == "text")
            break

        messages.append({"role": "assistant", "content": response.content})
        tool_results: list[dict[str, Any]] = []

        for block in response.content:
            if block.type != "tool_use":
                continue
            try:
                result = _execute_tool(g, block.name, block.input)
                matched_node_ids.update(_extract_node_ids(result))
                primitives_used.append({"name": block.name, "input": block.input, "result": result})
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps(result, default=str),
                    }
                )
            except Exception as e:
                primitives_used.append({"name": block.name, "input": block.input, "error": str(e)})
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": str(e),
                        "is_error": True,
                    }
                )

        messages.append({"role": "user", "content": tool_results})
    else:
        answer_text = "Unable to fully answer within the tool-call budget."

    return {
        "question": question,
        "answer": answer_text,
        "graph_nodes": g.number_of_nodes(),
        "graph_edges": g.number_of_edges(),
        "sources": list(sources_meta.keys()),
        "matched_node_ids": sorted(matched_node_ids),
        "matched_subgraph": _build_subgraph(g, matched_node_ids),
        "primitives_used": primitives_used,
    }


def query_sync(
    question: str,
    graph_path: Path,
    client: anthropic.Anthropic | None = None,
) -> dict[str, Any]:
    """Synchronous version of query_graph (wrapper for CLI)."""
    import asyncio

    return asyncio.run(query_graph(question, graph_path, client))
