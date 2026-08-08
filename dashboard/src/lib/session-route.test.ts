import { describe, expect, it } from 'vitest';

import { isResumableStatus, runStatusLabel } from '@/lib/session-route';

describe('isResumableStatus', () => {
  it('allows interrupted runs but not successful runs', () => {
    expect(isResumableStatus('failed')).toBe(true);
    expect(isResumableStatus('cancelled')).toBe(true);
    expect(isResumableStatus('completed')).toBe(false);
    expect(isResumableStatus('running')).toBe(false);
  });
});

describe('runStatusLabel', () => {
  it('uses operator-facing lifecycle language', () => {
    expect(runStatusLabel('cancelled')).toBe('Stopped');
    expect(runStatusLabel('running')).toBe('Running');
    expect(runStatusLabel(null)).toBe('Loading');
  });
});
