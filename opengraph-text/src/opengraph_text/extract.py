"""Extract entities and relationships from a single text document via Claude."""

from __future__ import annotations

import sys
from pathlib import Path

import anthropic
from dotenv import load_dotenv

from opengraph_text.schema import DocumentExtraction, validate_extraction

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
load_dotenv(_PROJECT_ROOT / ".env", override=True)

_SYSTEM_PROMPT = """\
You are a precise text knowledge-graph extractor. Analyze the provided document and call
`submit_extraction` with a complete, structured extraction.

Guidelines:
- Extract important entities, concepts, sections, text chunks, attributes, and relationships.
- Use stable, descriptive snake_case IDs.
- Every edge source and target must reference an existing node ID.
- Confidence values must be between 0.0 and 1.0.
- Return one complete, self-consistent extraction.

Call `submit_extraction` exactly once.
"""


def _read_text(document_path: Path) -> str:
    """Read a UTF-8 text document from disk."""
    return document_path.read_text(encoding="utf-8")


def extract_document(document_path: Path, client: anthropic.Anthropic) -> DocumentExtraction:
    """Extract a knowledge graph from a single text document."""
    document_text = _read_text(document_path)
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
                    f"Use document id='{document_id}' and path='{document_path}'.\n\n"
                    f"Document text:\n{document_text}"
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