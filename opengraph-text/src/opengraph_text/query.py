"""Natural-language querying over a text knowledge graph."""

from __future__ import annotations

import json
from pathlib import Path

import anthropic

from opengraph_text.graph import TextGraph
from opengraph_text.schema import QueryResult

_SYSTEM_PROMPT = """\
You answer questions over a text knowledge graph.

Use the provided graph summary and graph JSON to identify relevant nodes and edges.
Return a concise answer with matched node IDs and a small supporting subgraph.
"""


def query_graph(graph: TextGraph, question: str, client: anthropic.Anthropic) -> QueryResult:
    """Answer a natural-language question over a TextGraph."""
    graph_json = json.dumps(graph.summary(), indent=2)

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2048,
        system=_SYSTEM_PROMPT,
        tools=[
            {
                "name": "submit_query_result",
                "description": "Submit the structured query result.",
                "input_schema": QueryResult.model_json_schema(),
            }
        ],
        tool_choice={"type": "tool", "name": "submit_query_result"},
        messages=[
            {
                "role": "user",
                "content": (
                    f"Question:\n{question}\n\n"
                    f"Graph summary:\n{graph_json}\n"
                ),
            }
        ],
    )

    tool_use_block = next(
        (block for block in response.content if block.type == "tool_use"),
        None,
    )
    if tool_use_block is None:
        raise ValueError(f"Model did not call submit_query_result. Response: {response.content}")

    return QueryResult.model_validate(tool_use_block.input)


def query_graph_file(graph_path: Path, question: str, client: anthropic.Anthropic) -> QueryResult:
    """Load a graph from disk and answer a question."""
    graph = TextGraph.from_json(graph_path)
    return query_graph(graph, question, client)