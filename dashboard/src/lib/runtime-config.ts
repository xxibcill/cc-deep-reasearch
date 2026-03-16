const DEFAULT_BACKEND_ORIGIN = 'http://localhost:8000';

function trimTrailingSlashes(value: string): string {
  return value.replace(/\/+$/, '');
}

function toWebSocketOrigin(origin: string): string {
  try {
    const url = new URL(origin);
    url.protocol = url.protocol === 'https:' ? 'wss:' : 'ws:';
    url.pathname = '';
    url.search = '';
    url.hash = '';
    return trimTrailingSlashes(url.toString());
  } catch {
    return 'ws://localhost:8000';
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
  websocketBaseUrl: trimTrailingSlashes(
    process.env.NEXT_PUBLIC_CC_WS_BASE_URL ?? `${toWebSocketOrigin(backendOrigin)}/ws`
  ),
};
