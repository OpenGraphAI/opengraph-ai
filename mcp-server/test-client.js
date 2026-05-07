import { spawn } from "child_process";

async function testMCP() {
  console.log("Starting MCP server test...\n");

  const server = spawn("npm", ["run", "dev"], {
    cwd: "/Users/d/Documents/GitHub/opengraph-ai/mcp-server",
  });

  let isConnected = false;

  server.stderr.on("data", (data) => {
    const msg = data.toString();
    console.log("[SERVER]", msg.trim());
    if (msg.includes("listening")) {
      isConnected = true;
      setTimeout(sendTests, 1000);
    }
  });

  server.stdout.on("data", (data) => {
    console.log("[STDOUT]", data.toString().trim());
  });

  function sendTests() {
    if (!isConnected) return;

    // Test 1: List tools
    console.log("\n--- Test 1: List Tools ---");
    const listRequest = {
      jsonrpc: "2.0",
      id: 1,
      method: "tools/list",
    };
    server.stdin.write(JSON.stringify(listRequest) + "\n");

    // Test 2: Call extract_text tool
    setTimeout(() => {
      console.log("\n--- Test 2: Extract Text (Offline) ---");
      const extractRequest = {
        jsonrpc: "2.0",
        id: 2,
        method: "tools/call",
        params: {
          name: "extract_text",
          arguments: {
            text: "Alice founded Acme Corporation in London.",
            use_llm: false,
          },
        },
      };
      server.stdin.write(JSON.stringify(extractRequest) + "\n");
    }, 2000);

    // Test 3: Call query_graph tool
    setTimeout(() => {
      console.log("\n--- Test 3: Query Graph ---");
      const queryRequest = {
        jsonrpc: "2.0",
        id: 3,
        method: "tools/call",
        params: {
          name: "query_graph",
          arguments: {
            dataset: "text_example",
            query: "alice",
          },
        },
      };
      server.stdin.write(JSON.stringify(queryRequest) + "\n");
    }, 5000);

    // Cleanup
    setTimeout(() => {
      console.log("\n--- Tests Complete ---\n");
      server.kill();
      process.exit(0);
    }, 8000);
  }

  server.on("error", (err) => {
    console.error("Server error:", err);
    process.exit(1);
  });

  server.on("close", (code) => {
    console.log(`\nServer exited with code ${code}`);
    if (code !== 0) process.exit(code);
  });

  setTimeout(() => {
    console.error("Test timeout!");
    server.kill();
    process.exit(1);
  }, 12000);
}

testMCP().catch(console.error);
