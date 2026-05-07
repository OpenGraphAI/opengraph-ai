import { Tool } from '@modelcontextprotocol/sdk/types.js';

export const TOOLS: Tool[] = [
  {
    name: 'extract_text',
    description:
      'Extract entities and relationships from unstructured text using LLM. Supports chunking for long text.',
    inputSchema: {
      type: 'object',
      properties: {
        text: {
          type: 'string',
          description: 'The text content to extract entities and relationships from',
        },
        dataset_name: {
          type: 'string',
          description: 'Optional dataset name for organizing extractions',
        },
      },
      required: ['text'],
    },
  },

  {
    name: 'extract_graph',
    description:
      'Extract entities and relationships from CSV files in Google Cloud Storage and build a knowledge graph. Returns entities and relationships stored in Neo4j.',
    inputSchema: {
      type: 'object',
      properties: {
        gcs_bucket: {
          type: 'string',
          description: 'Google Cloud Storage bucket name (e.g., "davidluobucket")',
        },
        gcs_prefix: {
          type: 'string',
          description: 'Path prefix in GCS (e.g., "User-DL/Airline+Loyalty+Program")',
        },
        dataset_name: {
          type: 'string',
          description:
            'Name for the dataset in Neo4j (used for namespacing entities/relationships)',
        },
      },
      required: ['gcs_bucket', 'gcs_prefix', 'dataset_name'],
    },
  },

  {
    name: 'query_graph',
    description:
      'Execute a Cypher query against the knowledge graph stored in Neo4j. Returns raw query results.',
    inputSchema: {
      type: 'object',
      properties: {
        cypher_query: {
          type: 'string',
          description:
            'Cypher query string (e.g., "MATCH (n:Entity) RETURN n.name LIMIT 10")',
        },
        dataset_name: {
          type: 'string',
          description: 'Dataset name to query from',
        },
      },
      required: ['cypher_query', 'dataset_name'],
    },
  },

  {
    name: 'visualize_graph',
    description:
      'Generate a network graph visualization as PNG. Shows entities as nodes and relationships as edges.',
    inputSchema: {
      type: 'object',
      properties: {
        dataset_name: {
          type: 'string',
          description: 'Dataset name to visualize',
        },
        output_path: {
          type: 'string',
          description: 'Optional output path for the PNG file (default: /tmp/{dataset}-graph.png)',
        },
      },
      required: ['dataset_name'],
    },
  },

  {
    name: 'summarize_graph',
    description:
      'Generate a summary of the knowledge graph, showing most connected entities and relationships.',
    inputSchema: {
      type: 'object',
      properties: {
        dataset_name: {
          type: 'string',
          description: 'Dataset name to summarize',
        },
        max_nodes: {
          type: 'number',
          description: 'Maximum number of top entities to include in summary (default: 10)',
        },
      },
      required: ['dataset_name'],
    },
  },

  {
    name: 'list_datasets',
    description: 'List all available datasets in the knowledge graph database.',
    inputSchema: {
      type: 'object',
      properties: {},
      required: [],
    },
  },

  {
    name: 'demo_pipeline',
    description:
      'Run the complete demo pipeline: extract from text, build graph, store in Neo4j, and visualize.',
    inputSchema: {
      type: 'object',
      properties: {
        dataset_name: {
          type: 'string',
          description: 'Optional dataset name (default: "demo")',
        },
      },
      required: [],
    },
  },
];

/**
 * Get tool by name
 */
export function getTool(name: string): Tool | undefined {
  return TOOLS.find((t) => t.name === name);
}

/**
 * Get all tool names
 */
export function getToolNames(): string[] {
  return TOOLS.map((t) => t.name);
}
