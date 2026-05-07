import { CallToolRequest } from '@modelcontextprotocol/sdk/types.js';
import {
  extractFromText,
  extractFromGCS,
  queryGraph,
  visualizeGraph,
  listDatasets,
  runDemoPipeline,
} from './python-bridge.js';

function toToolResult(payload: unknown, isError = false): { content: Array<{ type: 'text'; text: string }>; isError?: boolean } {
  return {
    content: [
      {
        type: 'text',
        text: JSON.stringify(payload),
      },
    ],
    ...(isError ? { isError: true } : {}),
  };
}

export async function handleExtractTextTool(request: CallToolRequest): Promise<any> {
  const { text, dataset_name } = request.params.arguments as {
    text: string;
    dataset_name?: string;
  };

  if (!text) {
    throw new Error('text parameter is required');
  }

  const result = await extractFromText(text);

  if (!result.success) {
    throw new Error(`Extraction failed: ${result.error}`);
  }

  return toToolResult({
      status: 'success',
      message: 'Text extraction completed',
      data: result.data,
      dataset: dataset_name || 'default',
    });
}

export async function handleExtractGraphTool(request: CallToolRequest): Promise<any> {
  const { gcs_bucket, gcs_prefix, dataset_name } = request.params.arguments as {
    gcs_bucket: string;
    gcs_prefix: string;
    dataset_name: string;
  };

  if (!gcs_bucket || !gcs_prefix || !dataset_name) {
    throw new Error('gcs_bucket, gcs_prefix, and dataset_name are required');
  }

  const result = await extractFromGCS(gcs_bucket, gcs_prefix, dataset_name);

  if (!result.success) {
    throw new Error(`Graph extraction failed: ${result.error}`);
  }

  return toToolResult({
      status: 'success',
      message: 'Graph extraction completed',
      data: result.data,
      dataset: dataset_name,
    });
}

export async function handleQueryGraphTool(request: CallToolRequest): Promise<any> {
  const { cypher_query, dataset_name } = request.params.arguments as {
    cypher_query: string;
    dataset_name: string;
  };

  if (!cypher_query) {
    throw new Error('cypher_query is required');
  }

  const result = await queryGraph(cypher_query, dataset_name || '');

  return toToolResult({
      status: result.success ? 'success' : 'error',
      message: result.success ? 'Query executed' : result.error,
      data: result.data,
      query: cypher_query,
    }, !result.success);
}

export async function handleVisualizeGraphTool(request: CallToolRequest): Promise<any> {
  const { dataset_name, output_path } = request.params.arguments as {
    dataset_name: string;
    output_path?: string;
  };

  if (!dataset_name) {
    throw new Error('dataset_name is required');
  }

  const path = output_path || `/tmp/${dataset_name}-graph.png`;
  const result = await visualizeGraph(dataset_name, path);

  if (!result.success) {
    throw new Error(`Visualization failed: ${result.error}`);
  }

  return toToolResult({
      status: 'success',
      message: 'Graph visualization created',
      data: result.data,
      output_path: path,
      dataset: dataset_name,
    });
}

export async function handleListDatasetsTool(): Promise<any> {
  const result = await listDatasets();

  return toToolResult({
      status: result.success ? 'success' : 'error',
      message: result.success ? 'Datasets listed' : result.error,
      data: result.data,
    }, !result.success);
}

export async function handleSummarizeTool(request: CallToolRequest): Promise<any> {
  const { dataset_name, max_nodes } = request.params.arguments as {
    dataset_name: string;
    max_nodes?: number;
  };

  if (!dataset_name) {
    throw new Error('dataset_name is required');
  }

  // Query top nodes by relationship count
  const query = `
    MATCH (n)-[r]-(m)
    RETURN n.name as entity, count(r) as connections, labels(n) as types
    ORDER BY connections DESC
    LIMIT ${max_nodes || 10}
  `;

  const result = await queryGraph(query, dataset_name);

  if (!result.success) {
    throw new Error(`Summary failed: ${result.error}`);
  }

  return toToolResult({
      status: 'success',
      message: 'Dataset summary generated',
      data: result.data,
      dataset: dataset_name,
    });
}

export async function handleDemoPipelineTool(request: CallToolRequest): Promise<any> {
  const { dataset_name } = request.params.arguments as {
    dataset_name?: string;
  };

  const name = dataset_name || 'demo';
  const result = await runDemoPipeline(name);

  if (!result.success) {
    throw new Error(`Demo pipeline failed: ${result.error}`);
  }

  return toToolResult({
      status: 'success',
      message: 'Demo pipeline completed',
      data: result.data,
      dataset: name,
    });
}
