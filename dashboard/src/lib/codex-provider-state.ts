import type { CodexLoginFlow, CodexLoginResponse } from '@/types/codex';

export type CodexReasoningEffort = 'minimal' | 'low' | 'medium' | 'high' | 'xhigh';

export type CodexSettingsDraft = {
  enabled: boolean;
  model: string;
  reasoningEffort: CodexReasoningEffort;
  timeoutSeconds: string;
};

export type CodexLoginRecovery = {
  login_id: string;
  flow: CodexLoginFlow;
  timestamp: number;
};

type SessionStorageLike = Pick<Storage, 'getItem' | 'setItem' | 'removeItem'>;

export const CODEX_LOGIN_RECOVERY_STORAGE_KEY = 'ccdr.codex-active-login';

const CODEX_LOGIN_RECOVERY_KEYS = ['flow', 'login_id', 'timestamp'] as const;

function modelsMatch(left: string, right: string): boolean {
  return left.trim() === right.trim();
}

export function rebaseCodexSettingsDraft(
  draft: CodexSettingsDraft,
  previousBaseline: CodexSettingsDraft,
  nextBaseline: CodexSettingsDraft
): CodexSettingsDraft {
  return {
    enabled:
      draft.enabled === previousBaseline.enabled ? nextBaseline.enabled : draft.enabled,
    model: modelsMatch(draft.model, previousBaseline.model)
      ? nextBaseline.model
      : draft.model,
    reasoningEffort:
      draft.reasoningEffort === previousBaseline.reasoningEffort
        ? nextBaseline.reasoningEffort
        : draft.reasoningEffort,
    timeoutSeconds:
      draft.timeoutSeconds === previousBaseline.timeoutSeconds
        ? nextBaseline.timeoutSeconds
        : draft.timeoutSeconds,
  };
}

export function serializeCodexLoginRecovery(recovery: CodexLoginRecovery): string {
  return JSON.stringify({
    login_id: recovery.login_id,
    flow: recovery.flow,
    timestamp: recovery.timestamp,
  });
}

export function parseCodexLoginRecovery(
  serialized: string,
  now: number,
  maxAgeMs: number
): CodexLoginRecovery | null {
  try {
    const value = JSON.parse(serialized) as Record<string, unknown>;
    const keys = Object.keys(value).sort();
    const expectedKeys = [...CODEX_LOGIN_RECOVERY_KEYS].sort();
    if (
      keys.length !== expectedKeys.length ||
      keys.some((key, index) => key !== expectedKeys[index])
    ) {
      return null;
    }
    if (
      typeof value.login_id !== 'string' ||
      value.login_id.trim().length === 0 ||
      (value.flow !== 'browser' && value.flow !== 'device_code') ||
      typeof value.timestamp !== 'number' ||
      !Number.isFinite(value.timestamp) ||
      value.timestamp <= 0 ||
      value.timestamp > now ||
      now - value.timestamp >= maxAgeMs
    ) {
      return null;
    }
    return {
      login_id: value.login_id,
      flow: value.flow,
      timestamp: value.timestamp,
    };
  } catch {
    return null;
  }
}

export function storeCodexLoginRecovery(
  storage: SessionStorageLike,
  recovery: CodexLoginRecovery
): void {
  try {
    storage.setItem(
      CODEX_LOGIN_RECOVERY_STORAGE_KEY,
      serializeCodexLoginRecovery(recovery)
    );
  } catch {
    // Storage can be unavailable in hardened browser contexts.
  }
}

export function loadCodexLoginRecovery(
  storage: SessionStorageLike,
  now: number,
  maxAgeMs: number
): CodexLoginRecovery | null {
  try {
    const serialized = storage.getItem(CODEX_LOGIN_RECOVERY_STORAGE_KEY);
    if (!serialized) {
      return null;
    }
    const recovery = parseCodexLoginRecovery(serialized, now, maxAgeMs);
    if (!recovery) {
      storage.removeItem(CODEX_LOGIN_RECOVERY_STORAGE_KEY);
    }
    return recovery;
  } catch {
    return null;
  }
}

export function clearCodexLoginRecovery(storage: SessionStorageLike): void {
  try {
    storage.removeItem(CODEX_LOGIN_RECOVERY_STORAGE_KEY);
  } catch {
    // Storage can be unavailable in hardened browser contexts.
  }
}

export function loginResponseFromRecovery(
  recovery: CodexLoginRecovery
): CodexLoginResponse {
  return {
    login_id: recovery.login_id,
    flow: recovery.flow,
    status: 'pending',
    auth_url: null,
    verification_url: null,
    user_code: null,
    error: null,
    created_at: new Date(recovery.timestamp).toISOString(),
    completed_at: null,
  };
}
