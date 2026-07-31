// @vitest-environment node

import { describe, expect, it } from 'vitest';

import { createBackendLaunchSpec } from './backend-launcher.mjs';

describe('createBackendLaunchSpec', () => {
  it('builds the shared production backend command and CORS defaults', () => {
    const launch = createBackendLaunchSpec({
      host: '127.0.0.1',
      port: 8000,
      frontendPort: 3000,
      projectRoot: '/project',
      env: { PATH: '/bin' },
    });

    expect(launch.command).toBe('uv');
    expect(launch.args).toEqual([
      'run',
      'uvicorn',
      'cc_deep_research.web_server:create_app',
      '--factory',
      '--ws', 'websockets-sansio',
      '--host', '127.0.0.1',
      '--port', '8000',
    ]);
    expect(launch.options).toMatchObject({
      cwd: '/project',
      stdio: 'pipe',
      env: {
        PATH: '/bin',
        CORS_ALLOWED_ORIGINS: [
          'http://localhost:3000',
          'http://127.0.0.1:3000',
          'http://[::1]:3000',
        ].join(','),
      },
    });
  });

  it('adds reload and preserves an explicit CORS policy for development', () => {
    const launch = createBackendLaunchSpec({
      host: '0.0.0.0',
      port: 9000,
      frontendPort: 4000,
      projectRoot: '/project',
      reload: true,
      env: { CORS_ALLOWED_ORIGINS: 'https://dashboard.example' },
    });

    expect(launch.args).toContain('--reload');
    expect(launch.options.env.CORS_ALLOWED_ORIGINS).toBe(
      'https://dashboard.example',
    );
  });
});
