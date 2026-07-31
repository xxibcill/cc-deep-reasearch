'use client';

import {
  startTransition,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react';

import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { AlertDialog } from '@/components/ui/alert-dialog';
import { Badge } from '@/components/ui/badge';
import { Button, buttonVariants } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { CheckboxRow, SettingFieldShell } from '@/components/ui/form-field';
import { Input } from '@/components/ui/input';
import { NativeSelect } from '@/components/ui/native-select';
import { useNotifications } from '@/components/ui/notification-center';
import {
  cancelCodexLogin,
  getApiErrorMessage,
  getActiveCodexLogin,
  getCodexAccount,
  getCodexLogin,
  getConfigUpdateErrorDetails,
  isApiErrorCode,
  logoutCodex,
  startCodexBrowserLogin,
  startCodexDeviceCodeLogin,
  updateConfig,
} from '@/lib/api';
import {
  getCodexLoginOutcome,
  getCodexLoginTransition,
  type CodexLoginAction,
} from '@/lib/codex-login-state';
import {
  clearCodexLoginRecovery,
  loadCodexLoginRecovery,
  loginResponseFromRecovery,
  rebaseCodexSettingsDraft,
  storeCodexLoginRecovery,
  type CodexReasoningEffort,
  type CodexSettingsDraft,
} from '@/lib/codex-provider-state';
import type { CodexAccountResponse, CodexLoginResponse } from '@/types/codex';
import type { ConfigResponse } from '@/types/config';

type CodexProviderPanelProps = {
  config: ConfigResponse;
  onConfigChange: (config: ConfigResponse) => void;
};

type BannerState = {
  variant: 'info' | 'warning' | 'success' | 'destructive';
  title: string;
  description: string;
} | null;

type AuthAction = 'browser' | 'device' | 'cancel' | 'logout' | null;

const CODEX_CONFIG_PATHS = [
  'llm.codex.enabled',
  'llm.codex.model',
  'llm.codex.reasoning_effort',
  'llm.codex.timeout_seconds',
] as const;
const REASONING_EFFORT_OPTIONS = ['minimal', 'low', 'medium', 'high', 'xhigh'] as const;
const LOGIN_POLL_INTERVAL_MS = 1_500;
const LOGIN_POLL_TIMEOUT_MS = 10 * 60 * 1_000;

function readPath(source: Record<string, unknown>, path: string): unknown {
  let current: unknown = source;
  for (const segment of path.split('.')) {
    if (!current || typeof current !== 'object' || !(segment in current)) {
      return undefined;
    }
    current = (current as Record<string, unknown>)[segment];
  }
  return current;
}

function normalizeReasoningEffort(value: unknown): CodexReasoningEffort {
  return REASONING_EFFORT_OPTIONS.includes(value as CodexReasoningEffort)
    ? (value as CodexReasoningEffort)
    : 'medium';
}

function settingsFromConfig(config: ConfigResponse): CodexSettingsDraft {
  const source = config.persisted_config;
  const model = readPath(source, 'llm.codex.model');
  const timeoutSeconds = readPath(source, 'llm.codex.timeout_seconds');

  return {
    enabled: readPath(source, 'llm.codex.enabled') === true,
    model: typeof model === 'string' ? model : '',
    reasoningEffort: normalizeReasoningEffort(
      readPath(source, 'llm.codex.reasoning_effort')
    ),
    timeoutSeconds:
      typeof timeoutSeconds === 'number' || typeof timeoutSeconds === 'string'
        ? String(timeoutSeconds)
        : '180',
  };
}

function getDirtyPaths(
  draft: CodexSettingsDraft,
  baseline: CodexSettingsDraft
): Array<(typeof CODEX_CONFIG_PATHS)[number]> {
  const paths: Array<(typeof CODEX_CONFIG_PATHS)[number]> = [];
  if (draft.enabled !== baseline.enabled) {
    paths.push('llm.codex.enabled');
  }
  if (draft.model.trim() !== baseline.model.trim()) {
    paths.push('llm.codex.model');
  }
  if (draft.reasoningEffort !== baseline.reasoningEffort) {
    paths.push('llm.codex.reasoning_effort');
  }
  if (draft.timeoutSeconds !== baseline.timeoutSeconds) {
    paths.push('llm.codex.timeout_seconds');
  }
  return paths;
}

function formatSettingValue(value: unknown): string {
  if (typeof value === 'boolean') {
    return value ? 'Enabled' : 'Disabled';
  }
  if (value === null || value === undefined || String(value).trim().length === 0) {
    return 'Runtime default';
  }
  return String(value);
}

function getRuntimeBadgeVariant(
  runtimeStatus: string | undefined
): 'success' | 'warning' | 'secondary' {
  if (runtimeStatus === 'ready') {
    return 'success';
  }
  if (runtimeStatus === 'starting' || runtimeStatus === 'closing') {
    return 'warning';
  }
  return 'secondary';
}

export function CodexProviderPanel({
  config,
  onConfigChange,
}: CodexProviderPanelProps) {
  const { notify } = useNotifications();
  const mountedRef = useRef(true);
  const loginStartedAtRef = useRef(0);
  const [baseline, setBaseline] = useState<CodexSettingsDraft>(() =>
    settingsFromConfig(config)
  );
  const baselineRef = useRef(baseline);
  const overriddenFields = useMemo(
    () => new Set(config.overridden_fields),
    [config.overridden_fields]
  );
  const [draft, setDraft] = useState<CodexSettingsDraft>(baseline);
  const [savingSettings, setSavingSettings] = useState(false);
  const [settingsBanner, setSettingsBanner] = useState<BannerState>(null);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [account, setAccount] = useState<CodexAccountResponse | null>(null);
  const [loadingAccount, setLoadingAccount] = useState(true);
  const [accountError, setAccountError] = useState<string | null>(null);
  const [login, setLogin] = useState<CodexLoginResponse | null>(null);
  const [polling, setPolling] = useState(false);
  const [authAction, setAuthAction] = useState<AuthAction>(null);
  const [authBanner, setAuthBanner] = useState<BannerState>(null);
  const [logoutOpen, setLogoutOpen] = useState(false);

  const dirtyPaths = getDirtyPaths(draft, baseline);
  const runtimeReady = account?.runtime_status === 'ready';
  const loginOutcome = login ? getCodexLoginOutcome(login.status) : null;
  const activeLoginId = login?.login_id ?? null;
  const codexRouteSelected = Object.values(
    (readPath(config.effective_config, 'llm.route_defaults') as Record<string, unknown>) ?? {}
  ).some((route) => route === 'codex');

  const resumeManagedLogin = useCallback(
    (
      activeLogin: CodexLoginResponse,
      title = 'Resuming Codex sign-in',
      description = 'Checking the managed runtime for the active sign-in request.'
    ): boolean => {
      if (!mountedRef.current || getCodexLoginOutcome(activeLogin.status) !== 'active') {
        return false;
      }
      const startedAt = Date.now();
      loginStartedAtRef.current = startedAt;
      storeCodexLoginRecovery(window.sessionStorage, {
        login_id: activeLogin.login_id,
        flow: activeLogin.flow,
        timestamp: startedAt,
      });
      setLogin(activeLogin);
      setPolling(true);
      setAuthBanner({
        variant: 'info',
        title,
        description,
      });
      return true;
    },
    []
  );

  useEffect(() => {
    const previousBaseline = baselineRef.current;
    const nextBaseline = settingsFromConfig(config);
    setDraft((current) =>
      rebaseCodexSettingsDraft(current, previousBaseline, nextBaseline)
    );
    baselineRef.current = nextBaseline;
    setBaseline(nextBaseline);
  }, [config]);

  const refreshAccount = useCallback(
    async (announceFailure: boolean) => {
      setLoadingAccount(true);
      setAccountError(null);

      try {
        const response = await getCodexAccount();
        if (!mountedRef.current) {
          return;
        }
        setAccount(response);
        if (response.error_message) {
          setAccountError(response.error_message);
        }
      } catch (error) {
        if (!mountedRef.current) {
          return;
        }
        const message = getApiErrorMessage(error, 'Failed to read the Codex account.');
        setAccount(null);
        setAccountError(message);
        if (announceFailure) {
          notify({
            variant: 'destructive',
            title: 'Codex account refresh failed',
            description: message,
          });
        }
      } finally {
        if (mountedRef.current) {
          setLoadingAccount(false);
        }
      }
    },
    [notify]
  );

  const applyLoginResponse = useCallback(
    async (response: CodexLoginResponse, action: CodexLoginAction) => {
      const transition = getCodexLoginTransition(response, action);
      if (transition.keepLogin) {
        const startedAt =
          action === 'poll' && loginStartedAtRef.current > 0
            ? loginStartedAtRef.current
            : Date.now();
        loginStartedAtRef.current = startedAt;
        storeCodexLoginRecovery(window.sessionStorage, {
          login_id: response.login_id,
          flow: response.flow,
          timestamp: startedAt,
        });
        setLogin(response);
        setPolling(true);
      } else {
        clearCodexLoginRecovery(window.sessionStorage);
        setLogin(null);
        setPolling(false);
      }
      if (transition.banner) {
        setAuthBanner(transition.banner);
      }
      if (transition.refreshAccount) {
        await refreshAccount(false);
      }
      if (transition.notification) {
        notify(transition.notification);
      }
      return transition.outcome;
    },
    [notify, refreshAccount]
  );

  const recoverMissingLogin = useCallback(async () => {
    clearCodexLoginRecovery(window.sessionStorage);
    setLogin(null);
    setPolling(false);
    try {
      const activeLogin = await getActiveCodexLogin();
      if (
        activeLogin &&
        resumeManagedLogin(
          activeLogin,
          'Active Codex sign-in recovered',
          'The previous request ended, but the managed runtime has another active sign-in.'
        )
      ) {
        return;
      }
    } catch {
      // The account refresh owns runtime availability reporting.
    }
    setAuthBanner({
      variant: 'warning',
      title: 'Previous Codex sign-in ended',
      description: 'The saved sign-in is no longer active. Start a new sign-in request.',
    });
  }, [resumeManagedLogin]);

  useEffect(() => {
    mountedRef.current = true;
    const recovery = loadCodexLoginRecovery(
      window.sessionStorage,
      Date.now(),
      LOGIN_POLL_TIMEOUT_MS
    );
    if (recovery) {
      loginStartedAtRef.current = recovery.timestamp;
      setLogin(loginResponseFromRecovery(recovery));
      setPolling(true);
      setAuthBanner({
        variant: 'info',
        title: 'Resuming Codex sign-in',
        description: 'Checking the managed runtime for the active sign-in request.',
      });
    } else {
      void getActiveCodexLogin()
        .then((activeLogin) => {
          if (activeLogin) {
            resumeManagedLogin(activeLogin);
          }
        })
        .catch(() => {
          // The account refresh below owns initial runtime error reporting.
        });
    }
    void refreshAccount(false);

    return () => {
      mountedRef.current = false;
    };
  }, [refreshAccount, resumeManagedLogin]);

  useEffect(() => {
    if (!activeLoginId || !polling) {
      return;
    }

    let stopped = false;
    let timerId: number | null = null;

    const stopWithBanner = (banner: NonNullable<BannerState>) => {
      if (stopped) {
        return;
      }
      setPolling(false);
      setAuthBanner(banner);
    };

    const poll = async () => {
      if (Date.now() - loginStartedAtRef.current >= LOGIN_POLL_TIMEOUT_MS) {
        clearCodexLoginRecovery(window.sessionStorage);
        stopWithBanner({
          variant: 'warning',
          title: 'Status checks paused',
          description:
            'This page stopped checking after 10 minutes. Resume checks or cancel the sign-in request.',
        });
        return;
      }

      try {
        const response = await getCodexLogin(activeLoginId);
        if (stopped) {
          return;
        }
        const outcome = await applyLoginResponse(response, 'poll');
        if (outcome === 'active') {
          timerId = window.setTimeout(poll, LOGIN_POLL_INTERVAL_MS);
        }
      } catch (error) {
        if (stopped) {
          return;
        }
        if (isApiErrorCode(error, 'codex_login_not_found')) {
          await recoverMissingLogin();
          return;
        }
        stopWithBanner({
          variant: 'warning',
          title: 'Status checks paused',
          description: getApiErrorMessage(
            error,
            'The dashboard could not check the Codex sign-in status.'
          ),
        });
      }
    };

    timerId = window.setTimeout(poll, LOGIN_POLL_INTERVAL_MS);

    return () => {
      stopped = true;
      if (timerId !== null) {
        window.clearTimeout(timerId);
      }
    };
  }, [activeLoginId, applyLoginResponse, polling, recoverMissingLogin]);

  const handleSettingsSave = async () => {
    const writablePaths = dirtyPaths.filter((path) => !overriddenFields.has(path));
    if (writablePaths.length === 0) {
      return;
    }

    const updates: Record<string, unknown> = {};
    for (const path of writablePaths) {
      if (path === 'llm.codex.enabled') {
        updates[path] = draft.enabled;
      } else if (path === 'llm.codex.model') {
        updates[path] = draft.model.trim() || null;
      } else if (path === 'llm.codex.reasoning_effort') {
        updates[path] = draft.reasoningEffort;
      } else {
        updates[path] = Number(draft.timeoutSeconds);
      }
    }

    setSavingSettings(true);
    setSettingsBanner(null);
    setFieldErrors({});

    try {
      const response = await updateConfig({ updates });
      const previousBaseline = baselineRef.current;
      const nextBaseline = settingsFromConfig(response);
      startTransition(() => {
        onConfigChange(response);
        setDraft((current) =>
          rebaseCodexSettingsDraft(current, previousBaseline, nextBaseline)
        );
        baselineRef.current = nextBaseline;
        setBaseline(nextBaseline);
        setSettingsBanner({
          variant: 'success',
          title: 'Codex settings saved',
          description: `Saved ${writablePaths.length} Codex ${writablePaths.length === 1 ? 'setting' : 'settings'} for future runs.`,
        });
      });
      notify({
        variant: 'success',
        title: 'Codex settings saved',
        description: 'Future Codex-routed runs will use the updated provider settings.',
      });
    } catch (error) {
      const details = getConfigUpdateErrorDetails(error);
      const nextFieldErrors: Record<string, string> = {};
      for (const item of details.fields) {
        nextFieldErrors[item.field] = item.message;
      }
      for (const item of details.conflicts) {
        nextFieldErrors[item.field] = `${item.message} (${item.env_vars.join(', ')})`;
      }
      setFieldErrors(nextFieldErrors);
      setSettingsBanner({
        variant: 'destructive',
        title: 'Codex settings failed to save',
        description: details.message,
      });
      notify({
        variant: 'destructive',
        persistent: true,
        title: 'Codex settings failed to save',
        description: details.message,
      });
    } finally {
      setSavingSettings(false);
    }
  };

  const startLogin = async (flow: 'browser' | 'device') => {
    setAuthAction(flow);
    setAuthBanner(null);

    try {
      const response =
        flow === 'browser'
          ? await startCodexBrowserLogin()
          : await startCodexDeviceCodeLogin();
      await applyLoginResponse(response, flow);
    } catch (error) {
      try {
        const activeLogin = await getActiveCodexLogin();
        if (
          activeLogin &&
          resumeManagedLogin(
            activeLogin,
            'Existing Codex sign-in resumed',
            'Another sign-in request is already active. This page will continue checking it.'
          )
        ) {
          return;
        }
      } catch {
        // Preserve the original login-start error below.
      }
      const message = getApiErrorMessage(error, 'Failed to start Codex sign-in.');
      setAuthBanner({
        variant: 'destructive',
        title: 'Could not start Codex sign-in',
        description: message,
      });
      notify({
        variant: 'destructive',
        persistent: true,
        title: 'Could not start Codex sign-in',
        description: message,
      });
    } finally {
      setAuthAction(null);
    }
  };

  const handleCancelLogin = async () => {
    if (!login) {
      return;
    }

    setAuthAction('cancel');
    setPolling(false);
    try {
      const response = await cancelCodexLogin(login.login_id);
      await applyLoginResponse(response, 'cancel');
    } catch (error) {
      if (isApiErrorCode(error, 'codex_login_not_found')) {
        await recoverMissingLogin();
        return;
      }
      const message = getApiErrorMessage(error, 'Failed to cancel Codex sign-in.');
      setAuthBanner({
        variant: 'destructive',
        title: 'Could not cancel Codex sign-in',
        description: message,
      });
      notify({
        variant: 'destructive',
        title: 'Could not cancel Codex sign-in',
        description: message,
      });
    } finally {
      setAuthAction(null);
    }
  };

  const handleLogout = async () => {
    setAuthAction('logout');
    setAuthBanner(null);

    try {
      const response = await logoutCodex();
      setAccount(response);
      clearCodexLoginRecovery(window.sessionStorage);
      setLogin(null);
      setPolling(false);
      setLogoutOpen(false);
      setAuthBanner({
        variant: 'success',
        title: 'Signed out of Codex',
        description: 'The managed ChatGPT session was removed from the Codex runtime.',
      });
      notify({
        variant: 'success',
        title: 'Signed out of Codex',
        description: 'Codex authentication has been cleared.',
      });
    } catch (error) {
      const message = getApiErrorMessage(error, 'Failed to sign out of Codex.');
      setAuthBanner({
        variant: 'destructive',
        title: 'Codex sign-out failed',
        description: message,
      });
      notify({
        variant: 'destructive',
        persistent: true,
        title: 'Codex sign-out failed',
        description: message,
      });
    } finally {
      setAuthAction(null);
    }
  };

  const copyUserCode = async () => {
    if (!login?.user_code) {
      return;
    }
    try {
      await navigator.clipboard.writeText(login.user_code);
      notify({
        variant: 'success',
        title: 'Device code copied',
        description: 'Paste it into the ChatGPT verification page.',
      });
    } catch (error) {
      notify({
        variant: 'destructive',
        title: 'Could not copy the device code',
        description: getApiErrorMessage(error, 'Copy the code manually instead.'),
      });
    }
  };

  const resumePolling = () => {
    const startedAt = Date.now();
    loginStartedAtRef.current = startedAt;
    if (login) {
      storeCodexLoginRecovery(window.sessionStorage, {
        login_id: login.login_id,
        flow: login.flow,
        timestamp: startedAt,
      });
    }
    setAuthBanner({
      variant: 'info',
      title: 'Status checks resumed',
      description: 'Waiting for the managed runtime to finish sign-in.',
    });
    setPolling(true);
  };

  return (
    <>
      <Card className="border-border/80 bg-card/95">
        <CardHeader className="space-y-2">
          <div className="flex flex-wrap items-center gap-2">
            <CardTitle className="text-base">Codex provider</CardTitle>
            <Badge variant={draft.enabled ? 'success' : 'secondary'}>
              {draft.enabled ? 'Enabled' : 'Disabled'}
            </Badge>
            <Badge variant={account?.authenticated ? 'success' : 'outline'}>
              {account?.authenticated ? 'Authenticated' : 'Signed out'}
            </Badge>
            <Badge variant={getRuntimeBadgeVariant(account?.runtime_status)}>
              Runtime {account?.runtime_status ?? 'unknown'}
            </Badge>
          </div>
          <CardDescription>
            Route work through the managed Codex app-server and authenticate with ChatGPT. Account
            credentials stay in the runtime and are never exposed as dashboard secret fields.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-5">
          <section className="space-y-4" aria-labelledby="codex-provider-settings-title">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <h3 id="codex-provider-settings-title" className="text-sm font-semibold">
                  Provider settings
                </h3>
                <p className="mt-1 text-sm text-muted-foreground">
                  Saved values apply to future runs that select the codex route.
                </p>
              </div>
              <Badge variant={dirtyPaths.length > 0 ? 'info' : 'secondary'}>
                {dirtyPaths.length > 0 ? `${dirtyPaths.length} unsaved` : 'Saved'}
              </Badge>
            </div>

            {codexRouteSelected && !baseline.enabled ? (
              <Alert variant="warning">
                <AlertTitle>Codex is selected but disabled</AlertTitle>
                <AlertDescription>
                  At least one effective agent route points to codex. Enable this provider before
                  starting a new run.
                </AlertDescription>
              </Alert>
            ) : null}

            {settingsBanner ? (
              <Alert variant={settingsBanner.variant}>
                <AlertTitle>{settingsBanner.title}</AlertTitle>
                <AlertDescription>{settingsBanner.description}</AlertDescription>
              </Alert>
            ) : null}

            <div className="grid gap-4 sm:grid-cols-2">
              <SettingFieldShell
                label="Enable Codex"
                description="Allow the codex route to dispatch requests through app-server."
                error={fieldErrors['llm.codex.enabled']}
                overridden={overriddenFields.has('llm.codex.enabled')}
                dirty={dirtyPaths.includes('llm.codex.enabled')}
                draftValue={formatSettingValue(draft.enabled)}
                effectiveValue={formatSettingValue(
                  readPath(config.effective_config, 'llm.codex.enabled')
                )}
                persistedValue={formatSettingValue(
                  readPath(config.persisted_config, 'llm.codex.enabled')
                )}
                overrideSource={config.override_sources['llm.codex.enabled']}
              >
                <CheckboxRow
                  id="config-codex-enabled"
                  checked={draft.enabled}
                  disabled={savingSettings || overriddenFields.has('llm.codex.enabled')}
                  label="Enable the Codex provider"
                  onCheckedChange={(enabled) =>
                    setDraft((current) => ({ ...current, enabled }))
                  }
                />
              </SettingFieldShell>

              <SettingFieldShell
                label="Model"
                description="Leave blank to use the authenticated Codex runtime default."
                error={fieldErrors['llm.codex.model']}
                overridden={overriddenFields.has('llm.codex.model')}
                dirty={dirtyPaths.includes('llm.codex.model')}
                draftValue={formatSettingValue(draft.model)}
                effectiveValue={formatSettingValue(
                  readPath(config.effective_config, 'llm.codex.model')
                )}
                persistedValue={formatSettingValue(
                  readPath(config.persisted_config, 'llm.codex.model')
                )}
                overrideSource={config.override_sources['llm.codex.model']}
              >
                <Input
                  aria-label="Codex model"
                  value={draft.model}
                  placeholder="Runtime default"
                  disabled={savingSettings || overriddenFields.has('llm.codex.model')}
                  onChange={(event) =>
                    setDraft((current) => ({ ...current, model: event.target.value }))
                  }
                />
              </SettingFieldShell>

              <SettingFieldShell
                label="Reasoning effort"
                description="Choose how much reasoning the Codex model should use."
                error={fieldErrors['llm.codex.reasoning_effort']}
                overridden={overriddenFields.has('llm.codex.reasoning_effort')}
                dirty={dirtyPaths.includes('llm.codex.reasoning_effort')}
                draftValue={formatSettingValue(draft.reasoningEffort)}
                effectiveValue={formatSettingValue(
                  readPath(config.effective_config, 'llm.codex.reasoning_effort')
                )}
                persistedValue={formatSettingValue(
                  readPath(config.persisted_config, 'llm.codex.reasoning_effort')
                )}
                overrideSource={config.override_sources['llm.codex.reasoning_effort']}
              >
                <NativeSelect
                  aria-label="Codex reasoning effort"
                  value={draft.reasoningEffort}
                  disabled={
                    savingSettings || overriddenFields.has('llm.codex.reasoning_effort')
                  }
                  onChange={(event) =>
                    setDraft((current) => ({
                      ...current,
                      reasoningEffort: normalizeReasoningEffort(event.target.value),
                    }))
                  }
                >
                  {REASONING_EFFORT_OPTIONS.map((effort) => (
                    <option key={effort} value={effort}>
                      {effort}
                    </option>
                  ))}
                </NativeSelect>
              </SettingFieldShell>

              <SettingFieldShell
                label="Request timeout"
                description="Seconds to wait for a Codex response, from 30 to 900."
                error={fieldErrors['llm.codex.timeout_seconds']}
                overridden={overriddenFields.has('llm.codex.timeout_seconds')}
                dirty={dirtyPaths.includes('llm.codex.timeout_seconds')}
                draftValue={formatSettingValue(draft.timeoutSeconds)}
                effectiveValue={formatSettingValue(
                  readPath(config.effective_config, 'llm.codex.timeout_seconds')
                )}
                persistedValue={formatSettingValue(
                  readPath(config.persisted_config, 'llm.codex.timeout_seconds')
                )}
                overrideSource={config.override_sources['llm.codex.timeout_seconds']}
              >
                <Input
                  aria-label="Codex request timeout in seconds"
                  type="number"
                  min={30}
                  max={900}
                  value={draft.timeoutSeconds}
                  disabled={
                    savingSettings || overriddenFields.has('llm.codex.timeout_seconds')
                  }
                  onChange={(event) =>
                    setDraft((current) => ({
                      ...current,
                      timeoutSeconds: event.target.value,
                    }))
                  }
                />
              </SettingFieldShell>
            </div>

            <div className="flex flex-wrap justify-end gap-2">
              <Button
                type="button"
                variant="outline"
                size="sm"
                disabled={savingSettings || dirtyPaths.length === 0}
                onClick={() => {
                  setDraft(baseline);
                  setFieldErrors({});
                  setSettingsBanner(null);
                }}
              >
                Reset Codex settings
              </Button>
              <Button
                type="button"
                size="sm"
                disabled={
                  savingSettings ||
                  dirtyPaths.length === 0 ||
                  dirtyPaths.every((path) => overriddenFields.has(path))
                }
                onClick={handleSettingsSave}
              >
                {savingSettings ? 'Saving…' : 'Save Codex settings'}
              </Button>
            </div>
          </section>

          <section
            className="space-y-4 border-t border-border pt-5"
            aria-labelledby="codex-account-title"
          >
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <h3 id="codex-account-title" className="text-sm font-semibold">
                  Managed ChatGPT account
                </h3>
                <p className="mt-1 text-sm text-muted-foreground">
                  Sign in through app-server. No API key or account token is stored in project
                  configuration.
                </p>
              </div>
              <Button
                type="button"
                size="sm"
                variant="outline"
                disabled={loadingAccount || authAction !== null}
                onClick={() => void refreshAccount(true)}
              >
                {loadingAccount ? 'Checking…' : 'Refresh account'}
              </Button>
            </div>

            {authBanner ? (
              <Alert variant={authBanner.variant}>
                <AlertTitle>{authBanner.title}</AlertTitle>
                <AlertDescription>{authBanner.description}</AlertDescription>
              </Alert>
            ) : null}

            {accountError ? (
              <Alert variant="destructive">
                <AlertTitle>Codex runtime unavailable</AlertTitle>
                <AlertDescription>{accountError}</AlertDescription>
              </Alert>
            ) : loadingAccount && !account ? (
              <Alert>
                <AlertTitle>Checking Codex account</AlertTitle>
                <AlertDescription>
                  Reading the managed runtime status and current account.
                </AlertDescription>
              </Alert>
            ) : account?.authenticated ? (
              <Alert variant="success">
                <AlertTitle>ChatGPT account connected</AlertTitle>
                <AlertDescription>
                  {account.email ?? 'The managed Codex account'} is authenticated
                  {account.plan_type ? ` on the ${account.plan_type} plan` : ''}. Account type:{' '}
                  {account.account_type ?? 'chatgpt'}.
                </AlertDescription>
              </Alert>
            ) : (
              <Alert variant={runtimeReady ? 'warning' : 'default'}>
                <AlertTitle>
                  {runtimeReady ? 'ChatGPT sign-in required' : 'Codex runtime is not ready'}
                </AlertTitle>
                <AlertDescription>
                  {runtimeReady
                    ? 'Choose browser or device-code sign-in before using authenticated Codex routes.'
                    : `Current runtime status: ${account?.runtime_status ?? 'unknown'}. Start or repair the local app-server, then refresh this account.`}
                </AlertDescription>
              </Alert>
            )}

            {login ? (
              <div
                className="space-y-4 rounded-2xl border border-primary/30 bg-primary/8 p-4"
                aria-live="polite"
              >
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <div className="font-medium">
                      {login.flow === 'browser' ? 'Browser sign-in' : 'Device-code sign-in'}
                    </div>
                    <p className="mt-1 text-sm text-muted-foreground">
                      Status: {login.status}. Keep this page open while sign-in completes.
                    </p>
                  </div>
                  <Badge variant={polling ? 'info' : 'warning'}>
                    {polling ? 'Checking status' : 'Checks paused'}
                  </Badge>
                </div>

                {login.auth_url ? (
                  <a
                    className={buttonVariants({ variant: 'default', size: 'sm' })}
                    href={login.auth_url}
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    Open ChatGPT sign-in
                  </a>
                ) : null}

                {login.verification_url ? (
                  <div className="space-y-3 rounded-xl border border-border bg-background/80 p-3">
                    {login.user_code ? (
                      <div>
                        <div className="text-xs uppercase tracking-[0.18em] text-muted-foreground">
                          Device code
                        </div>
                        <code className="mt-2 block break-all text-lg font-semibold tracking-[0.16em]">
                          {login.user_code}
                        </code>
                      </div>
                    ) : null}
                    <div className="flex flex-wrap gap-2">
                      <a
                        className={buttonVariants({ variant: 'default', size: 'sm' })}
                        href={login.verification_url}
                        target="_blank"
                        rel="noopener noreferrer"
                      >
                        Open verification page
                      </a>
                      {login.user_code ? (
                        <Button type="button" size="sm" variant="outline" onClick={copyUserCode}>
                          Copy device code
                        </Button>
                      ) : null}
                    </div>
                  </div>
                ) : null}

                <div className="flex flex-wrap gap-2">
                  {!polling && loginOutcome === 'active' ? (
                    <Button type="button" size="sm" variant="outline" onClick={resumePolling}>
                      Resume status checks
                    </Button>
                  ) : null}
                  <Button
                    type="button"
                    size="sm"
                    variant="outline"
                    disabled={authAction !== null}
                    onClick={handleCancelLogin}
                  >
                    {authAction === 'cancel' ? 'Canceling…' : 'Cancel sign-in'}
                  </Button>
                </div>
              </div>
            ) : null}

            <div className="flex flex-wrap gap-2">
              {account?.authenticated ? (
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  className="text-destructive"
                  disabled={authAction !== null}
                  onClick={() => setLogoutOpen(true)}
                >
                  Sign out
                </Button>
              ) : (
                <>
                  <Button
                    type="button"
                    size="sm"
                    disabled={!runtimeReady || authAction !== null || login !== null}
                    onClick={() => void startLogin('browser')}
                  >
                    {authAction === 'browser' ? 'Starting…' : 'Sign in with browser'}
                  </Button>
                  <Button
                    type="button"
                    size="sm"
                    variant="outline"
                    disabled={!runtimeReady || authAction !== null || login !== null}
                    onClick={() => void startLogin('device')}
                  >
                    {authAction === 'device' ? 'Starting…' : 'Use device code'}
                  </Button>
                </>
              )}
            </div>
          </section>
        </CardContent>
      </Card>

      <AlertDialog
        open={logoutOpen}
        onOpenChange={setLogoutOpen}
        title="Sign out of Codex?"
        description="This clears the managed ChatGPT session from the local Codex runtime. Saved provider settings and route selections are not changed."
        confirmLabel="Sign out"
        destructive
        loading={authAction === 'logout'}
        loadingLabel="Signing out…"
        onConfirm={handleLogout}
      />
    </>
  );
}
