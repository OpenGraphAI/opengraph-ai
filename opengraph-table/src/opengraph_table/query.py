"""Natural-language query interface for table knowledge graphs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import anthropic
import networkx as nx


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

    # Extract relevant context
    context = _build_context(g, sources_meta)

    # Ask Claude to interpret the question
    system_prompt = """\
You are an expert analyst of structured knowledge graphs extracted from tables.
You have access to a graph containing entities, their relationships, metrics, and source information.

Your task is to:
1. Understand the user's question
2. Identify relevant entities, relationships, and metrics from the graph
3. Provide a clear, natural-language answer with supporting evidence
4. Cite the sources and specific data that led to your answer

Always be precise and cite specific entities and their relationships."""

    user_message = f"""\
Here is the knowledge graph context:

{context}

User question: {question}

Please answer the question based on the graph data provided. Include:
- Direct answer
- Supporting reasoning from the graph
- Specific entities and relationships involved
- Source references
"""

    response = client.messages.create(
        model="claude-3-5-sonnet-20241022",
        max_tokens=1024,
        system=system_prompt,
        messages=[{"role": "user", "content": user_message}],
    )

    answer_text = response.content[0].text

    return {
        "question": question,
        "answer": answer_text,
        "graph_nodes": g.number_of_nodes(),
        "graph_edges": g.number_of_edges(),
        "sources": list(sources_meta.keys()),
    }


def _build_context(g: nx.DiGraph, sources_meta: dict[str, Any]) -> str:
    """Build human-readable context from graph for Claude."""
    lines = ["## Knowledge Graph Summary\n"]

    # Add source information
    if sources_meta:
        lines.append("### Data Sources\n")
        for source_id, source_info in sources_meta.items():
            lines.append(f"- {source_info.get('filename', source_id)}")
            if source_info.get("sheet_name"):
                lines.append(f" (sheet: {source_info['sheet_name']})")
            lines.append(f" - Extracted: {source_info.get('extracted_at', 'N/A')}\n")

    # Extract entities with their relationships
    lines.append("\n### Entities and Relationships\n")
    entities = {n: a for n, a in g.nodes(data=True) if a.get("type") == "entity"}

    for entity_id, attrs in sorted(entities.items(), key=lambda x: x[1].get("name", "")):
        name = attrs.get("name", "Unknown")
        etype = attrs.get("entity_type", "unknown")
        confidence = attrs.get("confidence", 0.0)

        lines.append(f"**{name}** (type: {etype}, confidence: {confidence:.2f})\n")

        # Add attributes
        if attrs.get("attributes"):
            for k, v in attrs["attributes"].items():
                lines.append(f"  - {k}: {v}\n")

        # Add relationships
        successors = list(g.successors(entity_id))
        if successors:
            for succ_id in successors:
                succ_attrs = g.nodes.get(succ_id, {})
                if succ_attrs.get("type") == "entity":
                    edges = g.get_edge_data(entity_id, succ_id)
                    if edges:
                        for edge_data in edges.values():
                            rel_type = edge_data.get("relation", "related_to")
                            lines.append(f"  → {rel_type} → {succ_attrs.get('name', succ_id)}\n")

        lines.append("\n")

    # Add metrics
    metrics = {n: a for n, a in g.nodes(data=True) if a.get("type") == "metric"}
    if metrics:
        lines.append("### Metrics\n")
        for metric_id, attrs in metrics.items():
            name = attrs.get("name", "Unknown")
            metric_type = attrs.get("metric_type", "unknown")
            value = attrs.get("value", "N/A")
            lines.append(f"- {name} ({metric_type}): {value}\n")

    return "".join(lines)


def query_sync(
    question: str,
    graph_path: Path,
    client: anthropic.Anthropic | None = None,
) -> dict[str, Any]:
    """Synchronous version of query_graph (wrapper for CLI)."""
    import asyncio

    return asyncio.run(query_graph(question, graph_path, client))
