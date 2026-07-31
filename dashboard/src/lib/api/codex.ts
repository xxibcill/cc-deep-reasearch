import { apiClient } from '@/lib/api/client';
import type {
  CodexAccountResponse,
  CodexLoginResponse,
} from '@/types/codex';

export const CODEX_AUTH_TIMEOUT_MS = 75_000;

export async function getCodexAccount(): Promise<CodexAccountResponse> {
  const response = await apiClient.get<CodexAccountResponse>('/llm/codex/account', {
    timeout: CODEX_AUTH_TIMEOUT_MS,
  });
  return response.data;
}

export async function getActiveCodexLogin(): Promise<CodexLoginResponse | null> {
  const response = await apiClient.get<CodexLoginResponse | null>(
    '/llm/codex/login/active',
    { timeout: CODEX_AUTH_TIMEOUT_MS }
  );
  return response.data;
}

export async function startCodexBrowserLogin(): Promise<CodexLoginResponse> {
  const response = await apiClient.post<CodexLoginResponse>(
    '/llm/codex/login/browser',
    undefined,
    { timeout: CODEX_AUTH_TIMEOUT_MS }
  );
  return response.data;
}

export async function startCodexDeviceCodeLogin(): Promise<CodexLoginResponse> {
  const response = await apiClient.post<CodexLoginResponse>(
    '/llm/codex/login/device-code',
    undefined,
    { timeout: CODEX_AUTH_TIMEOUT_MS }
  );
  return response.data;
}

export async function getCodexLogin(loginId: string): Promise<CodexLoginResponse> {
  const encodedLoginId = encodeURIComponent(loginId);
  const response = await apiClient.get<CodexLoginResponse>(
    `/llm/codex/login/${encodedLoginId}`,
    { timeout: CODEX_AUTH_TIMEOUT_MS }
  );
  return response.data;
}

export async function cancelCodexLogin(loginId: string): Promise<CodexLoginResponse> {
  const encodedLoginId = encodeURIComponent(loginId);
  const response = await apiClient.delete<CodexLoginResponse>(
    `/llm/codex/login/${encodedLoginId}`,
    { timeout: CODEX_AUTH_TIMEOUT_MS }
  );
  return response.data;
}

export async function logoutCodex(): Promise<CodexAccountResponse> {
  const response = await apiClient.post<CodexAccountResponse>(
    '/llm/codex/logout',
    undefined,
    { timeout: CODEX_AUTH_TIMEOUT_MS }
  );
  return response.data;
}
