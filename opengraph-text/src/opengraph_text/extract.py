"""Extract entities, topics, attributes, and claims from documents via Claude."""

from __future__ import annotations

import sys
from pathlib import Path

import anthropic
from dotenv import load_dotenv

from opengraph_text.schema import DocumentExtraction, validate_extraction

load_dotenv(override=True)

_MAX_CHARS = 20000

_SYSTEM_PROMPT = """\
You are a precise textual knowledge-graph extractor. Analyze the provided document and call \
`submit_extraction` with a complete, structured extraction.

Guidelines:
- **Entities**: Extract people, organizations, places, products, concepts, and events mentioned \
in the document. Assign a unique snake_case `id` derived from the label; append _1, _2, ... when \
the same label appears more than once (e.g. "jane_doe_1", "jane_doe_2").
- **Topics**: Propose the high-level subjects the document discusses, e.g. "machine_learning", \
"venture_capital". Topics are not a closed vocabulary; propose them freely based on content.
- **Attributes**: Extract key/value attributes (role, industry, location, size, founded, status, \
description) for the document as a whole and/or for prominent entities. Use concise values.
- **Claims**: Extract short (at most 200 characters), literal or near-verbatim assertions from \
the text, one ClaimNode per assertion.
- **Edges**: Wire every node into the graph:
  - A ContainsEdge per detected entity (source = document id).
  - An AboutTopicEdge per topic (source = document id).
  - A HasAttributeEdge per attribute (source = document id or entity id).
  - A StatesEdge per claim (source = document id).
  - RelatesToEdges for clear relationships between entities, using the controlled relation \
vocabulary (works_at, founded, invested_in, acquired, located_in, part_of, competitor_of, \
collaborates_with, mentions).
- **IDs**: Stable, descriptive snake_case. All IDs must be globally unique within the extraction.
- **Confidence**: 0.0-1.0. Prefer 0.7-0.95 for clear extractions; lower for ambiguous ones.

Call `submit_extraction` exactly once with a complete, self-consistent extraction.
"""


def _read_text(path: Path) -> str:
    if path.suffix.lower() == ".pdf":
        from pypdf import PdfReader

        reader = PdfReader(path)
        pages = [(page.extract_text() or "").strip() for page in reader.pages]
        text = "\n\n".join(page for page in pages if page)
        if not text.strip():
            raise ValueError(f"No extractable text found in PDF: {path}")
        return text
    return path.read_text(encoding="utf-8", errors="ignore")


def extract_document(document_path: Path, client: anthropic.Anthropic) -> DocumentExtraction:
    """Extract a knowledge graph from a single document using Claude."""
    text = _read_text(document_path)
    word_count = len(text.split())
    doc_format = document_path.suffix.lower().lstrip(".")
    document_id = document_path.stem.replace(" ", "_").replace("-", "_").lower()

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4096,
        system=_SYSTEM_PROMPT,
        tools=[
            {
                "name": "submit_extraction",
                "description": "Submit the complete knowledge-graph extraction for the document.",
                "input_schema": DocumentExtraction.model_json_schema(),
            }
        ],
        tool_choice={"type": "tool", "name": "submit_extraction"},
        messages=[
            {
                "role": "user",
                "content": (
                    f"Extract the knowledge graph from this document.\n"
                    f"Use document id='{document_id}', path='{document_path}', "
                    f"word_count={word_count}, format='{doc_format}'.\n\n"
                    f"Document text:\n{text[:_MAX_CHARS]}"
                ),
            }
        ],
    )

    tool_use_block = next(
        (block for block in response.content if block.type == "tool_use"),
        None,
    )
    if tool_use_block is None:
        raise ValueError(f"Model did not call submit_extraction. Response: {response.content}")

    extraction = DocumentExtraction.model_validate(tool_use_block.input)

    errors = validate_extraction(extraction)
    if errors:
        raise ValueError("Extraction failed validation:\n" + "\n".join(errors))

    return extraction


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python -m opengraph_text.extract <document_path>", file=sys.stderr)
        sys.exit(1)

    _client = anthropic.Anthropic()
    _path = Path(sys.argv[1])
    _extraction = extract_document(_path, _client)
    print(_extraction.model_dump_json(indent=2))
