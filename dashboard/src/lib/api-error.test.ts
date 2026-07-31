import { describe, expect, it } from 'vitest';

import { isApiErrorCode } from '@/lib/api';

describe('isApiErrorCode', () => {
  it('matches a structured backend error code', () => {
    expect(
      isApiErrorCode(
        {
          isAxiosError: true,
          response: {
            data: {
              code: 'codex_login_not_found',
              error: 'The login is no longer active.',
            },
          },
        },
        'codex_login_not_found'
      )
    ).toBe(true);
  });

  it('rejects ordinary errors and different codes', () => {
    expect(isApiErrorCode(new Error('offline'), 'codex_login_not_found')).toBe(false);
    expect(
      isApiErrorCode(
        {
          isAxiosError: true,
          response: { data: { code: 'different_error' } },
        },
        'codex_login_not_found'
      )
    ).toBe(false);
  });
});
