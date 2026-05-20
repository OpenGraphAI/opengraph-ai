"""Tests for the Cloud Run service endpoint that runs the graph workflow."""

from fastapi.testclient import TestClient

from api.main import app


client = TestClient(app)


def test_graph_from_gcs_endpoint_returns_workflow_result(monkeypatch) -> None:
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

    monkeypatch.setattr("api.routes.run_graph_from_gcs_workflow", fake_workflow)

    response = client.post(
        "/graph/from-gcs",
        json={"dataset": "DemoSet", "model": "gpt-4o-mini"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["dataset"] == "DemoSet"
    assert payload["entity_count"] == 1
    assert payload["graph_json"]["metadata"]["dataset"] == "DemoSet"


def test_graph_from_gcs_endpoint_returns_400_on_workflow_error(monkeypatch) -> None:
    def fake_workflow(**kwargs):
        del kwargs
        raise EnvironmentError("GCS_BUCKET is not set")

    monkeypatch.setattr("api.routes.run_graph_from_gcs_workflow", fake_workflow)

    response = client.post("/graph/from-gcs", json={"dataset": "DemoSet"})

    assert response.status_code == 400
    assert response.json()["detail"] == "GCS_BUCKET is not set"