# OpenGraph AI - Claude Code Rules

## Purpose
This file provides configuration and guidelines for Claude Code (Cursor) integration with the OpenGraph AI MCP server.

## Environment Setup

### Required Environment Variables
```bash
export OPENAI_API_KEY=sk-...
export GCP_PROJECT_ID=user-account-493600
export NEO4J_URI=neo4j+s://...
export NEO4J_USERNAME=neo4j
export NEO4J_PASSWORD=...
export GCS_BUCKET=davidluobucket
export PYTHON_EXECUTABLE=/path/to/venv/bin/python3
```

### MCP Server Configuration

Add to `cursor_server_configs` in `.cursor/settings.json`:

```json
{
  "tools": [
    {
      "name": "opengraph-ai-mcp",
      "command": "/Users/d/Documents/GitHub/opengraph-ai/mcp-server",
      "executable": "npm",
      "args": ["run", "start"]
    }
  ]
}
```

Or use stdin launch:
```json
{
  "stdio": {
    "command": "npm",
    "args": ["run", "start"],
    "cwd": "/Users/d/Documents/GitHub/opengraph-ai/mcp-server"
  }
}
```

## Available Tools

### 1. Extract Text
Extract entities and relationships from unstructured text.

**Parameters:**
- `text` (required): Text content to extract from
- `dataset_name` (optional): Name for organizing extractions

**Example:**
```
Extract entities and relationships from this text:
"Apple Inc. was founded by Steve Jobs in 1976 in Los Altos, California."
```

**Response:** JSON with entities (Person, Organization, Date) and relationships (founded, located_in)

### 2. Extract Graph
Extract structured data from CSV files in Google Cloud Storage.

**Parameters:**
- `gcs_bucket` (required): e.g., "davidluobucket"
- `gcs_prefix` (required): e.g., "User-DL/Airline+Loyalty+Program"
- `dataset_name` (required): e.g., "airline_loyalty_analysis"

**Example:**
```
Extract graph from the Airline Loyalty dataset in GCS bucket davidluobucket
```

### 3. Query Graph
Execute Cypher queries against the Neo4j knowledge graph.

**Parameters:**
- `cypher_query` (required): Cypher query string
- `dataset_name` (required): Dataset to query

**Example Queries:**
```cypher
# Find top customers by loyalty points
MATCH (c:Customer)-[r:HAS_ACCOUNT]->(p:Program)
RETURN c.name, SUM(p.points) as total_points
ORDER BY total_points DESC
LIMIT 10

# Find related entities
MATCH (n)-[r]-(m) WHERE n.name = "specific_entity"
RETURN n, r, m LIMIT 5
```

### 4. Visualize Graph
Generate network visualization as PNG.

**Parameters:**
- `dataset_name` (required): Dataset to visualize
- `output_path` (optional): Output file path

**Example:**
```
Visualize the knowledge graph for the airline_loyalty dataset
```

### 5. Summarize Graph
Generate summary of most connected entities.

**Parameters:**
- `dataset_name` (required): Dataset to summarize
- `max_nodes` (optional): Number of top entities (default: 10)

**Example:**
```
Summarize the main entities in the airline_loyalty dataset, showing top 15
```

### 6. List Datasets
List all available datasets in the knowledge graph.

**Example:**
```
Show all available datasets
```

### 7. Demo Pipeline
Run complete extraction pipeline: text→graph→Neo4j→visualization

**Parameters:**
- `dataset_name` (optional): Name for the demo dataset (default: "demo")

## Best Practices

### 1. Data Extraction Workflow
```
1. Start with extract_text or extract_graph
2. Use query_graph to explore structure
3. Use summarize_graph for overview
4. Use visualize_graph to understand relationships
```

### 2. Cypher Query Tips
- Use `LIMIT` to prevent huge result sets
- Use `COUNT()` to get statistics
- Use `COLLECT()` to aggregate related items
- Filter with `WHERE` clauses for specific datasets

### 3. Large Dataset Handling
- Extract from GCS for structured data (tables)
- Use dataset_name for isolation
- Query in sections with LIMIT
- Export visualizations for sharing

## API Endpoints

### FastAPI Server (Alternative to MCP)
Base URL: `https://opengraph-ai-451791921471.us-central1.run.app`

**Health Check:**
```
GET /health
```

**Graph from GCS:**
```
POST /graph/from-gcs
{
  "dataset_name": "my_dataset",
  "gcs_input_uri": "gs://bucket/prefix",
  "use_llm": true
}
```

## Development

### Running MCP Server Locally
```bash
cd /Users/d/Documents/GitHub/opengraph-ai/mcp-server
npm install
npm run build
npm run dev
```

### Testing Tools
```bash
# List available tools
npm test

# Run specific tool
node test-client.js extract_text "Some sample text"
```

### Building for Production
```bash
npm run build
npm run lint
npm test
npm publish
```

## Troubleshooting

### MCP Server Not Connecting
1. Check if Node.js is installed: `node --version`
2. Check if packages are installed: `ls node_modules/@modelcontextprotocol`
3. Verify environment variables are set
4. Check Python venv is activated

### Python CLI Errors
1. Verify PYTHON_EXECUTABLE environment variable
2. Check GCP credentials: `gcloud auth list`
3. Verify Neo4j connection: `gcloud sql connect neo4j`
4. Check GCS bucket access: `gsutil ls gs://davidluobucket`

### Query Results Empty
1. Verify dataset exists: Use `list_datasets` tool
2. Check dataset namespace: Queries are namespaced by dataset name
3. Verify Cypher syntax with Neo4j Browser
4. Check data was extracted: Use `query_graph` with MATCH (n) RETURN count(n)

## Examples

### Complete Analysis Workflow
```
1. "Extract from the CSV files in gs://davidluobucket/User-DL/Airline+Loyalty+Program"
   → Creates dataset with entities and relationships

2. "Show me all customers in the airline_loyalty dataset"
   → Runs: MATCH (c:Customer) RETURN c

3. "What are the top 5 most active customers?"
   → Runs: MATCH (c:Customer)-[r:HAS_ACTIVITY]-(a:Activity) 
           RETURN c.name, count(a) as activities 
           ORDER BY activities DESC LIMIT 5

4. "Visualize the airline_loyalty dataset"
   → Creates PNG showing all entities and relationships

5. "Summarize the key entities"
   → Returns top 10 most connected entities
```

### Text Extraction Example
```
"Extract entities and relationships from this customer service feedback:
'Customer John Smith called about his United Airlines loyalty account on 2024-05-15.
He had issues with points redemption. The issue was resolved by agent Jane Doe.'"

Result:
{
  "entities": [
    {"name": "John Smith", "type": "Person"},
    {"name": "United Airlines", "type": "Organization"},
    {"name": "Jane Doe", "type": "Person"},
    {"name": "2024-05-15", "type": "Date"}
  ],
  "relationships": [
    {"source": "John Smith", "target": "United Airlines", "type": "loyalty_member"},
    {"source": "Jane Doe", "target": "John Smith", "type": "resolved_issue"}
  ]
}
```

## API Reference

### Python CLI Commands
```bash
# Extract from text
python -m cli extract --text "some text" --format json

# Extract from GCS
python -m cli extract --gcs-bucket bucket --gcs-prefix path --dataset-name name

# Query graph
python -m cli query --dataset dataset_name --cypher "MATCH (n) RETURN n"

# Visualize
python -m cli visualize --dataset dataset_name --output path

# List datasets
python -m cli graphdb list --format json

# Demo pipeline
python -m cli demo --dataset demo_name
```

## Support

For issues or questions:
1. Check troubleshooting section above
2. Review test outputs: `npm test`
3. Check logs in `/tmp/opengraph-ai.log`
4. Review Python CLI help: `python -m cli --help`
