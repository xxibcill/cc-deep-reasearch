import { describe, expect, it } from 'vitest';

import {
  getCodexLoginFailureMessage,
  getCodexLoginOutcome,
  getCodexLoginTransition,
} from '@/lib/codex-login-state';
import type { CodexLoginResponse } from '@/types/codex';

function makeLogin(
  status: CodexLoginResponse['status'],
  error: string | null = null
): CodexLoginResponse {
  return {
    login_id: 'login-123',
    flow: 'browser',
    status,
    auth_url: null,
    verification_url: null,
    user_code: null,
    error,
    created_at: '2026-07-31T12:00:00Z',
    completed_at: status === 'pending' ? null : '2026-07-31T12:00:01Z',
  };
}

describe('getCodexLoginOutcome', () => {
  it.each(['pending', 'canceling'] as const)('keeps %s logins active', (status) => {
    expect(getCodexLoginOutcome(status)).toBe('active');
  });

  it('recognizes a successful login', () => {
    expect(getCodexLoginOutcome('succeeded')).toBe('succeeded');
  });

  it.each(['failed', 'expired'] as const)('stops polling for %s logins', (status) => {
    expect(getCodexLoginOutcome(status)).toBe('failed');
  });

  it('stops polling for canceled logins', () => {
    expect(getCodexLoginOutcome('canceled')).toBe('canceled');
  });
});

describe('getCodexLoginFailureMessage', () => {
  it('prefers the runtime error', () => {
    expect(getCodexLoginFailureMessage('failed', 'Authorization was denied.')).toBe(
      'Authorization was denied.'
    );
  });

  it('explains expiration when the runtime has no error', () => {
    expect(getCodexLoginFailureMessage('expired', null)).toBe(
      'The sign-in request expired before it completed.'
    );
  });
});

describe('getCodexLoginTransition', () => {
  it('keeps active polling state without replacing the current banner', () => {
    expect(getCodexLoginTransition(makeLogin('pending'), 'poll')).toMatchObject({
      outcome: 'active',
      keepLogin: true,
      refreshAccount: false,
      banner: null,
    });
  });

  it('describes a login that wins a cancellation race', () => {
    expect(getCodexLoginTransition(makeLogin('succeeded'), 'cancel')).toMatchObject({
      outcome: 'succeeded',
      keepLogin: false,
      refreshAccount: true,
      banner: {
        title: 'Codex sign-in completed before cancellation',
      },
      notification: {
        title: 'Codex sign-in complete',
      },
    });
  });

  it('centralizes terminal failure handling', () => {
    expect(
      getCodexLoginTransition(makeLogin('failed', 'Authorization was denied.'), 'poll')
    ).toMatchObject({
      outcome: 'failed',
      keepLogin: false,
      banner: {
        variant: 'destructive',
        description: 'Authorization was denied.',
      },
      notification: {
        persistent: true,
      },
    });
  });
});
