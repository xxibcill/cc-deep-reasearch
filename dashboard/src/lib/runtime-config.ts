const DEFAULT_BACKEND_ORIGIN = 'http://localhost:8000';
const DEFAULT_WEBSOCKET_BASE_URL = 'ws://localhost:8000/ws';

function trimTrailingSlashes(value: string): string {
  return value.replace(/\/+$/, '');
}

function normalizeWebSocketPath(pathname: string): string {
  const trimmedPath = trimTrailingSlashes(pathname);
  const pathWithoutSession = trimmedPath.replace(/\/session(?:\/.*)?$/, '');

  if (!pathWithoutSession || pathWithoutSession === '/') {
    return '/ws';
  }

  if (pathWithoutSession.endsWith('/ws')) {
    return pathWithoutSession;
  }

  return `${pathWithoutSession}/ws`;
}

function normalizeWebSocketBaseUrl(value: string): string {
  try {
    const url = new URL(value);
    if (url.protocol === 'http:') {
      url.protocol = 'ws:';
    } else if (url.protocol === 'https:') {
      url.protocol = 'wss:';
    }

    if (url.protocol !== 'ws:' && url.protocol !== 'wss:') {
      return DEFAULT_WEBSOCKET_BASE_URL;
    }

    // Accept either the websocket namespace or the backend origin in env config.
    url.pathname = normalizeWebSocketPath(url.pathname);
    url.search = '';
    url.hash = '';
    return trimTrailingSlashes(url.toString());
  } catch {
    return DEFAULT_WEBSOCKET_BASE_URL;
  }
}

const backendOrigin = trimTrailingSlashes(
  process.env.NEXT_PUBLIC_CC_BACKEND_ORIGIN ?? DEFAULT_BACKEND_ORIGIN
);

export const dashboardRuntimeConfig = {
  backendOrigin,
  apiBaseUrl: trimTrailingSlashes(
    process.env.NEXT_PUBLIC_CC_API_BASE_URL ?? `${backendOrigin}/api`
  ),
  websocketBaseUrl: normalizeWebSocketBaseUrl(
    process.env.NEXT_PUBLIC_CC_WS_BASE_URL ?? backendOrigin
  ),
};
