"""Extract entities and relationships from images via Claude vision."""

from __future__ import annotations

import base64
import io
import sys
from pathlib import Path

import anthropic
from dotenv import load_dotenv
from PIL import Image

from opengraph_image.schema import ImageExtraction, validate_extraction

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
load_dotenv(_PROJECT_ROOT / ".env", override=True)

_MAX_LONG_EDGE = 1568

_SYSTEM_PROMPT = """\
You are a precise visual knowledge-graph extractor. Analyze the provided image and call \
`submit_extraction` with a complete, structured extraction.

Guidelines:
- **Objects**: Be SPECIFIC with labels — use fine-grained species/breed/model names in snake_case \
(e.g. "golden_retriever" not "dog", "oak_tree" not "tree", "toyota_prius" not "car"). Assign a \
unique snake_case `id`; append _1, _2, ... when the same label appears more than once (e.g. \
"labrador_retriever_1", "labrador_retriever_2"). Provide normalized [x, y, w, h] bounding boxes \
(values in [0,1]) wherever possible.
- **Scene**: Pick exactly one scene label from the controlled vocabulary that best describes the \
overall context.
- **Attributes**: Extract color, material, mood, lighting, style, and/or size for the image as a \
whole and for prominent objects. Use concise lowercase values.
- **Text spans**: Transcribe ALL visible text accurately, one TextSpanNode per distinct text region.
- **Edges**: Wire every node into the graph:
  - A ContainsEdge per detected object (source = image id).
  - Exactly one InSceneEdge (source = image id).
  - A HasAttributeEdge per attribute (source = image id or object id).
  - A HasTextEdge per text span (source = image id).
  - RelatedToEdges for any clear spatial or semantic relationships between objects.
- **IDs**: Stable, descriptive snake_case. All IDs must be globally unique within the extraction.
- **Confidence**: 0.0–1.0. Prefer 0.7–0.95 for clear detections; lower for ambiguous ones.

Call `submit_extraction` exactly once with a complete, self-consistent extraction.
"""


def _resize_if_needed(img: Image.Image) -> Image.Image:
    long_edge = max(img.width, img.height)
    if long_edge <= _MAX_LONG_EDGE:
        return img
    scale = _MAX_LONG_EDGE / long_edge
    return img.resize((int(img.width * scale), int(img.height * scale)), Image.LANCZOS)


def extract_image(image_path: Path, client: anthropic.Anthropic) -> ImageExtraction:
    """Extract a knowledge-graph from a single image using Claude vision."""
    img = Image.open(image_path)
    original_format = img.format or "JPEG"
    orig_width, orig_height = img.width, img.height

    img = _resize_if_needed(img.convert("RGB"))

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=90)
    image_b64 = base64.standard_b64encode(buf.getvalue()).decode()

    image_id = image_path.stem.replace(" ", "_").replace("-", "_").lower()

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4096,
        system=_SYSTEM_PROMPT,
        tools=[
            {
                "name": "submit_extraction",
                "description": "Submit the complete knowledge-graph extraction for the image.",
                "input_schema": ImageExtraction.model_json_schema(),
            }
        ],
        tool_choice={"type": "tool", "name": "submit_extraction"},
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/jpeg",
                            "data": image_b64,
                        },
                    },
                    {
                        "type": "text",
                        "text": (
                            f"Extract the knowledge graph from this image.\n"
                            f"Use image id='{image_id}', path='{image_path}', "
                            f"width={orig_width}, height={orig_height}, "
                            f"format='{original_format}'."
                        ),
                    },
                ],
            }
        ],
    )

    tool_use_block = next(
        (block for block in response.content if block.type == "tool_use"),
        None,
    )
    if tool_use_block is None:
        raise ValueError(f"Model did not call submit_extraction. Response: {response.content}")

    extraction = ImageExtraction.model_validate(tool_use_block.input)

    errors = validate_extraction(extraction)
    if errors:
        raise ValueError("Extraction failed validation:\n" + "\n".join(errors))

    return extraction


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python -m opengraph_image.extract <image_path>", file=sys.stderr)
        sys.exit(1)

    _client = anthropic.Anthropic()
    _path = Path(sys.argv[1])
    _extraction = extract_image(_path, _client)
    print(_extraction.model_dump_json(indent=2))
