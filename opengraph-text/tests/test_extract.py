"""Tests for opengraph_text.extract."""

from pathlib import Path

import anthropic

from opengraph_text.extract import extract_document
from opengraph_text.schema import DocumentExtraction, validate_extraction

SAMPLE_DOC = Path(__file__).parent / "sample_documents" / "test_doc.txt"


def test_extract_document_returns_valid_extraction():
    client = anthropic.Anthropic()

    extraction = extract_document(SAMPLE_DOC, client)

    assert isinstance(extraction, DocumentExtraction)
    assert extraction.document.id == "test_doc"
    assert extraction.document.format == "txt"
    assert extraction.entities != []
    assert validate_extraction(extraction) == []
