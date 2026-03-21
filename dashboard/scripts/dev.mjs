#!/usr/bin/env node

/**
 * Development launcher for CC Deep Research Dashboard
 *
 * Starts both the backend API (FastAPI on port 8000) and the frontend (Next.js on port 3000).
 * Handles graceful shutdown and logs both processes with clear prefixes.
 */

import { spawn } from 'child_process';
import net from 'net';
import { dirname, resolve } from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);
const rootDir = resolve(__dirname, '..');
const projectRoot = resolve(__dirname, '..', '..');

const DEFAULT_BACKEND_PORT = Number.parseInt(process.env.BACKEND_PORT || '8000', 10);
const DEFAULT_FRONTEND_PORT = Number.parseInt(process.env.FRONTEND_PORT || '3000', 10);

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

function findAvailablePort(startPort, excludedPorts = new Set()) {
  return new Promise((resolvePort, reject) => {
    const tryPort = (port) => {
      if (excludedPorts.has(port)) {
        tryPort(port + 1);
        return;
      }

      const server = net.createServer();

      server.once('error', (error) => {
        server.close(() => {
          if (error.code === 'EADDRINUSE' || error.code === 'EACCES') {
            tryPort(port + 1);
            return;
          }
          reject(error);
        });
      });

      server.once('listening', () => {
        const address = server.address();
        const resolvedPort = typeof address === 'object' && address ? address.port : port;
        server.close(() => resolvePort(resolvedPort));
      });

      server.listen(port, '0.0.0.0');
    };

    tryPort(startPort);
  });
}

function attachLogs(child, prefixColor, label) {
  const forward = (stream) => {
    stream.on('data', (data) => {
      const lines = data.toString().split(/\r?\n/);
      for (const line of lines) {
        if (line.length > 0) {
          log(prefixColor, `[${label}] ${line}`);
        }
      }
    });
  };

  forward(child.stdout);
  forward(child.stderr);

  child.on('error', (error) => {
    log(prefixColor, `[${label}] failed to start: ${error.message}`);
  });
}

function startBackend(port) {
  log(COLORS.cyan, `[backend] Starting FastAPI server on port ${port}...`);

  const backend = spawn('uv', [
    'run',
    'uvicorn',
    'cc_deep_research.web_server:create_app',
    '--factory',
    '--ws', 'websockets-sansio',
    '--host', '0.0.0.0',
    '--port', String(port),
    '--reload',
  ], {
    cwd: projectRoot,
    stdio: 'pipe',
  });

  attachLogs(backend, COLORS.cyan, 'backend');

  return backend;
}

function startFrontend(frontendPort, backendPort) {
  log(COLORS.magenta, `[frontend] Starting Next.js dev server on port ${frontendPort}...`);

  const frontend = spawn('npm', ['run', 'dev:frontend'], {
    cwd: rootDir,
    stdio: 'pipe',
    env: {
      ...process.env,
      PORT: String(frontendPort),
      NEXT_PUBLIC_CC_BACKEND_ORIGIN: `http://localhost:${backendPort}`,
      NEXT_PUBLIC_CC_API_BASE_URL: `http://localhost:${backendPort}/api`,
      NEXT_PUBLIC_CC_WS_BASE_URL: `ws://localhost:${backendPort}/ws`,
      NEXT_PUBLIC_API_BASE_URL: `http://localhost:${backendPort}`,
    },
  });

  attachLogs(frontend, COLORS.magenta, 'frontend');

  return frontend;
}

let backend;
let frontend;
let isShuttingDown = false;

// Handle graceful shutdown
const shutdown = (reason, exitCode = 0) => {
  if (isShuttingDown) {
    return;
  }

  isShuttingDown = true;
  log(COLORS.green, `\nReceived ${reason}, shutting down...`);

  if (frontend && !frontend.killed) {
    frontend.kill('SIGTERM');
  }

  if (backend && !backend.killed) {
    backend.kill('SIGTERM');
  }

  setTimeout(() => {
    log(COLORS.green, 'Goodbye!');
    process.exit(exitCode);
  }, 1000);
};

process.on('SIGINT', () => shutdown('SIGINT'));
process.on('SIGTERM', () => shutdown('SIGTERM'));

function attachExitHandlers() {
  frontend.on('exit', (code, signal) => {
    if (isShuttingDown) {
      return;
    }

    const detail = code !== null ? `code ${code}` : `signal ${signal ?? 'unknown'}`;
    log(COLORS.reset, `[frontend] exited with ${detail}`);
    shutdown('frontend exit', code ?? 1);
  });

  backend.on('exit', (code, signal) => {
    if (isShuttingDown) {
      return;
    }

    const detail = code !== null ? `code ${code}` : `signal ${signal ?? 'unknown'}`;
    log(COLORS.reset, `[backend] exited with ${detail}`);
    shutdown('backend exit', code ?? 1);
  });
}

async function main() {
  const backendPort = await findAvailablePort(DEFAULT_BACKEND_PORT);
  const frontendPort = await findAvailablePort(
    DEFAULT_FRONTEND_PORT,
    new Set([backendPort]),
  );

  log(COLORS.green, 'Starting CC Deep Research Dashboard development environment...');
  if (backendPort !== DEFAULT_BACKEND_PORT) {
    log(COLORS.green, `Preferred backend port ${DEFAULT_BACKEND_PORT} is busy, using ${backendPort}`);
  }
  if (frontendPort !== DEFAULT_FRONTEND_PORT) {
    log(COLORS.green, `Preferred frontend port ${DEFAULT_FRONTEND_PORT} is busy, using ${frontendPort}`);
  }
  log(COLORS.green, `Backend:  http://localhost:${backendPort}`);
  log(COLORS.green, `Frontend: http://localhost:${frontendPort}`);
  console.log('');

  backend = startBackend(backendPort);
  frontend = startFrontend(frontendPort, backendPort);
  attachExitHandlers();
}

main().catch((error) => {
  log(COLORS.reset, `Failed to start development environment: ${error.message}`);
  process.exit(1);
});
