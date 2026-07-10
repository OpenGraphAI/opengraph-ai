"""Extract structured data from text using Anthropic's vision API."""

from __future__ import annotations

import json
import re
import sys
import warnings
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(override=True)  # .env wins over shell env vars

import anthropic
from pypdf import PdfReader

from .schema import DocumentExtraction, validate_extraction

MODEL = "claude-sonnet-4-6"
MAX_WORDS = 10_000

_SLUG_RE = re.compile(r"[^a-z0-9]+")

SYSTEM_PROMPT = """\
You are a knowledge-graph extraction engine. Given the full text of a single \
document, extract a structured graph of entities, topics, attributes, claims, \
and relationships by calling the `submit_extraction` tool exactly once.

## Entities
Identify named entities mentioned in the document: people, organizations, \
places, products, concepts, and events. For each entity, assign a stable, \
snake_case `id` that would naturally match the same entity if it appeared in \
a different document (e.g. "anthropic", "sam_altman", "san_francisco"). \
Prefer SPECIFIC labels over generic ones: use "openai" rather than "company", \
and "sam_altman" rather than "ceo". If two distinct entities would otherwise \
collide on the same id (e.g. two different people named "john_smith"), \
disambiguate with a numeric suffix such as "john_smith_1" and "john_smith_2".

## Topics
Identify the top 1 to 3 topics that best describe what the document is about. \
Topics are not drawn from a closed vocabulary — propose free-form snake_case \
labels such as "machine_learning" or "venture_capital".

## Attributes
Extract attributes of the document and of individual entities using the \
controlled vocabulary: role, industry, location, size, founded, status, \
description. Attach each attribute to the document or entity it describes.

## Claims
Extract at most 5 key factual claims stated in the document. Each claim must \
be a direct, verbatim-style assertion under 200 characters — a single fact, \
not a summary of the whole document.

## Relationships
Extract relationships between entities using ONLY this controlled relation \
vocabulary: works_at, founded, invested_in, acquired, located_in, part_of, \
competitor_of, collaborates_with, mentions. Do not invent new relation types; \
if a relationship doesn't fit, either omit it or use "mentions".

## General instructions
- Every node id must be unique within the extraction and must be snake_case.
- Every edge's source and target must reference an id of a node you actually \
extracted (including the document node id, which will be provided to you).
- Assign a confidence score between 0.0 and 1.0 to every node and edge, \
reflecting how certain the extraction is.
- Call `submit_extraction` exactly once with the complete extraction. Do not \
respond with any text outside the tool call.
"""


def _slugify(stem: str) -> str:
    """Convert a filename stem into a lowercase snake_case identifier."""

    slug = _SLUG_RE.sub("_", stem.lower()).strip("_")
    return slug or "document"


def _read_document(document_path: Path) -> tuple[str, str]:
    """Read a document's text content.

    Returns a (text, format) tuple where format is one of "txt", "md", "pdf".
    """

    suffix = document_path.suffix.lower()

    if suffix in (".txt", ".md"):
        text = document_path.read_text(encoding="utf-8")
        doc_format = suffix.lstrip(".")
        return text, doc_format

    if suffix == ".pdf":
        reader = PdfReader(document_path)
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
        return text, "pdf"

    raise ValueError(
        f"Unsupported document extension {suffix!r} for {document_path}. "
        "Supported extensions are: .txt, .md, .pdf"
    )


def extract_document(document_path: Path, client: anthropic.Anthropic) -> DocumentExtraction:
    """Extract a structured knowledge graph from a single document."""

    document_path = Path(document_path)
    text, doc_format = _read_document(document_path)

    words = text.split()
    word_count = len(words)

    if word_count > MAX_WORDS:
        warnings.warn(
            f"{document_path.name} has {word_count} words; truncating to the "
            f"first {MAX_WORDS} words. Chunking is a v1 concern.",
            stacklevel=2,
        )
        text = " ".join(words[:MAX_WORDS])
        word_count = MAX_WORDS

    document_id = _slugify(document_path.stem)

    response = client.messages.create(
        model=MODEL,
        max_tokens=4096,
        system=SYSTEM_PROMPT,
        tools=[
            {
                "name": "submit_extraction",
                "description": (
                    "Submit the complete extracted knowledge graph for this document."
                ),
                "input_schema": DocumentExtraction.model_json_schema(),
            }
        ],
        tool_choice={"type": "tool", "name": "submit_extraction"},
        messages=[
            {
                "role": "user",
                "content": (
                    f"Document id: {document_id}\n"
                    f"Document path: {document_path}\n"
                    f"Document format: {doc_format}\n"
                    f"Word count: {word_count}\n\n"
                    f"Document text:\n\n{text}"
                ),
            }
        ],
    )

    tool_use_block = next(
        (block for block in response.content if block.type == "tool_use"
         and block.name == "submit_extraction"),
        None,
    )
    if tool_use_block is None:
        raise RuntimeError(
            f"Model did not call submit_extraction (stop_reason={response.stop_reason!r})"
        )

    extraction_input = dict(tool_use_block.input)
    extraction_input.setdefault("document", {})
    extraction_input["document"] = {
        **extraction_input["document"],
        "id": document_id,
        "path": str(document_path),
        "word_count": word_count,
        "format": doc_format,
    }

    extraction = DocumentExtraction.model_validate(extraction_input)

    errors = validate_extraction(extraction)
    if errors:
        raise ValueError(
            "Extraction failed validation:\n" + "\n".join(f"- {e}" for e in errors)
        )

    return extraction


def main() -> None:
    if len(sys.argv) != 2:
        print("Usage: python -m opengraph_text.extract <path/to/doc>", file=sys.stderr)
        raise SystemExit(1)

    document_path = Path(sys.argv[1])
    client = anthropic.Anthropic()

    extraction = extract_document(document_path, client)
    print(json.dumps(extraction.model_dump(mode="json"), indent=2))


if __name__ == "__main__":
    main()
