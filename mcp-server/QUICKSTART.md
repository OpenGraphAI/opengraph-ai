# OpenGraph AI MCP Server - Quick Start Guide

Get started with the OpenGraph AI Model Context Protocol (MCP) server in 5 minutes.

## What is This?

The OpenGraph AI MCP server lets Claude, Cursor, and other AI agents:
- Extract entities and relationships from text
- Extract structured data from CSV files in Google Cloud Storage
- Query knowledge graphs stored in Neo4j
- Visualize knowledge graphs as network diagrams

## Prerequisites

- **Node.js** 20+ ([Install](https://nodejs.org/))
- **Python** 3.11+ ([Install](https://www.python.org/))
- **Google Cloud** account with credentials
- **Neo4j AuraDB** instance (free tier available)

## Installation (5 minutes)

### Option 1: From NPM (Recommended)

```bash
# Install globally
npm install -g opengraph-mcp

# Start the server
opengraph-mcp
```

### Option 2: From Source

```bash
# Clone repository
git clone https://github.com/your-org/opengraph-ai.git
cd opengraph-ai/mcp-server

# Install dependencies
npm install

# Build TypeScript
npm run build

# Start the server
npm run start
```

## Configuration (2 minutes)

Set these environment variables:

```bash
# OpenAI API
export OPENAI_API_KEY=sk-...

# Neo4j AuraDB connection
export NEO4J_URI=neo4j+s://...
export NEO4J_USERNAME=neo4j
export NEO4J_PASSWORD=...

# Google Cloud
export GCP_PROJECT_ID=your-project-id
export GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json
export GCS_BUCKET=your-gcs-bucket

# Optional: Python location
export PYTHON_EXECUTABLE=/path/to/python3
```

### Get Credentials

**OpenAI API Key:**
1. Go to [platform.openai.com/api-keys](https://platform.openai.com/api-keys)
2. Create a new API key
3. Copy and set as `OPENAI_API_KEY`

**Neo4j AuraDB:**
1. Sign up at [neo4j.com/cloud/aura](https://neo4j.com/cloud/aura)
2. Create a free instance
3. Copy connection string and credentials

**Google Cloud:**
1. Create service account: `gcloud iam service-accounts create mcp-server`
2. Create and download key: `gcloud iam service-accounts keys create key.json --iam-account=...`
3. Set `GOOGLE_APPLICATION_CREDENTIALS=/path/to/key.json`

## Integration with Claude/Cursor (3 minutes)

### For Claude Desktop

Edit `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "opengraph": {
      "command": "npm",
      "args": ["run", "start"],
      "cwd": "/path/to/opengraph-ai/mcp-server",
      "env": {
        "OPENAI_API_KEY": "sk-...",
        "NEO4J_URI": "neo4j+s://...",
        "NEO4J_USERNAME": "neo4j",
        "NEO4J_PASSWORD": "..."
      }
    }
  }
}
```

Then restart Claude Desktop.

### For Cursor

Edit `.cursor/settings.json`:

```json
{
  "tools": [
    {
      "name": "opengraph-ai",
      "command": "npm",
      "args": ["run", "start"],
      "cwd": "/path/to/opengraph-ai/mcp-server"
    }
  ]
}
```

Restart Cursor and the tools will be available.

## Usage Examples

### Example 1: Extract from Text

**You:** "Extract entities and relationships from this text: 'Apple was founded by Steve Jobs in 1976 in California.'"

**Claude will use the extract_text tool to:**
- Identify entities: Apple (Organization), Steve Jobs (Person), 1976 (Date), California (Location)
- Find relationships: Steve Jobs founded Apple, Apple is located in California
- Return structured JSON

### Example 2: Extract from CSV

**You:** "Extract the knowledge graph from the CSV files in gs://my-bucket/data/orders and call it 'ecommerce'"

**Claude will:**
- Read CSV files from GCS
- Extract entities and relationships using LLM
- Store in Neo4j under 'ecommerce' dataset
- Return statistics (50 entities, 200 relationships)

### Example 3: Query Graph

**You:** "Find the top 10 customers by order count in the ecommerce dataset"

**Claude will execute:**
```cypher
MATCH (c:Customer)-[r:PLACED_ORDER]-(o:Order)
RETURN c.name, count(o) as orders
ORDER BY orders DESC
LIMIT 10
```

### Example 4: Visualize

**You:** "Visualize the ecommerce dataset"

**Claude will:**
- Query all entities and relationships
- Generate network visualization
- Show graph with nodes as entities, edges as relationships

### Example 5: Summarize

**You:** "Give me a summary of the ecommerce dataset"

**Claude will:**
- Find most connected entities
- Return top 10 entities with connection counts
- Provide dataset statistics

## Available Tools

| Tool | Purpose | Use Case |
|------|---------|----------|
| **extract_text** | Extract from unstructured text | Email, documents, feedback |
| **extract_graph** | Extract from CSV files in GCS | Structured data, tables |
| **query_graph** | Run Cypher queries | Analysis, insights |
| **visualize_graph** | Generate network diagram | Understanding relationships |
| **summarize_graph** | Get overview of dataset | Key entities, connections |
| **list_datasets** | See all datasets | Data inventory |
| **demo_pipeline** | Run full extraction pipeline | Testing, demos |

## Quick Test

Verify everything is working:

```bash
# Check Node.js
node --version  # Should be 20+

# Check Python CLI
python3 -m cli --help

# Check MCP server starts
cd mcp-server
npm run build
npm run start
# Should print: "OpenGraph AI MCP server online"
```

## Common Issues

### "Python module not found"

```bash
# Install Python packages
pip install -r ../requirements.txt
```

### "Neo4j connection failed"

```bash
# Test Neo4j connection
python3 -c "from neo4j import GraphDatabase; print('OK')"

# Verify credentials
echo $NEO4J_URI
echo $NEO4J_USERNAME
```

### "GCS bucket not accessible"

```bash
# Test GCS access
gcloud auth list
gsutil ls gs://your-bucket

# Set credentials
gcloud auth activate-service-account --key-file=/path/to/key.json
```

### "MCP server won't connect"

```bash
# Check if running
ps aux | grep "npm run"

# Check logs
cd mcp-server && npm run dev
```

## Next Steps

1. **Try extraction**: Use `extract_text` tool with sample text
2. **Load your data**: Use `extract_graph` with your CSV files
3. **Explore queries**: Use `query_graph` with Cypher queries
4. **Visualize**: Generate network diagrams with `visualize_graph`
5. **Deploy**: Publish to npm or deploy to server

## Advanced Usage

### Custom Cypher Queries

```cypher
# Find relationship patterns
MATCH (a)-[r1]-(b)-[r2]-(c)
WHERE type(r1) = 'CONNECTS_TO'
RETURN a, r1, b, r2, c

# Aggregations
MATCH (n) RETURN labels(n)[0] as type, count(*) as count

# Shortest paths
MATCH p = shortestPath((a {id: '123'})-[*]-(b {id: '456'}))
RETURN p
```

### Batch Processing

```
1. Use list_datasets to see existing datasets
2. Create multiple datasets for different sources
3. Query across datasets with proper filtering
4. Combine visualizations
```

### Performance Tips

- Use `LIMIT` in queries to prevent large result sets
- Extract to separate datasets by source
- Use `summarize_graph` before full visualization
- Cache frequently used queries

## Documentation

- [Full API Reference](./PACKAGE.md)
- [Claude Code Rules](../.claude/rules.md)
- [Architecture Guide](./README.md)
- [GitHub Repository](https://github.com/your-org/opengraph-ai)

## Support

- **Issues**: Report bugs on [GitHub](https://github.com/your-org/opengraph-ai/issues)
- **Discussions**: Ask questions on [GitHub Discussions](https://github.com/your-org/opengraph-ai/discussions)
- **Documentation**: See [README.md](./README.md)

## Next: Publish to NPM

Ready to share with others?

```bash
# Update version in package.json
npm version patch

# Test everything
npm run build
npm run test

# Publish
npm publish

# Tag release
git tag v0.1.0
git push --tags
```

## License

MIT - See LICENSE for details
