/**
 * MCP tool handlers for OpenGraph AI.
 *
 * Bridges between MCP protocol and the Python CLI via child process spawning.
 */

import { spawn } from "child_process";
import { join } from "path";
import { fileURLToPath } from "url";
import { dirname } from "path";

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);
const PROJECT_ROOT = join(__dirname, "../..");

function spawnPythonCLI(args: string[]): Promise<string> {
  return new Promise((resolve, reject) => {
    const proc = spawn(
      `${PROJECT_ROOT}/.venv/bin/python`,
      ["-m", "cli", ...args],
      {
        cwd: PROJECT_ROOT,
      }
    );

    let stdout = "";
    let stderr = "";

    proc.stdout?.on("data", (data: any) => {
      stdout += data.toString();
    });

    proc.stderr?.on("data", (data: any) => {
      stderr += data.toString();
    });

    proc.on("close", (code: any) => {
      if (code === 0) {
        resolve(stdout);
      } else {
        reject(new Error(`CLI failed with code ${code}: ${stderr}`));
      }
    });

    proc.on("error", (err: any) => {
      reject(err);
    });
  });
}

export async function extractText(
  text: string,
  useLlm: boolean
): Promise<string> {
  // Write text to temp file since stdin is harder to manage
  const fs = await import("fs/promises");
  const os = await import("os");
  const tmpDir = os.tmpdir();
  const tmpFile = join(tmpDir, `text-extract-${Date.now()}.txt`);

  try {
    await fs.writeFile(tmpFile, text, "utf-8");
    const args = useLlm
      ? ["extract", "text", tmpFile]
      : ["demo", tmpFile, "--output", "/dev/null"];

    return await spawnPythonCLI(args);
  } finally {
    try {
      await fs.unlink(tmpFile);
    } catch {
      // Ignore cleanup errors
    }
  }
}

export async function queryGraph(
  dataset: string,
  query: string
): Promise<string> {
  return spawnPythonCLI(["query", dataset, query]);
}

export async function visualizeGraph(
  dataset: string,
  outputPath: string
): Promise<string> {
  return spawnPythonCLI([
    "visualize",
    dataset,
    "--output",
    outputPath,
    "--schema-view",
  ]);
}

export async function demoPipeline(
  sourcePath: string,
  useLlm: boolean
): Promise<string> {
  const args = useLlm
    ? ["demo", sourcePath, "--llm"]
    : ["demo", sourcePath];

  return spawnPythonCLI(args);
}
