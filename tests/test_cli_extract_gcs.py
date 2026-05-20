"""Tests for Cloud Run-backed extract CLI flow."""

from click.testing import CliRunner
from typer.main import get_command

from cli.__main__ import app as cli_app


runner = CliRunner()


def test_extract_text_invokes_cloud_run_file_workflow(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_run(**kwargs):
        captured.update(kwargs)
        return {
            "dataset": "DemoSet",
            "source_uri": "gs://bucket/opengraph-ai/input/DemoSet/note.txt",
            "gcs_json_uri": "gs://bucket/opengraph-ai/output/DemoSet/graph.json",
            "gcs_png_uri": "gs://bucket/opengraph-ai/output/DemoSet/graph.png",
            "entity_count": 2,
            "relationship_count": 1,
            "graph_json": {"entities": [], "relationships": []},
        }

    monkeypatch.setattr("cli.commands.extract.run_graph_from_gcs_file_via_cloud_run", fake_run)

    result = runner.invoke(
        get_command(cli_app),
        [
            "extract",
            "text",
            "gs://bucket/opengraph-ai/input/DemoSet/note.txt",
            "--output-gcs-uri",
            "gs://bucket/opengraph-ai/output/DemoSet",
        ],
    )

    assert result.exit_code == 0, result.stdout
    assert captured["dataset"] == "DemoSet"
    assert captured["file_name"] == "note.txt"
    assert captured["bucket"] == "bucket"
    assert captured["input_prefix"] == "opengraph-ai/input"
    assert captured["output_prefix"] == "opengraph-ai/output"


def test_extract_tables_gcs_invokes_cloud_run_dataset_workflow(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_run(**kwargs):
        captured.update(kwargs)
        return {
            "dataset": "Airline+Loyalty+Program",
            "gcs_input_uri": "gs://bucket/opengraph-ai/input/Airline+Loyalty+Program",
            "gcs_json_uri": "gs://bucket/opengraph-ai/output/Airline+Loyalty+Program/graph.json",
            "gcs_png_uri": "gs://bucket/opengraph-ai/output/Airline+Loyalty+Program/graph.png",
            "stored_node_count": 1,
            "stored_edge_count": 0,
            "entity_count": 1,
            "relationship_count": 0,
            "graph_json": {"entities": [], "relationships": []},
        }

    monkeypatch.setattr("cli.commands.extract.run_graph_from_gcs_via_cloud_run", fake_run)

    result = runner.invoke(
        get_command(cli_app),
        [
            "extract",
            "tables-gcs",
            "Airline+Loyalty+Program",
            "--bucket",
            "bucket",
            "--project-id",
            "proj",
        ],
    )

    assert result.exit_code == 0, result.stdout
    assert captured["dataset"] == "Airline+Loyalty+Program"
    assert captured["bucket"] == "bucket"
    assert captured["project_id"] == "proj"
    assert captured["input_prefix"] == "opengraph-ai/input"
