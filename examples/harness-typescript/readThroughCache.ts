// Minimal dnr read-through cache adapter for TypeScript/Node agent harnesses.
// dnr misses are soft, normal parsing still happens, and cache writes never
// fail the user task.

import { spawn } from "node:child_process";
import { mkdtemp, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";

type Reader = (file: string) => Promise<string>;

type RunResult = {
  code: number | null;
  stdout: string;
  stderr: string;
};

function dnrBin(): string {
  return process.env.DNR_BIN || "dnr";
}

function runDnr(args: string[]): Promise<RunResult | null> {
  return new Promise((resolve) => {
    const child = spawn(dnrBin(), args, { stdio: ["ignore", "pipe", "pipe"] });
    let stdout = "";
    let stderr = "";

    child.stdout.setEncoding("utf8");
    child.stderr.setEncoding("utf8");
    child.stdout.on("data", (chunk) => {
      stdout += chunk;
    });
    child.stderr.on("data", (chunk) => {
      stderr += chunk;
    });
    child.on("error", () => resolve(null));
    child.on("close", (code) => resolve({ code, stdout, stderr }));
  });
}

export async function readCachedTranscript(file: string): Promise<string | null> {
  const result = await runDnr(["read", file]);
  if (!result || result.code !== 0) return null;
  return result.stdout.trim().length > 0 ? result.stdout : null;
}

export async function cacheTranscript(
  file: string,
  transcript: string,
  options: { method: string; transcriber: string },
): Promise<void> {
  if (transcript.trim().length === 0) return;

  let dir: string | null = null;
  try {
    dir = await mkdtemp(join(tmpdir(), "dnr-"));
    const transcriptFile = join(dir, "transcript.md");
    await writeFile(transcriptFile, transcript, "utf8");
    await runDnr([
      "record",
      file,
      "--transcript-file",
      transcriptFile,
      "--method",
      options.method,
      "--transcriber",
      options.transcriber,
    ]);
  } catch {
    // Cache writes are best-effort. Never fail the user's task.
  } finally {
    if (dir) await rm(dir, { recursive: true, force: true });
  }
}

export async function readWithDnrCache(
  file: string,
  normalReader: Reader,
  options: { method: string; transcriber: string },
): Promise<string> {
  const cached = await readCachedTranscript(file);
  if (cached !== null) return cached;

  const transcript = await normalReader(file);
  await cacheTranscript(file, transcript, options);
  return transcript;
}

export async function queryFolder(folder: string, queryArgs: string[]): Promise<string | null> {
  await runDnr(["index", folder]);
  const result = await runDnr(["query", folder, ...queryArgs]);
  if (!result || result.code !== 0) return null;
  return result.stdout;
}
