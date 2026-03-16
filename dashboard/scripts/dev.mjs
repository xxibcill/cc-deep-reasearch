#!/usr/bin/env node

/**
 * Development launcher for CC Deep Research Dashboard
 *
 * Starts both the backend API (FastAPI on port 8000) and the frontend (Next.js on port 3000).
 * Handles graceful shutdown and logs both processes with clear prefixes.
 */

import { spawn } from 'child_process';
import { dirname, resolve } from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);
const rootDir = resolve(__dirname, '..');
const projectRoot = resolve(__dirname, '..', '..');

const BACKEND_PORT = process.env.BACKEND_PORT || '8000';
const FRONTEND_PORT = process.env.FRONTEND_PORT || '3000';

// Colors for log prefixes
const COLORS = {
  reset: '\x1b[0m',
  cyan: '\x1b[36m',
  magenta: '\x1b[35m',
  green: '\x1b[32m',
};

function log(prefix, message) {
  const timestamp = new Date().toISOString().slice(11, 19);
  console.log(`[${timestamp}] ${prefix}${message}${COLORS.reset}`);
}

function startBackend() {
  log(COLORS.cyan, '[backend] Starting FastAPI server...');

  const backend = spawn('uv', [
    'run',
    'uvicorn',
    'cc_deep_research.web_server:create_app',
    '--factory',
    '--host', '0.0.0.0',
    '--port', BACKEND_PORT,
    '--reload',
  ], {
    cwd: projectRoot,
    stdio: 'pipe',
    shell: true,
  });

  backend.stdout.on('data', (data) => {
    const lines = data.toString().trim().split('\n');
    for (const line of lines) {
      log(COLORS.cyan, `[backend] ${line}`);
    }
  });

  backend.stderr.on('data', (data) => {
    const lines = data.toString().trim().split('\n');
    for (const line of lines) {
      log(COLORS.cyan, `[backend] ${line}`);
    }
  });

  return backend;
}

function startFrontend() {
  log(COLORS.magenta, '[frontend] Starting Next.js dev server...');

  const frontend = spawn('npm', ['run', 'dev'], {
    cwd: rootDir,
    stdio: 'pipe',
    shell: true,
    env: {
      ...process.env,
      PORT: FRONTEND_PORT,
      NEXT_PUBLIC_API_BASE_URL: `http://localhost:${BACKEND_PORT}`,
    },
  });

  frontend.stdout.on('data', (data) => {
    const lines = data.toString().trim().split('\n');
    for (const line of lines) {
      log(COLORS.magenta, `[frontend] ${line}`);
    }
  });

  frontend.stderr.on('data', (data) => {
    const lines = data.toString().trim().split('\n');
    for (const line of lines) {
      log(COLORS.magenta, `[frontend] ${line}`);
    }
  });

  return frontend;
}

// Main
log(COLORS.green, 'Starting CC Deep Research Dashboard development environment...');
log(COLORS.green, `Backend:  http://localhost:${BACKEND_PORT}`);
log(COLORS.green, `Frontend: http://localhost:${FRONTEND_PORT}`);
console.log('');

const backend = startBackend();
const frontend = startFrontend();

// Handle graceful shutdown
const shutdown = (signal) => {
  log(COLORS.green, `\nReceived ${signal}, shutting down...`);

  frontend.kill('SIGTERM');
  backend.kill('SIGTERM');

  setTimeout(() => {
    log(COLORS.green, 'Goodbye!');
    process.exit(0);
  }, 1000);
};

process.on('SIGINT', () => shutdown('SIGINT'));
process.on('SIGTERM', () => shutdown('SIGTERM'));

// Handle child process exits
frontend.on('exit', (code) => {
  if (code !== 0 && code !== null) {
    log(COLORS.reset, `[frontend] exited with code ${code}`);
  }
});

backend.on('exit', (code) => {
  if (code !== 0 && code !== null) {
    log(COLORS.reset, `[backend] exited with code ${code}`);
  }
});
