import { describe, expect, it, vi } from 'vitest';

import {
  CODEX_LOGIN_RECOVERY_STORAGE_KEY,
  clearCodexLoginRecovery,
  loadCodexLoginRecovery,
  loginResponseFromRecovery,
  parseCodexLoginRecovery,
  rebaseCodexSettingsDraft,
  serializeCodexLoginRecovery,
  storeCodexLoginRecovery,
  type CodexLoginRecovery,
  type CodexSettingsDraft,
} from '@/lib/codex-provider-state';

function makeSettings(
  overrides: Partial<CodexSettingsDraft> = {}
): CodexSettingsDraft {
  return {
    enabled: false,
    model: '',
    reasoningEffort: 'medium',
    timeoutSeconds: '180',
    ...overrides,
  };
}

function makeStorage(initialValue: string | null = null) {
  let value = initialValue;
  return {
    getItem: vi.fn(() => value),
    setItem: vi.fn((_key: string, nextValue: string) => {
      value = nextValue;
    }),
    removeItem: vi.fn(() => {
      value = null;
    }),
  };
}

describe('rebaseCodexSettingsDraft', () => {
  it('preserves dirty fields while adopting new values for clean fields', () => {
    const previous = makeSettings();
    const draft = makeSettings({ model: 'draft-model' });
    const next = makeSettings({
      enabled: true,
      model: 'server-model',
      reasoningEffort: 'high',
      timeoutSeconds: '240',
    });

    expect(rebaseCodexSettingsDraft(draft, previous, next)).toEqual({
      enabled: true,
      model: 'draft-model',
      reasoningEffort: 'high',
      timeoutSeconds: '240',
    });
  });

  it('treats model-only whitespace as clean when rebasing', () => {
    const previous = makeSettings({ model: 'runtime-default' });
    const draft = makeSettings({ model: ' runtime-default ' });
    const next = makeSettings({ model: 'new-runtime-default' });

    expect(rebaseCodexSettingsDraft(draft, previous, next).model).toBe(
      'new-runtime-default'
    );
  });
});

describe('Codex login recovery', () => {
  const now = Date.UTC(2026, 6, 31, 12, 5);
  const recovery: CodexLoginRecovery = {
    login_id: 'login-123',
    flow: 'device_code',
    timestamp: now - 1_000,
  };

  it('serializes only the recovery allowlist', () => {
    const serialized = serializeCodexLoginRecovery({
      ...recovery,
      auth_url: 'https://example.invalid/private',
      user_code: 'SECRET-CODE',
      token: 'secret-token',
    } as CodexLoginRecovery);

    expect(JSON.parse(serialized)).toEqual(recovery);
    expect(serialized).not.toContain('auth_url');
    expect(serialized).not.toContain('user_code');
    expect(serialized).not.toContain('token');
  });

  it('rejects and clears expired recovery state', () => {
    const expired = serializeCodexLoginRecovery({
      ...recovery,
      timestamp: now - 10 * 60 * 1_000,
    });
    const storage = makeStorage(expired);

    expect(loadCodexLoginRecovery(storage, now, 10 * 60 * 1_000)).toBeNull();
    expect(storage.removeItem).toHaveBeenCalledWith(
      CODEX_LOGIN_RECOVERY_STORAGE_KEY
    );
  });

  it('rejects payloads containing fields outside the recovery allowlist', () => {
    const serialized = JSON.stringify({
      ...recovery,
      auth_url: 'https://example.invalid/private',
    });

    expect(parseCodexLoginRecovery(serialized, now, 10 * 60 * 1_000)).toBeNull();
  });

  it('stores, restores, and clears an active login without sensitive fields', () => {
    const storage = makeStorage();

    storeCodexLoginRecovery(storage, recovery);
    const serialized = storage.setItem.mock.calls[0]?.[1];
    expect(serialized ? JSON.parse(serialized) : null).toEqual(recovery);
    expect(loadCodexLoginRecovery(storage, now, 10 * 60 * 1_000)).toEqual(
      recovery
    );

    clearCodexLoginRecovery(storage);
    expect(storage.removeItem).toHaveBeenCalledWith(
      CODEX_LOGIN_RECOVERY_STORAGE_KEY
    );
  });

  it('creates a token-free pending snapshot for resumed polling', () => {
    expect(loginResponseFromRecovery(recovery)).toMatchObject({
      login_id: 'login-123',
      flow: 'device_code',
      status: 'pending',
      auth_url: null,
      verification_url: null,
      user_code: null,
    });
  });
});
