/**
 * MCP server entrypoint.
 *
 * TODO: Initialize MCP transport and tool bindings.
 */

import { listTools } from "./tools/index.js";

export function startServer(): void {
  // TODO: Replace logging with MCP server bootstrap logic.
  console.log("OpenGraph MCP server scaffold starting...");
  console.log("Tools:", listTools());
}

if (import.meta.url === `file://${process.argv[1]}`) {
  startServer();
}
