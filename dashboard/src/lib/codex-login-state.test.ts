import { describe, expect, it } from 'vitest';

import {
  getCodexLoginFailureMessage,
  getCodexLoginOutcome,
} from '@/lib/codex-login-state';

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
