/**
 * MCP tool registry and schemas for OpenGraph AI.
 */

import { Tool } from "@modelcontextprotocol/sdk/types.js";

export const TOOLS: Tool[] = [
  {
    name: "extract_text",
    description:
      "Extract entities and relationships from free-form text using LLM-backed extraction",
    inputSchema: {
      type: "object",
      properties: {
        text: {
          type: "string",
          description: "The text content to extract entities and relationships from",
        },
        use_llm: {
          type: "boolean",
          description:
            "Use OpenAI LLM for extraction (true) or regex heuristics (false). Requires OPENAI_API_KEY if true.",
          default: false,
        },
      },
      required: ["text"],
    },
  },
  {
    name: "query_graph",
    description:
      "Search a previously extracted and saved graph JSON for entities by name or type",
    inputSchema: {
      type: "object",
      properties: {
        dataset: {
          type: "string",
          description: "Dataset name (e.g., 'text_example', 'table_example')",
        },
        query: {
          type: "string",
          description: "Search term for entities (fuzzy match)",
        },
      },
      required: ["dataset", "query"],
    },
  },
  {
    name: "visualize_graph",
    description:
      "Render a saved graph JSON as a PNG image showing entities and relationships",
    inputSchema: {
      type: "object",
      properties: {
        dataset: {
          type: "string",
          description: "Dataset name (e.g., 'text_example')",
        },
        output_path: {
          type: "string",
          description: "Local file path where PNG should be saved",
        },
      },
      required: ["dataset", "output_path"],
    },
  },
  {
    name: "demo_pipeline",
    description:
      "Run the full extraction pipeline (read, extract, build, visualize) on a text file or table folder",
    inputSchema: {
      type: "object",
      properties: {
        source_path: {
          type: "string",
          description: "Path to a .txt file or folder containing CSV tables",
        },
        use_llm: {
          type: "boolean",
          description:
            "Use LLM extraction for tables (true) or offline mode (false). Text files always use heuristics.",
          default: false,
        },
      },
      required: ["source_path"],
    },
  },
];

export function listTools(): Tool[] {
  return TOOLS;
}
