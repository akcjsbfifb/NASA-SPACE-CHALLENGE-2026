import { spawn } from 'node:child_process';
import { createInterface } from 'node:readline';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
export const REPO_ROOT = path.resolve(__dirname, '..');
export function defaultPythonPath(platform = process.platform) {
  return platform === 'win32'
    ? path.join(REPO_ROOT, '.venv', 'Scripts', 'python.exe')
    : path.join(REPO_ROOT, '.venv', 'bin', 'python');
}
export const DEFAULT_PYTHON = defaultPythonPath();
export const DEFAULT_WORKER_SCRIPT = path.join(REPO_ROOT, 'backend/app/workers/artemis_search.py');

export class ArtemisSearchWorker {
  constructor({ python = DEFAULT_PYTHON, script = DEFAULT_WORKER_SCRIPT, env = process.env } = {}) {
    this.python = python;
    this.script = script;
    this.env = env;
    this.child = null;
    this.readline = null;
    this.pending = null;
    this.buffers = [];
    this.startError = null;
    this.exited = null;
  }

  start() {
    if (this.child) return;
    this.child = spawn(this.python, [this.script], {
      cwd: REPO_ROOT,
      env: this.env,
      stdio: ['pipe', 'pipe', 'pipe'],
    });
    this.readline = createInterface({ input: this.child.stdout });
    this.readline.on('line', (line) => {
      if (this.pending) {
        const { resolve, reject } = this.pending;
        this.pending = null;
        try {
          resolve(JSON.parse(line));
        } catch (error) {
          reject(error);
        }
        return;
      }
      this.buffers.push(line);
    });
    this.child.on('exit', (code, signal) => {
      this.exited = { code, signal };
      if (this.pending) {
        const { reject } = this.pending;
        this.pending = null;
        reject(new Error(`worker exited (code=${code}, signal=${signal})`));
      }
    });
    let stderr = '';
    this.child.stderr.setEncoding('utf8');
    this.child.stderr.on('data', (chunk) => {
      stderr += chunk;
    });
    this.child.on('close', (code) => {
      if (code !== 0 && code !== null && !this.startError && this.buffers.length === 0 && !this.pending) {
        const trimmed = stderr.trim();
        if (trimmed) this.startError = new Error(trimmed);
      }
    });
  }

  stop() {
    if (!this.child) return;
    this.child.kill();
    this.child = null;
    this.readline?.close();
    this.readline = null;
    this.pending = null;
    this.buffers = [];
    this.exited = null;
    this.startError = null;
  }

  drainBuffered() {
    const lines = this.buffers;
    this.buffers = [];
    return lines;
  }

  send(payload) {
    this.start();
    return new Promise((resolve, reject) => {
      if (this.exited) {
        reject(new Error(`worker already exited (code=${this.exited.code})`));
        return;
      }
      const buffered = this.drainBuffered();
      if (buffered.length > 0) {
        try {
          resolve(JSON.parse(buffered[0]));
        } catch (error) {
          reject(error);
        }
        return;
      }
      this.pending = { resolve, reject };
      const line = `${JSON.stringify(payload)}\n`;
      const wrote = this.child.stdin.write(line, (err) => {
        if (err) reject(err);
      });
      if (!wrote) {
        this.child.stdin.once('drain', () => {});
      }
    });
  }
}

export async function buscarWithWorker(worker, payload, { retryOnDeath = true } = {}) {
  try {
    return await worker.send(payload);
  } catch (firstError) {
    if (!retryOnDeath) throw firstError;
    worker.stop();
    worker.start();
    return worker.send(payload);
  }
}
