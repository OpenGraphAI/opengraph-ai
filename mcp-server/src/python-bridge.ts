import { spawn, ChildProcessWithoutNullStreams } from 'child_process';
import path from 'path';
import { fileURLToPath } from 'url';
import globalProcess from 'process';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const projectRoot = path.join(__dirname, '..');

export interface PythonResult {
  success: boolean;
  data?: any;
  error?: string;
  stderr?: string;
}

export interface ProgressCallback {
  (progress: number, message: string): void;
}

/**
 * Spawns Python CLI command and captures output
 * Supports progress streaming via stderr
 */
export async function executePythonCommand(
  command: string,
  args: string[] = [],
  onProgress?: ProgressCallback
): Promise<PythonResult> {
  return new Promise((resolve) => {
    const pythonPath: string = globalProcess.env.PYTHON_EXECUTABLE || 'python3';
    const cliArgs = ['-m', 'cli', command, ...args];

    let stdout = '';
    let stderr = '';
    let lastProgress = 0;

    const childProcess: ChildProcessWithoutNullStreams = spawn(pythonPath, cliArgs, {
      cwd: projectRoot,
      env: {
        ...globalProcess.env,
        PYTHONUNBUFFERED: '1',
      },
    });

    // Capture stdout (results)
    childProcess.stdout?.on('data', (data: Buffer) => {
      stdout += data.toString();
    });

    // Parse stderr for progress updates
    childProcess.stderr?.on('data', (data: Buffer) => {
      const text = data.toString();
      stderr += text;

      // Look for progress indicators: [50/150] or [33%]
      const progressMatch = text.match(/\[(\d+)\/(\d+)\]|\[(\d+)%\]/);
      if (progressMatch) {
        let progress = 0;
        if (progressMatch[3]) {
          // Percentage format
          progress = parseInt(progressMatch[3], 10);
        } else {
          // Fraction format
          progress = Math.round((parseInt(progressMatch[1], 10) / parseInt(progressMatch[2], 10)) * 100);
        }

        if (progress > lastProgress && onProgress) {
          onProgress(progress, text.trim());
          lastProgress = progress;
        }
      }
    });

    childProcess.on('close', (code: number | null) => {
      if (code === 0) {
        try {
          // Try to parse as JSON first
          const data = stdout.trim() ? JSON.parse(stdout) : null;
          resolve({
            success: true,
            data,
          });
        } catch (e) {
          // If not JSON, return as raw string
          resolve({
            success: true,
            data: stdout.trim(),
          });
        }
      } else {
        resolve({
          success: false,
          error: `Command failed with code ${code}`,
          stderr: stderr.trim(),
        });
      }
    });

    childProcess.on('error', (err: Error) => {
      resolve({
        success: false,
        error: err.message,
        stderr: stderr.trim(),
      });
    });
  });
}

/**
 * Extract entities and relationships from text
 */
export async function extractFromText(
  text: string,
  onProgress?: ProgressCallback
): Promise<PythonResult> {
  // Use JSON mode to pass text safely
  const args = ['--text-data', text, '--format', 'json'];
  return executePythonCommand('extract', args, onProgress);
}

/**
 * Extract from CSV file in GCS
 */
export async function extractFromGCS(
  bucketName: string,
  prefix: string,
  datasetName: string,
  onProgress?: ProgressCallback
): Promise<PythonResult> {
  const args = [
    '--gcs-bucket',
    bucketName,
    '--gcs-prefix',
    prefix,
    '--dataset-name',
    datasetName,
    '--format',
    'json',
  ];
  return executePythonCommand('extract', args, onProgress);
}

/**
 * Run a Cypher query directly against Neo4j
 */
export async function runCypherQuery(
  cypher: string,
  onProgress?: ProgressCallback
): Promise<PythonResult> {
  return new Promise((resolve) => {
    const pythonPath: string = globalProcess.env.PYTHON_EXECUTABLE || 'python3';
    const scriptPath = path.join(__dirname, '..', '..', 'neo4j_query.py');
    let stdout = '';
    let stderr = '';

    const childProcess: ChildProcessWithoutNullStreams = spawn(pythonPath, [scriptPath, cypher], {
      cwd: path.join(__dirname, '..'),
      env: { ...globalProcess.env },
    });

    childProcess.stdout?.on('data', (data: Buffer) => { stdout += data.toString(); });
    childProcess.stderr?.on('data', (data: Buffer) => { stderr += data.toString(); });

    childProcess.on('close', (code: number | null) => {
      try {
        const parsed = JSON.parse(stdout.trim());
        resolve(parsed.success ? { success: true, data: parsed.data } : { success: false, error: parsed.error, stderr });
      } catch {
        resolve({ success: false, error: `Parse error: ${stdout}`, stderr });
      }
    });

    childProcess.on('error', (err: Error) => resolve({ success: false, error: err.message }));
  });
}

/**
 * Query graph from database
 */
export async function queryGraph(
  query: string,
  datasetName: string,
  onProgress?: ProgressCallback
): Promise<PythonResult> {
  return runCypherQuery(query, onProgress);
}

/**
 * Visualize graph as PNG
 */
export async function visualizeGraph(
  datasetName: string,
  outputPath: string,
  onProgress?: ProgressCallback
): Promise<PythonResult> {
  const args = ['--dataset', datasetName, '--output', outputPath, '--format', 'json'];
  return executePythonCommand('visualize', args, onProgress);
}

/**
 * List available datasets by querying Neo4j directly
 */
export async function listDatasets(onProgress?: ProgressCallback): Promise<PythonResult> {
  return runCypherQuery('MATCH (n) WHERE n.dataset IS NOT NULL RETURN DISTINCT n.dataset as dataset ORDER BY dataset', onProgress);
}

/**
 * Run full demo pipeline
 */
export async function runDemoPipeline(
  datasetName: string,
  onProgress?: ProgressCallback
): Promise<PythonResult> {
  const args = ['--dataset', datasetName, '--format', 'json'];
  return executePythonCommand('demo', args, onProgress);
}
