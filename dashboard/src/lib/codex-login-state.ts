import type { CodexLoginStatus } from '@/types/codex';

export type CodexLoginOutcome = 'active' | 'succeeded' | 'failed' | 'canceled';

export function getCodexLoginOutcome(status: CodexLoginStatus): CodexLoginOutcome {
  switch (status) {
    case 'pending':
    case 'canceling':
      return 'active';
    case 'succeeded':
      return 'succeeded';
    case 'canceled':
      return 'canceled';
    case 'failed':
    case 'expired':
      return 'failed';
  }
}

export function getCodexLoginFailureMessage(
  status: CodexLoginStatus,
  error: string | null
): string {
  if (error) {
    return error;
  }
  if (status === 'expired') {
    return 'The sign-in request expired before it completed.';
  }
  return 'Codex sign-in did not complete.';
}
