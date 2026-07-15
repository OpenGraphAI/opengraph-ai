"""Natural-language query interface for text knowledge graphs."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .graph import DocumentGraph

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip()).lower()


def _node_label(node_id: str, attrs: dict[str, Any]) -> str:
    if attrs.get("type") == "document":
        return Path(attrs.get("path", "")).name or node_id
    return attrs.get("label") or attrs.get("value") or attrs.get("text") or node_id


def _find_matching_nodes(graph: DocumentGraph, terms: set[str]) -> list[dict[str, Any]]:
    matches: list[dict[str, Any]] = []
    for node_id, attrs in graph.graph.nodes(data=True):
        label = _node_label(node_id, attrs).lower()
        if not label:
            continue
        if terms & set(_TOKEN_RE.findall(label)):
            info = {"id": node_id, "label": _node_label(node_id, attrs), **attrs}
            matches.append(info)
    return matches


def _build_answer(question: str, matches: list[dict[str, Any]], summary: dict[str, Any]) -> str:
    if not matches:
        documents = ", ".join(summary.get("documents", []))
        return (
            "I could not find any nodes that directly match your question. "
            f"This graph contains {summary.get('total_nodes')} nodes and {summary.get('total_edges')} edges. "
            f"Documents in the graph: {documents}."
        )

    matched_labels = sorted({match.get("label", match["id"]) for match in matches})
    return (
        "Found matching graph nodes: "
        + ", ".join(matched_labels[:10])
        + ("." if len(matched_labels) <= 10 else ", ...")
    )


def query_graph(graph: DocumentGraph, question: str, client: Any) -> dict[str, Any]:
    """Run a simple query over a DocumentGraph and return a JSON-safe result."""
    normalized = _normalize(question)
    terms = set(_TOKEN_RE.findall(normalized))
    matches = _find_matching_nodes(graph, terms)
    summary = graph.summary()
    answer = _build_answer(question, matches, summary)

    return {
        "question": question,
        "answer": answer,
        "graph_nodes": summary.get("total_nodes"),
        "graph_edges": summary.get("total_edges"),
        "matched_nodes": matches[:20],
    }

