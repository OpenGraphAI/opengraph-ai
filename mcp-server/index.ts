#!/usr/bin/env node

import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import {
  CallToolRequestSchema,
  ErrorCode,
  ListToolsRequestSchema,
  McpError,
} from "@modelcontextprotocol/sdk/types.js";
import { TOOLS } from "./src/tools.js";
import {
  handleExtractTextTool,
  handleExtractGraphTool,
  handleQueryGraphTool,
  handleVisualizeGraphTool,
  handleListDatasetsTool,
  handleSummarizeTool,
  handleDemoPipelineTool,
} from "./src/tool-handlers.js";

const server = new Server(
  {
    name: "opengraph-ai",
    version: "0.1.0",
  },
  {
    capabilities: {
      tools: {},
    },
  }
);

// Handle list tools request
server.setRequestHandler(ListToolsRequestSchema, async () => {
  return {
    tools: TOOLS,
  };
});

// Handle tool call requests
server.setRequestHandler(CallToolRequestSchema, async (request) => {
  const toolName = request.params.name;

  try {
    let result;

    switch (toolName) {
      case "extract_text":
        result = await handleExtractTextTool(request);
        break;

      case "extract_graph":
        result = await handleExtractGraphTool(request);
        break;

      case "query_graph":
        result = await handleQueryGraphTool(request);
        break;

      case "visualize_graph":
        result = await handleVisualizeGraphTool(request);
        break;

      case "summarize_graph":
        result = await handleSummarizeTool(request);
        break;

      case "list_datasets":
        result = await handleListDatasetsTool();
        break;

      case "demo_pipeline":
        result = await handleDemoPipelineTool(request);
        break;

      default:
        throw new McpError(ErrorCode.MethodNotFound, `Unknown tool: ${toolName}`);
    }

    return result;
  } catch (error) {
    const errorMessage = error instanceof Error ? error.message : String(error);
    throw new McpError(ErrorCode.InternalError, errorMessage);
  }
});

async function main() {
  const transport = new StdioServerTransport();
  await server.connect(transport);
  console.error("OpenGraph AI MCP server online");
}

main().catch((error) => {
  console.error("Fatal error:", error);
  process.exit(1);
});
