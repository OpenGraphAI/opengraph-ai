# OpenGraph AI MCP Server

The OpenGraph AI MCP (Model Context Protocol) server exposes graph extraction, querying, and visualization tools to AI agents like Claude Code and Cursor.

## Overview

The MCP server bridges OpenGraph AI's Python CLI with agent runtimes, allowing Claude and other MCP clients to:
- Extract entities and relationships from text
- Query saved knowledge graphs
- Visualize graphs as PNG images
- Run end-to-end extraction pipelines

## Installation

### Prerequisites
- Node.js 20+
- npm
- OpenGraph AI Python environment configured (see root [README.md](../README.md))

### Setup

```bash
cd mcp-server
npm install
npm run build
```

## Running the Server

### Development Mode
```bash
npm run dev
```

Output:
```
> opengraph-mcp-server@0.1.0 dev
> tsx index.ts
MCP server online
```

### Production Mode
```bash
npm run start
```

The server uses stdio transport and automatically connects to Claude/Cursor when configured.

## Configuration

### Claude Code / Cursor Setup

Add to your `.cursor/settings.json` or Claude Code MCP configuration:

```json
{
  "mcpServers": {
    "opengraph": {
      "command": "npm",
      "args": ["run", "start"],
      "cwd": "/Users/d/Documents/GitHub/opengraph-ai/mcp-server"
    }
  }
}
```

Or use absolute path to the built version:
```json
{
  "mcpServers": {
    "opengraph": {
      "command": "node",
      "args": ["/Users/d/Documents/GitHub/opengraph-ai/mcp-server/dist/index.js"],
      "cwd": "/Users/d/Documents/GitHub/opengraph-ai"
    }
  }
}
```

**Important**: Ensure your OpenGraph AI `.env.local` has the required secrets:
- `OPENAI_API_KEY` (for LLM-backed extraction)
- `GCS_BUCKET`, `GCP_PROJECT_ID` (for GCS workflows)
- `NEO4J_URI`, `NEO4J_USERNAME`, `NEO4J_PASSWORD` (for graph database)

## Tools

### 1. `extract_text`

Extract entities and relationships from free-form text.

**Parameters:**
- `text` (string, required): The text to extract from
- `use_llm` (boolean, optional): Use OpenAI LLM (true) or regex heuristics (false). Default: false

**Example:**
```
User: Use the extract_text tool to extract entities from this text:
"Alice Johnson founded Acme Corporation in London in 2020. Acme acquired Beta Labs in 2021."
```

**Output:**
```json
{
  "entities": [
    {"id": "alice-johnson", "label": "Alice Johnson", "type": "person"},
    {"id": "acme-corporation", "label": "Acme Corporation", "type": "org"},
    {"id": "london", "label": "London", "type": "place"},
    {"id": "beta-labs", "label": "Beta Labs", "type": "org"}
  ],
  "relationships": [
    {"source": "alice-johnson", "target": "acme-corporation", "relation": "founded"},
    {"source": "acme-corporation", "target": "beta-labs", "relation": "acquired"}
  ]
}
```

### 2. `query_graph`

Search a previously extracted and saved graph JSON for entities.

**Parameters:**
- `dataset` (string, required): Dataset name (e.g., 'text_example', 'table_example')
- `query` (string, required): Search term for entities (fuzzy match)

**Example:**
```
User: Query the text_example graph for "alice"
```

**Output:**
```
Query results for 'alice' in dataset 'text_example':
  - alice-johnson [person]: Alice Johnson (neighbors: 2)
```

### 3. `visualize_graph`

Render a saved graph JSON as a PNG image.

**Parameters:**
- `dataset` (string, required): Dataset name
- `output_path` (string, required): Local file path where PNG will be saved

**Example:**
```
User: Visualize the text_example graph and save it to /tmp/graph.png
```

**Output:**
```
Saved graph visualization to /tmp/graph.png (1024x768, 47 nodes, 12 relationships)
```

### 4. `demo_pipeline`

Run the full extraction pipeline on a text file or table folder.

**Parameters:**
- `source_path` (string, required): Path to a `.txt` file or folder containing CSV tables
- `use_llm` (boolean, optional): Use LLM for table extraction. Default: false

**Example:**
```
User: Run the demo pipeline on examples/text_example.txt
```

**Output:**
```
Reading examples/text_example.txt ...
Extracting entities and relationships (offline mode) ...
Building graph ...

Nodes (47):
  [alice] Alice [person]
  [acme] Acme [org]
  ...

Edges (12):
  alice --[founded]--> acme
  ...

Saved graph JSON to output/text_example/graph.json
```

## Usage Examples

### Example 1: Text Extraction & Analysis

```
Claude: Extract entities from this research summary:
"Dr. Sarah Chen at MIT developed a novel quantum algorithm. The research was funded by NSF and published in Nature."

Then query the graph for "MIT".
```

The MCP server will:
1. Extract entities (Dr. Sarah Chen, MIT, NSF, Nature)
2. Identify relationships (developed, funded by, published in)
3. Query for MIT and return neighbors and connections

### Example 2: Graph Visualization

```
Claude: Extract entities from the text_example dataset, then visualize the graph and show me the output path.
```

Output:
```
Graph saved to: /Users/d/Documents/GitHub/opengraph-ai/output/text_example/graph.json
PNG saved to: /Users/d/Documents/GitHub/opengraph-ai/output/text_example/graph.png
```

### Example 3: Table Analysis

```
Claude: Process the examples/table_example folder (CSV tables) using the demo pipeline, then visualize the schema.
```

### Example 4: Multi-step Workflow

```
Claude: 
1. Extract entities from the text "Apple Inc. was founded by Steve Jobs. Tim Cook is now the CEO."
2. Query the graph for "Apple"
3. Show me the relationships
```

## Troubleshooting

### "MCP server online" but Claude doesn't see tools

**Solution:**
- Verify MCP config path is correct
- Restart Claude/Cursor
- Check that npm dependencies are installed: `npm install`
- Ensure server is built: `npm run build`

### "Unknown tool" error

**Cause:** Tool name doesn't match exactly
**Solution:** Check tool name matches one of: `extract_text`, `query_graph`, `visualize_graph`, `demo_pipeline`

### LLM extraction fails with "OPENAI_API_KEY is not set"

**Solution:**
- Verify `.env.local` has `OPENAI_API_KEY` set in the project root
- Ensure the MCP server is started from a directory where `.env.local` is accessible
- The Python CLI loads environment variables automatically

### Query returns no results

**Cause:** Dataset hasn't been extracted yet
**Solution:**
- First run `extract_text` or `demo_pipeline` to generate graph JSON
- Verify dataset name matches the output folder (e.g., `text_example`)

### Graph visualization fails

**Cause:** Missing dependencies or invalid dataset
**Solution:**
- Ensure `matplotlib` and `networkx` are installed in Python environment
- Check that dataset graph.json exists in output folder
- Verify output path is writable

## Architecture

```
Claude/Cursor
    ↓ (stdio)
MCP Server (Node.js)
    ↓ (spawn subprocess)
Python CLI (.venv/bin/python -m cli)
    ↓ (imports)
OpenGraph Engine (Python)
    - Text/Table Extractors
    - Graph Builders
    - Query Engines
    - Neo4j Connectors
    - GCS Uploaders
```

## Development

### Adding a New Tool

1. Add tool to `tools/index.ts` in the `TOOLS` array
2. Implement handler in `tools/handlers.ts`
3. Add case to switch statement in `index.ts`
4. Rebuild: `npm run build`

### Example: Add a new "summarize_graph" tool

**tools/index.ts:**
```typescript
{
  name: "summarize_graph",
  description: "Generate a summary of a graph's entities and relationships",
  inputSchema: {
    type: "object",
    properties: {
      dataset: { type: "string", description: "Dataset name" },
    },
    required: ["dataset"],
  },
}
```

**tools/handlers.ts:**
```typescript
export async function summarizeGraph(dataset: string): Promise<string> {
  return spawnPythonCLI(["query", dataset, "*"]);
}
```

**index.ts:**
```typescript
case "summarize_graph":
  result = await summarizeGraph((args as any).dataset);
  break;
```

## Performance Considerations

- **Text extraction**: Large texts (>100KB) are chunked automatically
- **LLM calls**: Each chunk makes an API call; concurrent calls are batched
- **Graph visualization**: Large graphs (>500 nodes) may take 5-10 seconds
- **Neo4j operations**: Requires active database connection

## Limitations

- Text files are limited to UTF-8 encoding
- CSV tables must have consistent column headers
- Graph visualization works best with <1000 nodes
- LLM extraction requires OpenAI API credits
- GCS workflows require GCP credentials and network access

## Support

For issues or feature requests, see the main [README.md](../README.md) and [CLI_COMMANDS.md](../CLI_COMMANDS.md).
