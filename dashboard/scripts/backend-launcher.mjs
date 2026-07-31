/** Build the shared FastAPI backend spawn specification. */
export function createBackendLaunchSpec({
  host,
  port,
  frontendPort,
  projectRoot,
  reload = false,
  env = process.env,
}) {
  const args = [
    'run',
    'uvicorn',
    'cc_deep_research.web_server:create_app',
    '--factory',
    '--ws', 'websockets-sansio',
    '--host', host,
    '--port', String(port),
  ];
  if (reload) {
    args.push('--reload');
  }

  return {
    command: 'uv',
    args,
    options: {
      cwd: projectRoot,
      stdio: 'pipe',
      env: {
        ...env,
        CORS_ALLOWED_ORIGINS: env.CORS_ALLOWED_ORIGINS || [
          `http://localhost:${frontendPort}`,
          `http://127.0.0.1:${frontendPort}`,
          `http://[::1]:${frontendPort}`,
        ].join(','),
      },
    },
  };
}
