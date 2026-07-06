"""Tests for opengraph-table query workflow."""

from __future__ import annotations

import asyncio
import json
import tempfile
from dataclasses import dataclass
from pathlib import Path

import networkx as nx

from opengraph_table.query import query_graph, query_sync


@dataclass
class _FakeToolUseBlock:
    id: str
    name: str
    input: dict
    type: str = "tool_use"


@dataclass
class _FakeTextBlock:
    text: str
    type: str = "text"


@dataclass
class _FakeResponse:
    stop_reason: str
    content: list


class _FakeMessages:
    def __init__(self, responses: list[_FakeResponse]) -> None:
        self._responses = responses

    def create(self, **_: object) -> _FakeResponse:
        if not self._responses:
            raise RuntimeError("No fake responses remaining")
        return self._responses.pop(0)


class _FakeClient:
    def __init__(self, responses: list[_FakeResponse]) -> None:
        self.messages = _FakeMessages(responses)


def _write_sample_graph_json(path: Path) -> None:
    g = nx.DiGraph()
    g.add_node("adsh_amd_10q", type="filing", adsh="0000002488-26-000076", form="10-Q")
    g.add_node("entity_amd", type="entity", name="ADVANCED MICRO DEVICES INC", cik=2488)
    g.add_node("tag_NetIncomeLoss", type="xbrl_tag", tag="NetIncomeLoss")
    g.add_edge("adsh_amd_10q", "entity_amd", relation="filed_by")
    g.add_edge("adsh_amd_10q", "tag_NetIncomeLoss", relation="has_fact")

    payload = {
        "graph": nx.node_link_data(g),
        "sources": {
            "src_sub": {
                "id": "src_sub",
                "filename": "sub.tsv",
                "sheet_name": None,
                "page_index": None,
                "table_index": 0,
                "title": "Submissions",
                "extracted_at": "2026-05-07",
            }
        },
        "metadata": {},
    }
    path.write_text(json.dumps(payload, indent=2))


class TestQueryWorkflow:
    """Validate image-style tool-query behavior for table graphs."""

    def test_query_graph_tool_loop_success(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            graph_path = Path(tmpdir) / "graph.json"
            _write_sample_graph_json(graph_path)

            fake_client = _FakeClient(
                responses=[
                    _FakeResponse(
                        stop_reason="tool_use",
                        content=[
                            _FakeToolUseBlock(id="t1", name="count_by_type", input={}),
                            _FakeToolUseBlock(
                                id="t2", name="find_nodes_by_type", input={"node_type": "entity"}
                            ),
                        ],
                    ),
                    _FakeResponse(
                        stop_reason="end_turn",
                        content=[
                            _FakeTextBlock(
                                "There is 1 filing and 1 represented company: ADVANCED MICRO DEVICES INC."
                            )
                        ],
                    ),
                ]
            )

            result = asyncio.run(
                query_graph(
                    question="How many filings and which company is represented?",
                    graph_path=graph_path,
                    client=fake_client,
                )
            )

            assert "ADVANCED MICRO DEVICES" in result["answer"]
            assert result["graph_nodes"] == 3
            assert result["graph_edges"] == 2
            assert result["sources"] == ["src_sub"]
            assert "entity_amd" in result["matched_node_ids"]
            assert any(p["name"] == "count_by_type" for p in result["primitives_used"])
            assert any(p["name"] == "find_nodes_by_type" for p in result["primitives_used"])
            assert len(result["matched_subgraph"]["nodes"]) >= 1

    def test_query_graph_tool_error_is_captured(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            graph_path = Path(tmpdir) / "graph.json"
            _write_sample_graph_json(graph_path)

            fake_client = _FakeClient(
                responses=[
                    _FakeResponse(
                        stop_reason="tool_use",
                        content=[
                            _FakeToolUseBlock(
                                id="t1", name="get_neighbors", input={"node_id": "missing_node", "depth": 1}
                            )
                        ],
                    ),
                    _FakeResponse(
                        stop_reason="end_turn",
                        content=[_FakeTextBlock("I could not find that node, but the graph is loaded.")],
                    ),
                ]
            )

            result = asyncio.run(
                query_graph(
                    question="Show neighbors of missing_node",
                    graph_path=graph_path,
                    client=fake_client,
                )
            )

            assert "could not find" in result["answer"].lower()
            assert len(result["primitives_used"]) == 1
            assert result["primitives_used"][0]["name"] == "get_neighbors"
            assert "error" in result["primitives_used"][0]
            assert "No node found matching" in result["primitives_used"][0]["error"]

    def test_query_sync_wrapper(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            graph_path = Path(tmpdir) / "graph.json"
            _write_sample_graph_json(graph_path)

            fake_client = _FakeClient(
                responses=[
                    _FakeResponse(
                        stop_reason="end_turn",
                        content=[_FakeTextBlock("Sync wrapper works.")],
                    )
                ]
            )

            result = query_sync(
                question="Is sync query working?",
                graph_path=graph_path,
                client=fake_client,
            )

            assert result["answer"] == "Sync wrapper works."
            assert result["graph_nodes"] == 3
            assert result["graph_edges"] == 2
