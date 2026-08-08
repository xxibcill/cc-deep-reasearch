import { describe, expect, it } from 'vitest';

import { isResumableStatus } from '@/lib/session-route';

describe('isResumableStatus', () => {
  it('allows interrupted runs but not successful runs', () => {
    expect(isResumableStatus('failed')).toBe(true);
    expect(isResumableStatus('cancelled')).toBe(true);
    expect(isResumableStatus('completed')).toBe(false);
    expect(isResumableStatus('running')).toBe(false);
  });
});
