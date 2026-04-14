#!/usr/bin/env node

/**
 * Production launcher for CC Deep Research Dashboard.
 *
 * Builds the Next.js frontend, starts the FastAPI backend, and then starts the
 * production Next.js server. Handles graceful shutdown and labels logs clearly.
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

  if (child.stdout) {
    forward(child.stdout);
  }
  if (child.stderr) {
    forward(child.stderr);
  }

  child.on('error', (error) => {
    log(prefixColor, `[${label}] failed to start: ${error.message}`);
  });
}

function dashboardEnv(frontendPort, backendPort) {
  return {
    ...process.env,
    PORT: String(frontendPort),
    NEXT_PUBLIC_CC_BACKEND_ORIGIN: `http://localhost:${backendPort}`,
    NEXT_PUBLIC_CC_API_BASE_URL: `http://localhost:${backendPort}/api`,
    NEXT_PUBLIC_CC_WS_BASE_URL: `ws://localhost:${backendPort}/ws`,
  };
}

function runCommand(command, args, { cwd, env, label, color }) {
  return new Promise((resolvePromise, rejectPromise) => {
    const child = spawn(command, args, {
      cwd,
      env,
      stdio: 'pipe',
    });

    attachLogs(child, color, label);

    child.on('exit', (code, signal) => {
      if (code === 0) {
        resolvePromise();
        return;
      }

      const detail = code !== null ? `code ${code}` : `signal ${signal ?? 'unknown'}`;
      rejectPromise(new Error(`${label} exited with ${detail}`));
    });
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
  ], {
    cwd: projectRoot,
    stdio: 'pipe',
  });

  attachLogs(backend, COLORS.cyan, 'backend');
  return backend;
}

function startFrontend(frontendPort, backendPort) {
  log(COLORS.magenta, `[frontend] Starting Next.js production server on port ${frontendPort}...`);

  // Use PORT env var; do not pass --port flag to next start as it may conflict
  // with the PORT environment variable in some Next.js versions.
  const frontend = spawn('npm', ['run', 'start'], {
    cwd: rootDir,
    stdio: 'pipe',
    env: dashboardEnv(frontendPort, backendPort),
  });

  attachLogs(frontend, COLORS.magenta, 'frontend');
  return frontend;
}

let backend;
let frontend;
let isShuttingDown = false;

// shutdown() is idempotent: the isShuttingDown guard prevents double-shutdown
// when both a signal handler AND a process exit handler fire simultaneously.
// The first call kills child processes and schedules process.exit;
// subsequent calls are no-ops for safety.
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
  // Exit handlers are attached before spawn so we don't miss events from
  // processes that exit very quickly after startup.
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

  log(COLORS.green, 'Preparing CC Deep Research Dashboard production environment...');
  if (backendPort !== DEFAULT_BACKEND_PORT) {
    log(COLORS.green, `Preferred backend port ${DEFAULT_BACKEND_PORT} is busy, using ${backendPort}`);
  }
  if (frontendPort !== DEFAULT_FRONTEND_PORT) {
    log(COLORS.green, `Preferred frontend port ${DEFAULT_FRONTEND_PORT} is busy, using ${frontendPort}`);
  }

  log(COLORS.magenta, '[frontend] Building Next.js production bundle...');
  const buildError = await runCommand('npm', ['run', 'build'], {
    cwd: rootDir,
    env: dashboardEnv(frontendPort, backendPort),
    label: 'frontend-build',
    color: COLORS.magenta,
  }).then(() => null).catch((err) => err);

  if (buildError) {
    log(COLORS.reset, `Build failed: ${buildError.message}`);
    process.exit(1);
  }

  log(COLORS.green, `Backend:  http://localhost:${backendPort}`);
  log(COLORS.green, `Frontend: http://localhost:${frontendPort}`);
  console.log('');

  backend = startBackend(backendPort);
  frontend = startFrontend(frontendPort, backendPort);
  // Attach exit handlers AFTER spawning so they capture process events.
  // Handlers are registered synchronously so no exit event is missed.
  attachExitHandlers();
}

main().catch((error) => {
  log(COLORS.reset, `Failed to start production environment: ${error.message}`);
  process.exit(1);
});
