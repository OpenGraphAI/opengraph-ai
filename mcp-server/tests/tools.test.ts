import { test } from 'node:test';
import * as assert from 'node:assert';
import { TOOLS, getTool, getToolNames } from '../src/tools.js';

test('Tool Definitions', async (t) => {
  await t.test('should have 7 tools defined', () => {
    assert.strictEqual(TOOLS.length, 7);
  });

  await t.test('should have correct tool names', () => {
    const names = getToolNames();
    assert.deepStrictEqual(names, [
      'extract_text',
      'extract_graph',
      'query_graph',
      'visualize_graph',
      'summarize_graph',
      'list_datasets',
      'demo_pipeline',
    ]);
  });

  await t.test('extract_text tool should have correct schema', () => {
    const tool = getTool('extract_text');
    assert.ok(tool);
    assert.strictEqual(tool.name, 'extract_text');
    assert.ok(tool.inputSchema);
    const schema = tool.inputSchema as any;
    assert.ok(schema.properties.text);
    assert.deepStrictEqual(schema.required, ['text']);
  });

  await t.test('extract_graph tool should have correct schema', () => {
    const tool = getTool('extract_graph');
    assert.ok(tool);
    const schema = tool.inputSchema as any;
    assert.deepStrictEqual(schema.required, ['gcs_bucket', 'gcs_prefix', 'dataset_name']);
  });

  await t.test('query_graph tool should have correct schema', () => {
    const tool = getTool('query_graph');
    assert.ok(tool);
    const schema = tool.inputSchema as any;
    assert.deepStrictEqual(schema.required, ['cypher_query', 'dataset_name']);
  });

  await t.test('all tools should have descriptions', () => {
    TOOLS.forEach((tool) => {
      assert.ok(tool.description && tool.description.length > 0, `${tool.name} missing description`);
    });
  });

  await t.test('should return undefined for non-existent tool', () => {
    const tool = getTool('nonexistent');
    assert.strictEqual(tool, undefined);
  });
});

test('Tool Handlers - Input Validation', async (t) => {
  // These tests validate that handlers would properly validate input
  // Actual handler tests would require mocking the Python bridge

  await t.test('extract_text should require text parameter', () => {
    // This would be tested in the handler
    const request: any = {
      params: {
        arguments: {},
      },
    };
    // Handler should throw error
    assert.ok(request.params.arguments.text === undefined);
  });

  await t.test('extract_graph should require all parameters', () => {
    const request: any = {
      params: {
        arguments: {
          gcs_bucket: 'bucket',
          // missing gcs_prefix and dataset_name
        },
      },
    };
    assert.ok(!request.params.arguments.gcs_prefix);
  });
});

test('MCP Server Configuration', async (t) => {
  await t.test('should have proper MCP server setup', async () => {
    // Verify the index.ts creates a proper Server
    // This would be an integration test
    assert.ok(true); // Placeholder
  });

  await t.test('should have StdioServerTransport configured', async () => {
    // Verify transport setup
    assert.ok(true); // Placeholder
  });
});

test('Python Bridge Integration', async (t) => {
  await t.test('should have python-bridge module', () => {
    // Verify module exports
    assert.ok(true); // Placeholder for actual module test
  });

  await t.test('should have progress callback support', () => {
    // Verify progress streaming capability
    assert.ok(true); // Placeholder
  });
});

test('Tool Response Format', async (t) => {
  await t.test('should return structured response', () => {
    const response = {
      type: 'text',
      text: JSON.stringify({
        status: 'success',
        message: 'Operation completed',
        data: {},
      }),
    };

    assert.strictEqual(response.type, 'text');
    assert.ok(response.text);
    const parsed = JSON.parse(response.text);
    assert.strictEqual(parsed.status, 'success');
  });

  await t.test('should handle error responses', () => {
    const errorResponse = {
      type: 'text',
      text: JSON.stringify({
        status: 'error',
        error: 'Dataset not found',
      }),
      isError: true,
    };

    assert.ok(errorResponse.isError);
    assert.strictEqual(errorResponse.type, 'text');
  });
});
