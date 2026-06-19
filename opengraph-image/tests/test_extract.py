"""Integration test for opengraph_image.extract — calls the real Claude vision API."""

import os
from pathlib import Path

import anthropic
import pytest

from opengraph_image.extract import extract_image
from opengraph_image.schema import ImageExtraction, validate_extraction

_SAMPLE_DIR = Path(__file__).parent / "sample_images"
_DOG_IMAGE = _SAMPLE_DIR / "test_dog.jpg"


@pytest.fixture(scope="module")
def client() -> anthropic.Anthropic:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        pytest.skip("ANTHROPIC_API_KEY not set")
    return anthropic.Anthropic(api_key=api_key)


def test_extract_dog_image(client: anthropic.Anthropic) -> None:
    """extract_image returns a valid extraction with at least one detected object."""
    extraction = extract_image(_DOG_IMAGE, client)

    assert isinstance(extraction, ImageExtraction)
    assert len(extraction.objects) > 0, "Expected at least one detected object"
    errors = validate_extraction(extraction)
    assert errors == [], f"Extraction failed validation: {errors}"
