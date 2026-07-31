import type { CodexLoginResponse, CodexLoginStatus } from '@/types/codex';

export type CodexLoginOutcome = 'active' | 'succeeded' | 'failed' | 'canceled';
export type CodexLoginAction = 'poll' | 'browser' | 'device' | 'cancel';
export type CodexLoginBanner = {
  variant: 'info' | 'success' | 'destructive';
  title: string;
  description: string;
};
export type CodexLoginNotification = CodexLoginBanner & {
  persistent?: boolean;
};
export type CodexLoginTransition = {
  outcome: CodexLoginOutcome;
  keepLogin: boolean;
  refreshAccount: boolean;
  banner: CodexLoginBanner | null;
  notification: CodexLoginNotification | null;
};

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

export function getCodexLoginTransition(
  login: CodexLoginResponse,
  action: CodexLoginAction
): CodexLoginTransition {
  const outcome = getCodexLoginOutcome(login.status);
  if (outcome === 'active') {
    const banner =
      action === 'poll'
        ? null
        : {
            variant: 'info' as const,
            title:
              action === 'cancel'
                ? 'Canceling Codex sign-in'
                : action === 'browser'
                  ? 'Browser sign-in started'
                  : 'Device sign-in started',
            description:
              action === 'cancel'
                ? 'Waiting for the managed runtime to finish canceling the request.'
                : 'Complete the ChatGPT sign-in outside this dashboard. This page will update automatically.',
          };
    return {
      outcome,
      keepLogin: true,
      refreshAccount: false,
      banner,
      notification: null,
    };
  }

  if (outcome === 'succeeded') {
    const wonCancellationRace = action === 'cancel';
    return {
      outcome,
      keepLogin: false,
      refreshAccount: true,
      banner: {
        variant: 'success',
        title: wonCancellationRace
          ? 'Codex sign-in completed before cancellation'
          : 'Signed in to Codex',
        description: wonCancellationRace
          ? 'The managed ChatGPT account finished connecting before the cancel request arrived.'
          : 'The managed ChatGPT account is ready for future Codex-routed runs.',
      },
      notification:
        action === 'poll' || wonCancellationRace
          ? {
              variant: 'success',
              title: 'Codex sign-in complete',
              description: wonCancellationRace
                ? 'The managed ChatGPT account connected before cancellation.'
                : 'The Codex provider can now use the managed ChatGPT account.',
            }
          : null,
    };
  }

  if (outcome === 'failed') {
    const description = getCodexLoginFailureMessage(login.status, login.error);
    return {
      outcome,
      keepLogin: false,
      refreshAccount: false,
      banner: {
        variant: 'destructive',
        title: 'Codex sign-in failed',
        description,
      },
      notification:
        action === 'poll' || action === 'cancel'
          ? {
              variant: 'destructive',
              persistent: true,
              title: 'Codex sign-in failed',
              description,
            }
          : null,
    };
  }

  return {
    outcome,
    keepLogin: false,
    refreshAccount: false,
    banner: {
      variant: 'info',
      title: 'Codex sign-in canceled',
      description: 'No account changes were made.',
    },
    notification: null,
  };
}
