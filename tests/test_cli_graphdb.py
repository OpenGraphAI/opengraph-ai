"""Tests for graphdb CLI commands and Neo4j payload helpers."""

import json
from pathlib import Path

from click.testing import CliRunner
from typer.main import get_command

from cli.__main__ import app as cli_app
from cli.commands.graphdb import _dataset_name_from_json_path
from engine.connectors.neo4j_aura import _sanitize_node_properties
from engine.connectors.neo4j_aura import _sanitize_relationship_properties


runner = CliRunner()


def test_dataset_name_from_graph_json_parent() -> None:
    path = Path("output/Airline-Loyalty-Program/graph.json")
    assert _dataset_name_from_json_path(path) == "Airline-Loyalty-Program"


def test_sanitize_node_properties_excludes_structural_fields() -> None:
    entity = {
        "id": "n1",
        "label": "Alice",
        "type": "person",
        "dataset": "demo",
        "confidence": 0.91,
        "properties": {"source": "llm", "dataset": "bad"},
    }

    props = _sanitize_node_properties(entity)

    assert props["source"] == "llm"
    assert props["confidence"] == 0.91
    assert "dataset" not in props


def test_sanitize_relationship_properties_excludes_structural_fields() -> None:
    relationship = {
        "source": "n1",
        "target": "n2",
        "relation": "founded",
        "score": 0.5,
        "properties": {"evidence": "text", "dataset": "bad"},
    }

    props = _sanitize_relationship_properties(relationship)

    assert props["evidence"] == "text"
    assert props["score"] == 0.5
    assert "dataset" not in props


def test_graphdb_push_uses_dataset_and_calls_store(monkeypatch, tmp_path: Path) -> None:
    graph_path = tmp_path / "output" / "DemoSet" / "graph.json"
    graph_path.parent.mkdir(parents=True)
    graph_path.write_text(
        json.dumps({"entities": [{"id": "n1", "label": "Node"}], "relationships": []}),
        encoding="utf-8",
    )

    result = runner.invoke(
        get_command(cli_app),
        ["graphdb", "push", str(graph_path)],
    )

    assert result.exit_code == 1, result.stdout
    assert "disabled in GCP-only mode" in (result.output or "")


def test_graphdb_pull_writes_output(monkeypatch, tmp_path: Path) -> None:
    result = runner.invoke(
        get_command(cli_app),
        ["graphdb", "pull", "DemoSet"],
    )

    assert result.exit_code == 1, result.stdout
    assert "disabled in GCP-only mode" in (result.output or "")


def test_graphdb_from_gcs_runs_end_to_end(monkeypatch, tmp_path: Path) -> None:
    del tmp_path

    def fake_workflow(**kwargs):
        assert kwargs["dataset"] == "DemoSet"
        return {
            "dataset": "DemoSet",
            "gcs_input_uri": "gs://bucket/opengraph-ai/input/DemoSet",
            "gcs_json_uri": "gs://bucket/opengraph-ai/output/DemoSet/graph.json",
            "gcs_png_uri": "gs://bucket/opengraph-ai/output/DemoSet/graph.png",
            "stored_node_count": 1,
            "stored_edge_count": 0,
            "entity_count": 1,
            "relationship_count": 0,
            "graph_json": {
                "entities": [{"id": "n1", "label": "Alice", "type": "person"}],
                "relationships": [],
                "metadata": {"dataset": "DemoSet"},
            },
        }

    monkeypatch.setattr("cli.commands.graphdb.run_graph_from_gcs_via_cloud_run", fake_workflow)

    result = runner.invoke(
        get_command(cli_app),
        ["graphdb", "from-gcs", "DemoSet"],
    )

    assert result.exit_code == 0, result.stdout
    assert "gs://bucket/opengraph-ai/input/DemoSet" in result.stdout
    assert "Neo4j graph JSON:" in result.stdout
