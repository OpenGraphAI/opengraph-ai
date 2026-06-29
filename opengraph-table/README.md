# OpenGraph Table

A Python module for extracting knowledge graphs from tabular data (CSV, Excel, images) using Claude AI vision capabilities. Extract structured information from tables and build interconnected knowledge graphs with entity relationships, metrics, and metadata tracking.

## Features

- **Automatic Table Extraction**: Use Claude Sonnet 4.6 vision API to extract tables from images
- **Multi-table Knowledge Graphs**: Combine tables into unified knowledge graphs with automatic entity deduplication
- **Source Provenance Tracking**: Track all data back to source tables, sheets, and cell locations
- **Natural-Language Querying**: Ask questions about your knowledge graph in plain English
- **Multiple Output Formats**: Generate JSON (for programmatic use), HTML (for visualization), and Markdown reports
- **Incremental Updates**: Load and update existing graphs without starting from scratch
- **Comprehensive Schema**: Extract entities, relationships, metrics, notes, and column metadata

## Installation

```bash
# Clone the repository
git clone https://github.com/user/opengraph-ai.git
cd opengraph-ai/opengraph-table

# Install in development mode
pip install -e .
```

### Requirements

- Python 3.11+
- Anthropic API key (for Claude access)
- Dependencies: pydantic >= 2.13.4, typer >= 0.26.7, networkx, pandas, jinja2, markdown

## Quick Start

### 1. Extract Tables from Images

```bash
# Place table images in a folder
opengraph-table build /path/to/tables/

# Output files created:
# - /path/to/tables/opengraph-out/graph.json      (NetworkX graph)
# - /path/to/tables/opengraph-out/graph.html      (Visualization)
# - /path/to/tables/opengraph-out/graph.md        (Report)
```

### 2. View Graph Statistics

```bash
opengraph-table summary /path/to/graph.json
```

### 3. Query Your Knowledge Graph

```bash
opengraph-table query /path/to/graph.json \
  --question "What are the main entities in this dataset?"
```

### 4. Add More Tables Incrementally

```bash
opengraph-table ingest /path/to/new/tables/ \
  --graph /path/to/graph.json
```

## Usage

### Python API

```python
from opengraph_table.graph import TableGraph, build_graph_from_tables
from opengraph_table.extract import extract_table
from opengraph_table.query import query_graph
import anthropic

# Extract a single table
client = anthropic.Anthropic()
extraction = extract_table("/path/to/table.jpg", client)
print(extraction.entities)

# Build graph from multiple tables
graph = build_graph_from_tables(
    folder="/path/to/tables",
    output_prefix="/path/to/output/graph",
    merge=True
)

# Query the graph
result = query_graph(
    "What companies are mentioned?",
    "/path/to/graph.json"
)
print(result["answer"])
```

### CLI Commands

#### Build a Knowledge Graph

```bash
opengraph-table build /path/to/tables/
```

Options:
- `--output PATH`: Custom output path (default: `{folder}/opengraph-out/graph`)

#### View Graph Summary

```bash
opengraph-table summary /path/to/graph.json
```

Shows:
- Total nodes and edges
- Node types and counts
- Relation types
- Top nodes by degree

#### Query the Graph

```bash
opengraph-table query /path/to/graph.json --question "Your question here"
```

#### Incrementally Ingest New Data

```bash
opengraph-table ingest /path/to/new/tables/ --graph /path/to/graph.json
```

## Schema Overview

### Core Models

**TableExtraction**: Complete extraction from a single table
- `source`: Table metadata (filename, sheet, page, etc.)
- `columns`: Column definitions with data types
- `rows`: Row data with cell values
- `entities`: Extracted entities with attributes
- `relationships`: Entity-to-entity relationships
- `metrics`: Computed metrics (sums, averages, counts, etc.)
- `notes`: Annotations and insights

**TableEntity**: Represents an entity extracted from table data
- `id`: Unique identifier within source
- `name`: Entity name
- `entity_type`: Category (company, person, product, etc.)
- `source_cells`: Original cell locations
- `attributes`: Key-value pairs
- `confidence`: Extraction confidence (0.0-1.0)

**TableRelationship**: Connection between two entities
- `source_entity_id`: From entity
- `target_entity_id`: To entity
- `relation_type`: Relationship type
- `confidence`: Relationship confidence

**TableSource**: Provenance metadata
- `id`: Unique source identifier
- `filename`: Original file
- `sheet_name`: Sheet/tab name (if applicable)
- `page_index`: Page number (if from PDF/image)
- `table_index`: Table position within page
- `extracted_at`: ISO timestamp of extraction

## Output Formats

### graph.json
NetworkX graph in node-link format with:
- Node definitions (type, attributes, source references)
- Edge definitions (relationships, confidence scores)
- Source metadata
- Summary statistics

```json
{
  "graph": {
    "directed": true,
    "multigraph": false,
    "nodes": [...],
    "edges": [...],
    "metadata": {...}
  },
  "sources": {...},
  "metadata": {
    "total_nodes": 42,
    "total_edges": 67,
    "node_count_by_type": {...},
    "relation_count": {...}
  }
}
```

### graph.html
Interactive HTML visualization showing:
- Node statistics and types
- Entity listings with attributes
- Relationship network
- Source information

Open in any web browser.

### GRAPH_REPORT.md
Human-readable Markdown report with:
- Extraction summary
- Entity descriptions
- Relationship overview
- Data quality notes

## Architecture

### Load-First Pattern

The graph building system follows a load-first pattern:
1. Check if `graph.json` exists
2. If yes, load existing graph and metadata
3. Extract new table data
4. Merge new entities with existing graph (deduplicate by name + type + attributes)
5. Save updated graph

This enables incremental graph building from multiple sources.

### Entity Merging

Entities are deduplicated across tables by:
1. **Name normalization**: Convert to lowercase and strip whitespace
2. **Type matching**: Entity types must match exactly
3. **Confidence-based selection**: Higher confidence entities remain canonical

Related edges are automatically repointed to canonical entities.

### Node Scoping

Each node ID includes source scoping to prevent collisions:
- `source_001__entity_1` → Entity from specific source
- `source_001__col_0_product_id` → Column from specific source
- `source_001__metric_1` → Metric from specific source

## Testing

Run the test suite:

```bash
pytest tests/

# With coverage
pytest --cov=opengraph_table tests/
```

Test files:
- `tests/test_schema.py`: Pydantic model validation
- `tests/test_graph.py`: Graph operations, merging, I/O

## MCP Integration

The module includes a Model Control Protocol (MCP) server for integration with other systems:

```bash
opengraph-table-mcp
```

Available MCP tools:
- `extract_table`: Extract a single table
- `build_graph`: Build graph from folder
- `query_graph`: Query with natural language

## Environment Setup

Set your Anthropic API key:

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
```

## Examples

### Example 1: Extract Company Information from Multiple CSVs

```bash
# Place CSV files as images or in standard format
opengraph-table build ./company_data/

# Query the result
opengraph-table query ./company_data/opengraph-out/graph.json \
  --question "What companies are in the database?"
```

### Example 2: Track Data Provenance

```python
from opengraph_table.graph import TableGraph

# Load existing graph
graph = TableGraph()
graph.load("./data/graph.json")

# Check which source each entity comes from
for node_id, attrs in graph._g.nodes(data=True):
    if attrs.get('type') == 'entity':
        source = attrs.get('source')
        print(f"{attrs['name']} comes from {source}")
```

### Example 3: Incremental Data Ingestion

```bash
# Build initial graph
opengraph-table build ./initial_data/

# Add more tables later
opengraph-table ingest ./additional_data/ \
  --graph ./initial_data/opengraph-out/graph.json
```

## Limitations

- Extract.py uses Claude vision API (image dimension limits apply)
- Entity deduplication is heuristic-based; manual review recommended for critical applications
- Large graphs (10,000+ nodes) may require optimization for performance

## Contributing

Contributions welcome! Please:
1. Add tests for new features
2. Follow existing code style (black, isort)
3. Update documentation
4. Test with sample data before submitting PR

## License

See LICENSE file in parent repository.

## Related Projects

- **opengraph-image**: Extract knowledge graphs from images of objects and scenes
- **opengraph-ai**: Main project umbrella with CLI and Cloud Run infrastructure
