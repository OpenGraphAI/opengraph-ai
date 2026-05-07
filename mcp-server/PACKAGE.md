# OpenGraph AI MCP Server

[![npm version](https://img.shields.io/npm/v/opengraph-mcp.svg)](https://www.npmjs.com/package/opengraph-mcp)
[![npm downloads](https://img.shields.io/npm/dm/opengraph-mcp.svg)](https://www.npmjs.com/package/opengraph-mcp)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A Model Context Protocol (MCP) server that exposes semantic knowledge graph extraction and querying capabilities from the OpenGraph AI platform. Enables Claude and other AI agents to extract entities/relationships from text and CSV data, store them in Neo4j, and query the resulting knowledge graphs.

## Features

- **Text Extraction**: Extract entities and relationships from unstructured text using LLM-powered NER
- **Structured Data Extraction**: Extract graphs from CSV files in Google Cloud Storage
- **Knowledge Graph Querying**: Execute Cypher queries against Neo4j knowledge graphs
- **Graph Visualization**: Generate network visualizations as PNG images
- **Dataset Management**: List and manage multiple datasets with isolation
- **Progress Streaming**: Real-time progress updates during long-running operations
- **Integration**: Works with Claude, Cursor, and other MCP-compatible tools

## Installation

### NPM (Recommended)
```bash
npm install opengraph-mcp
npm start
```

### From Source
```bash
git clone https://github.com/your-org/opengraph-ai.git
cd opengraph-ai/mcp-server
npm install
npm run build
npm run start
```

## Configuration

### Environment Variables

Required:
```bash
export OPENAI_API_KEY=sk-...                    # OpenAI API key
export NEO4J_URI=neo4j+s://...                  # Neo4j AuraDB connection
export NEO4J_USERNAME=neo4j
export NEO4J_PASSWORD=...
export GCP_PROJECT_ID=user-account-493600      # Google Cloud project
export GOOGLE_APPLICATION_CREDENTIALS=...      # Path to GCP service account JSON
```

Optional:
```bash
export GCS_BUCKET=davidluobucket                # Default GCS bucket
export PYTHON_EXECUTABLE=/path/to/venv/bin/python3  # Python interpreter
```

### Claude / Cursor Configuration

Add to `.cursor/settings.json` or Claude settings:

```json
{
  "mcpServers": {
    "opengraph": {
      "command": "npm",
      "args": ["run", "start"],
      "cwd": "/path/to/opengraph-ai/mcp-server",
      "env": {
        "OPENAI_API_KEY": "${OPENAI_API_KEY}",
        "NEO4J_URI": "${NEO4J_URI}",
        "NEO4J_USERNAME": "neo4j",
        "NEO4J_PASSWORD": "${NEO4J_PASSWORD}"
      }
    }
  }
}
```

## Usage

### With Claude

The MCP server automatically exposes 7 tools to Claude:

1. **extract_text** - Extract entities/relationships from text
2. **extract_graph** - Extract from CSV in Google Cloud Storage
3. **query_graph** - Execute Cypher queries
4. **visualize_graph** - Generate network visualization
5. **summarize_graph** - Generate graph summary
6. **list_datasets** - List available datasets
7. **demo_pipeline** - Run complete extraction pipeline

**Example prompts:**

```
"Extract entities and relationships from this text:
'Apple Inc. was founded by Steve Jobs in 1976 in Silicon Valley.'"

"Extract the knowledge graph from the CSV files in gs://davidluobucket/User-DL/Airline+Loyalty+Program
and store it as the 'airline_loyalty' dataset"

"Query the airline_loyalty dataset to find the top 10 customers by loyalty points"

"Visualize the airline_loyalty dataset as a network graph"

"Summarize the main entities in the airline_loyalty dataset"
```

### Programmatically

```typescript
import { Client } from '@modelcontextprotocol/sdk/client/index.js';
import { StdioClientTransport } from '@modelcontextprotocol/sdk/client/stdio.js';

const transport = new StdioClientTransport({
  command: 'npm',
  args: ['run', 'start'],
  cwd: '/path/to/mcp-server',
});

const client = new Client(...);
await client.connect(transport);

// List tools
const tools = await client.listTools();

// Call a tool
const result = await client.callTool(
  {
    name: 'extract_text',
    arguments: { text: 'Your text here' },
  },
  undefined
);
```

## API Reference

### Tool: extract_text

Extract entities and relationships from unstructured text.

**Input:**
```typescript
{
  text: string;              // Text to extract from
  dataset_name?: string;     // Optional dataset name
}
```

**Output:**
```typescript
{
  type: 'text';
  text: JSON.stringify({
    status: 'success';
    message: 'Text extraction completed';
    data: {
      entities: Array<{ name: string; type: string; }>;
      relationships: Array<{ source: string; target: string; type: string; }>;
    };
    dataset: string;
  });
}
```

### Tool: extract_graph

Extract structured data from CSV files in Google Cloud Storage.

**Input:**
```typescript
{
  gcs_bucket: string;      // GCS bucket name
  gcs_prefix: string;      // Path prefix in GCS
  dataset_name: string;    // Dataset name in Neo4j
}
```

**Output:**
```typescript
{
  type: 'text';
  text: JSON.stringify({
    status: 'success';
    message: 'Graph extraction completed';
    data: {
      entities_count: number;
      relationships_count: number;
      tables_processed: number;
      artifacts: {
        graph_json: string;      // Path to JSON export
        visualization: string;   // Path to PNG
      };
    };
    dataset: string;
  });
}
```

### Tool: query_graph

Execute Cypher queries against the knowledge graph.

**Input:**
```typescript
{
  cypher_query: string;   // Cypher query
  dataset_name: string;   // Dataset to query
}
```

**Output:**
```typescript
{
  type: 'text';
  text: JSON.stringify({
    status: 'success';
    message: 'Query executed';
    data: any[];      // Query results
    query: string;
  });
}
```

### Tool: visualize_graph

Generate network visualization as PNG.

**Input:**
```typescript
{
  dataset_name: string;      // Dataset to visualize
  output_path?: string;      // Optional output file path
}
```

**Output:**
```typescript
{
  type: 'text';
  text: JSON.stringify({
    status: 'success';
    message: 'Graph visualization created';
    data: any;
    output_path: string;      // Path to generated PNG
    dataset: string;
  });
}
```

### Tool: summarize_graph

Generate summary of most connected entities.

**Input:**
```typescript
{
  dataset_name: string;    // Dataset to summarize
  max_nodes?: number;      // Top N entities (default: 10)
}
```

**Output:**
```typescript
{
  type: 'text';
  text: JSON.stringify({
    status: 'success';
    message: 'Dataset summary generated';
    data: Array<{
      entity: string;
      connections: number;
      types: string[];
    }>;
    dataset: string;
  });
}
```

### Tool: list_datasets

List all available datasets in the knowledge graph.

**Input:**
```typescript
{}  // No parameters
```

**Output:**
```typescript
{
  type: 'text';
  text: JSON.stringify({
    status: 'success';
    message: 'Datasets listed';
    data: string[];    // Dataset names
  });
}
```

### Tool: demo_pipeline

Run complete extraction pipeline.

**Input:**
```typescript
{
  dataset_name?: string;   // Optional dataset name (default: "demo")
}
```

**Output:**
```typescript
{
  type: 'text';
  text: JSON.stringify({
    status: 'success';
    message: 'Demo pipeline completed';
    data: {
      entities: number;
      relationships: number;
      visualization: string;
    };
    dataset: string;
  });
}
```

## Advanced Usage

### Cypher Query Examples

```cypher
# Find entities by type
MATCH (n:Person) RETURN n.name LIMIT 10

# Find relationships between specific entities
MATCH (a)-[r]-(b) WHERE a.name = 'Entity1' RETURN r, b

# Aggregate statistics
MATCH (n) RETURN labels(n)[0] as type, count(n) as count

# Shortest path between entities
MATCH p = shortestPath((a {name: 'A'})-[*]-(b {name: 'B'})) RETURN p

# Find communities (heavily connected subgraphs)
MATCH (n)-[r]-(m) RETURN n, r, m LIMIT 50
```

### Progress Streaming

The Python bridge automatically parses progress indicators from CLI output:

- Format: `[50/150]` or `[33%]`
- Progress events are emitted via stderr
- Available in tool handlers via `onProgress` callback

## Development

### Setup

```bash
git clone https://github.com/your-org/opengraph-ai.git
cd opengraph-ai/mcp-server
npm install
npm run build
```

### Scripts

```bash
npm run dev           # Start with tsx (development)
npm run build         # Build TypeScript
npm start             # Run compiled server
npm test              # Run tests
npm run lint          # Check TypeScript
npm run prepublishOnly  # Pre-publication checks
```

### Project Structure

```
mcp-server/
├── src/
│   ├── tools.ts              # Tool definitions
│   ├── tool-handlers.ts      # Tool implementation
│   └── python-bridge.ts      # Python CLI bridge
├── tests/
│   └── tools.test.ts         # Unit tests
├── dist/                     # Compiled JavaScript
├── index.ts                  # Server entrypoint
├── package.json
├── tsconfig.json
└── README.md
```

## Architecture

### Communication Flow

```
Claude / Cursor
     ↓
MCP Protocol (stdin/stdout)
     ↓
MCP Server (Node.js)
     ↓
Python Bridge
     ↓
CLI Commands
     ↓
Python Engine (extractors, graph builder, connectors)
     ↓
External Services (OpenAI API, Neo4j, GCS)
```

### Key Components

- **MCP Server**: Manages protocol communication and tool dispatch
- **Tool Handlers**: Request validation and processing
- **Python Bridge**: Spawns Python CLI processes with stdio communication
- **CLI**: Typer-based commands for extraction, querying, visualization
- **Engine**: Core extraction, graph building, Neo4j connectivity

## Troubleshooting

### Connection Issues

```
Error: Failed to connect to MCP server
→ Check Node.js is installed: node --version
→ Verify npm packages: npm list @modelcontextprotocol/sdk
→ Check stdio transport: npm run build
```

### Python CLI Errors

```
Error: Python command failed
→ Verify PYTHON_EXECUTABLE environment variable
→ Check CLI help: python -m cli --help
→ Test extraction: python -m cli extract --text "test"
```

### Neo4j Connection

```
Error: Failed to connect to Neo4j
→ Verify NEO4J_URI is correct
→ Check credentials: neo4j user password
→ Test connection with Neo4j Browser
```

### GCS Access

```
Error: GCS bucket not accessible
→ Check GOOGLE_APPLICATION_CREDENTIALS
→ Verify bucket exists: gsutil ls gs://bucket-name
→ Check service account permissions
```

## Performance

- **Text Extraction**: ~100-500ms per 1KB chunk
- **Graph Query**: <100ms for typical queries
- **Visualization**: 1-5s depending on graph size
- **Full Pipeline**: 10-30s for typical CSV datasets

## Limitations

- Text extraction limited to 10K characters per chunk
- Cypher queries limited to 10s execution time
- Visualization limited to 1000 nodes
- GCS objects limited to 5GB
- Neo4j queries return max 10,000 results

## Contributing

Contributions welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Submit a pull request

## License

MIT - See LICENSE file for details

## Support

- **Documentation**: [README](./README.md)
- **Issues**: [GitHub Issues](https://github.com/your-org/opengraph-ai/issues)
- **Discussions**: [GitHub Discussions](https://github.com/your-org/opengraph-ai/discussions)

## Related Projects

- [Model Context Protocol](https://modelcontextprotocol.io/)
- [OpenGraph AI Engine](../README.md)
- [Claude Desktop](https://claude.ai/)
- [Cursor](https://www.cursor.com/)

## Changelog

### 0.1.0 (2024-05)
- Initial MCP server implementation
- 7 core tools for extraction, querying, visualization
- Python bridge for CLI integration
- Test suite and documentation
