# opengraph-text Repository Structure

This document explains the layout and purpose of the `opengraph-text` package.

## Root

- `.env` / `.env.example`
  - Environment variable definitions, including `ANTHROPIC_API_KEY`.
- `.gitignore`
  - Git ignore rules for package artifacts.
- `README.md`
  - Project-level documentation and usage examples.
- `pyproject.toml`
  - Package metadata, dependencies, and entrypoint definitions.
- `repo_structure.md`
  - This walkthrough.

## `src/opengraph_text`

The package source code is under `src/opengraph_text`.

### `__init__.py`
- Minimal package initialization and general module docstring.

### `cli.py`
- `typer`-based command-line interface.
- Provides commands such as `build` and `summary`.
- `build(folder)` extracts documents from a folder and writes `opengraph-out/graph.json`.
- `summary(folder)` loads the saved graph and prints summary statistics.

### `extract.py`
- Contains the document extraction workflow.
- Supports `.txt`, `.md`, and `.pdf` files.
- Uses the Anthropic API to call a Claude model and extract a structured `DocumentExtraction` payload.
- Validates the extracted graph payload against Pydantic models.

### `graph.py`
- Defines the `DocumentGraph` and graph construction utilities.
- `DocumentGraph` stores a `networkx.MultiDiGraph` of documents, entities, topics, attributes, claims, and edges.
- `build_graph_from_folder(folder, output)` extracts all supported documents and saves `graph.json`.
- Graph nodes are merged across documents by normalized entity/topic/attribute labels.
- Provides `summary()` and JSON serialization support.

### `query.py`
- Implements a simple natural-language query interface over a built text graph.
- Uses keyword matching against node labels and document names.
- Returns a JSON-safe result with `question`, `answer`, `graph_nodes`, `graph_edges`, and `matched_nodes`.

### `schema.py`
- Defines the schema for extracted document graphs.
- `DocumentNode`, `EntityNode`, `TopicNode`, `AttributeNode`, and `ClaimNode` are defined with strict validation.
- Edge models ensure valid structure for relationships such as `contains`, `about_topic`, `has_attribute`, `states`, and `relates_to`.
- `DocumentExtraction` represents the full extraction for a single document.
- `validate_extraction()` verifies unique node IDs and consistent edge references.

### `server.py`
- Implements the MCP server using the official Python MCP SDK with `FastMCP`.
- Exposes tools:
  - `build_graph(folder_path)`
  - `query_graph(question, graph_path="")`
  - `get_document_entities(document_filename, graph_path="")`
  - `list_documents(graph_path="")`
  - `graph_summary(graph_path="")`
- Uses `dotenv.load_dotenv(override=True)` to load environment variables from `.env`.
- Lazily instantiates Anthropic clients inside tool functions.
- Uses standard I/O transport for MCP.

## `tests`

Contains package tests, including:

- `test_extract.py`
- `test_graph.py`
- `test_schema.py`
- `test_server.py`

`test_server.py` validates the MCP server with an in-process MCP client session.

## Package hooks

`pyproject.toml` defines these scripts:

- `opengraph-text` → `opengraph_text.cli:app`
- `opengraph-text-mcp` → `opengraph_text.server:main`

This package is designed to ingest text documents, build a linked knowledge graph, and expose both CLI and MCP server interfaces for querying and inspection.
