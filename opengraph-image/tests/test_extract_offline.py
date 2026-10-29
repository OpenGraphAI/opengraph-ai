"""Offline tests for opengraph_image.extract against a mocked Messages API."""

import json
from pathlib import Path

import anthropic
import httpx
import pytest

from opengraph_image.extract import DEFAULT_MODEL, ExtractionError, extract_image
from opengraph_image.schema import ImageExtraction

_DOG_IMAGE = Path(__file__).parent / "sample_images" / "test_dog.jpg"

_EXTRACTION = {
    "image": {"id": "test_dog", "path": str(_DOG_IMAGE), "width": 10, "height": 10, "format": "JPEG"},
    "objects": [{"id": "dog_1", "label": "golden_retriever", "confidence": 0.9, "bounding_box": [0.1, 0.1, 0.5, 0.5]}],
    "scenes": [{"id": "scene_1", "label": "outdoor", "confidence": 0.8}],
    "attributes": [],
    "text_spans": [],
    "contains_edges": [{"source": "test_dog", "target": "dog_1", "confidence": 0.9}],
    "in_scene_edges": [{"source": "test_dog", "target": "scene_1", "confidence": 0.8}],
    "has_attribute_edges": [],
    "has_text_edges": [],
    "related_to_edges": [],
}


def _client(text: str, stop_reason: str = "end_turn", requests: list | None = None) -> anthropic.Anthropic:
    def handler(request: httpx.Request) -> httpx.Response:
        if requests is not None:
            requests.append(json.loads(request.content))
        return httpx.Response(200, json={
            "id": "msg_test", "type": "message", "role": "assistant", "model": "claude-test",
            "content": [{"type": "text", "text": text}] if text else [],
            "stop_reason": stop_reason, "stop_sequence": None,
            "usage": {"input_tokens": 1200, "output_tokens": 340},
        })

    return anthropic.Anthropic(api_key="test", max_retries=0, http_client=httpx.Client(transport=httpx.MockTransport(handler)))


def test_requests_structured_output_instead_of_forced_tool_use() -> None:
    requests: list = []
    extraction = extract_image(_DOG_IMAGE, _client(json.dumps(_EXTRACTION), requests=requests))

    assert isinstance(extraction, ImageExtraction)
    assert extraction.objects[0].label == "golden_retriever"
    body = requests[0]
    assert "tool_choice" not in body and "tools" not in body
    assert body["output_config"]["format"]["type"] == "json_schema"
    assert body["model"] == DEFAULT_MODEL


def test_model_and_max_tokens_are_configurable() -> None:
    requests: list = []
    extract_image(_DOG_IMAGE, _client(json.dumps(_EXTRACTION), requests=requests), model="claude-sonnet-5-5", max_tokens=16000)

    assert requests[0]["model"] == "claude-sonnet-5-5"
    assert requests[0]["max_tokens"] == 16000


@pytest.mark.parametrize(("stop_reason", "text", "reason"), [
    ("refusal", "", "refused"),
    ("max_tokens", json.dumps(_EXTRACTION)[:60], "truncated"),
    ("end_turn", "{\"image\": 5}", "invalid"),
])
def test_unusable_responses_raise_a_classified_error(stop_reason: str, text: str, reason: str) -> None:
    with pytest.raises(ExtractionError) as caught:
        extract_image(_DOG_IMAGE, _client(text, stop_reason))

    assert caught.value.reason == reason
    assert caught.value.stop_reason == stop_reason
    assert isinstance(caught.value, ValueError)


def test_referential_errors_are_reported_as_invalid() -> None:
    broken = {**_EXTRACTION, "contains_edges": [{"source": "test_dog", "target": "missing", "confidence": 0.9}]}

    with pytest.raises(ExtractionError, match="unknown target") as caught:
        extract_image(_DOG_IMAGE, _client(json.dumps(broken)))

    assert caught.value.reason == "invalid"
