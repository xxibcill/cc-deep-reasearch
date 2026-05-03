import { describe, it, expect, vi, beforeEach } from 'vitest';
import { CONTENT_GEN_TIMEOUT_MS, SCRIPTING_TIMEOUT_MS } from './client';

// We import contentGenClient to verify it's configured correctly
import { contentGenClient, getContentGenErrorMessage } from './client';

describe('content-gen client', () => {
  describe('configuration', () => {
    it('has correct timeout for regular requests', () => {
      expect(CONTENT_GEN_TIMEOUT_MS).toBe(30000);
    });

    it('has extended timeout for scripting operations', () => {
      expect(SCRIPTING_TIMEOUT_MS).toBe(240000);
    });

    it('client has correct baseURL pattern', () => {
      expect(contentGenClient.defaults.baseURL).toMatch(/\/content-gen$/);
    });

    it('client has correct default timeout', () => {
      expect(contentGenClient.defaults.timeout).toBe(CONTENT_GEN_TIMEOUT_MS);
    });
  });

  describe('getContentGenErrorMessage', () => {
    it('returns fallback for non-Error objects', () => {
      const result = getContentGenErrorMessage('not an error', 'Fallback message');
      expect(result).toBe('Fallback message');
    });

    it('returns fallback for Error without message', () => {
      const result = getContentGenErrorMessage(new Error(), 'Fallback');
      expect(result).toBe('Fallback');
    });

    it('returns error message when available', () => {
      const result = getContentGenErrorMessage(
        new Error('API Error'),
        'Fallback'
      );
      expect(result).toBe('API Error');
    });
  });
});