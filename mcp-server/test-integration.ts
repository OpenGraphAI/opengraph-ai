#!/usr/bin/env node

/**
 * MCP Server Test Client
 * Tests the OpenGraph AI MCP server with various tool calls
 */

import { spawn } from 'child_process';
import { Client } from '@modelcontextprotocol/sdk/client/index.js';
import { StdioClientTransport } from '@modelcontextprotocol/sdk/client/stdio.js';
import process from 'process';

async function runTests() {
  console.log('Starting OpenGraph AI MCP Server tests...\n');

  // Spawn the MCP server
  const serverProcess = spawn('npm', ['run', 'start'], {
    cwd: process.cwd(),
    stdio: ['pipe', 'pipe', 'pipe'],
  });

  // Create transport and client
  const transport = new StdioClientTransport({
    command: 'npm',
    args: ['run', 'start'],
    cwd: process.cwd(),
  });

  const client = new Client(
    {
      name: 'test-client',
      version: '0.1.0',
    },
    {
      capabilities: {},
    }
  );

  try {
    // Connect client
    await client.connect(transport);
    console.log('✓ Connected to MCP server\n');

    // Test 1: List tools
    console.log('Test 1: Listing available tools...');
    const toolsList = await client.listTools();
    console.log(`✓ Found ${toolsList.tools.length} tools:`);
    toolsList.tools.forEach((tool) => {
      console.log(`  - ${tool.name}: ${tool.description}`);
    });
    console.log();

    // Test 2: Extract text
    console.log('Test 2: Extracting text...');
    try {
      const textResult = await client.callTool(
        {
          name: 'extract_text',
          arguments: {
            text: 'Apple was founded by Steve Jobs in 1976 in California.',
          },
        },
        undefined
      );
      console.log('✓ Text extraction result:');
      console.log(JSON.stringify(textResult, null, 2));
    } catch (error) {
      console.log(`⚠ Text extraction failed (expected if Python CLI not in path)`);
      console.log(`  Error: ${error instanceof Error ? error.message : String(error)}`);
    }
    console.log();

    // Test 3: List datasets
    console.log('Test 3: Listing datasets...');
    try {
      const datasetResult = await client.callTool(
        {
          name: 'list_datasets',
          arguments: {},
        },
        undefined
      );
      console.log('✓ Datasets:', JSON.stringify(datasetResult, null, 2));
    } catch (error) {
      console.log(`⚠ List datasets failed (expected if Neo4j not accessible)`);
      console.log(`  Error: ${error instanceof Error ? error.message : String(error)}`);
    }
    console.log();

    console.log('✓ All tests completed');
  } catch (error) {
    console.error('✗ Test failed:', error);
    process.exit(1);
  } finally {
    // Cleanup
    await client.close();
    serverProcess.kill();
  }
}

// Run tests
runTests().catch((error) => {
  console.error('Fatal error:', error);
  process.exit(1);
});
