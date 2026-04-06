'use client';

import { startTransition, useMemo, useState } from 'react';

import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { AlertDialog } from '@/components/ui/alert-dialog';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { getConfigUpdateErrorDetails, updateConfig } from '@/lib/api';
import type { ConfigResponse } from '@/types/config';

type ConfigSecretsPanelProps = {
  config: ConfigResponse;
  onConfigChange: (config: ConfigResponse) => void;
};

type BannerState = {
  variant: 'success' | 'destructive';
  title: string;
  description: string;
} | null;

const MULTI_VALUE_SUFFIX = '.api_keys';
const SECRET_FIELD_LABELS: Record<string, string> = {
  'tavily.api_keys': 'Tavily API keys',
  'llm.openrouter.api_key': 'OpenRouter API key',
  'llm.openrouter.api_keys': 'OpenRouter API keys',
  'llm.cerebras.api_key': 'Cerebras API key',
  'llm.cerebras.api_keys': 'Cerebras API keys',
  'llm.anthropic.api_key': 'Anthropic API key',
  'llm.anthropic.api_keys': 'Anthropic API keys',
};

function isMultiValueSecret(field: string): boolean {
  return field.endsWith(MULTI_VALUE_SUFFIX);
}

function getSecretFieldLabel(field: string): string {
  const mapped = SECRET_FIELD_LABELS[field];
  if (mapped) {
    return mapped;
  }
  return field
    .split('.')
    .map((segment) => segment.replaceAll('_', ' '))
    .map((segment) => segment.charAt(0).toUpperCase() + segment.slice(1))
    .join(' / ');
}

function formatPresence(present: boolean, count: number, fallback: string): string {
  if (!present) {
    return fallback;
  }
  return `${count} ${count === 1 ? 'value' : 'values'}`;
}

export function ConfigSecretsPanel({
  config,
  onConfigChange,
}: ConfigSecretsPanelProps) {
  const overriddenFields = useMemo(
    () => new Set(config.overridden_fields),
    [config.overridden_fields]
  );
  const [editingField, setEditingField] = useState<string | null>(null);
  const [draftValue, setDraftValue] = useState('');
  const [banner, setBanner] = useState<BannerState>(null);
  const [savingField, setSavingField] = useState<string | null>(null);
  const [clearField, setClearField] = useState<string | null>(null);

  const activeField = config.secret_fields.find((field) => field.field === editingField) ?? null;
  const clearTarget = config.secret_fields.find((field) => field.field === clearField) ?? null;
  const persistedSecretCount = config.secret_fields.filter((field) => field.persisted_present).length;
  const runtimeSecretCount = config.secret_fields.filter((field) => field.effective_present).length;
  const overriddenSecretCount = config.secret_fields.filter((field) =>
    overriddenFields.has(field.field)
  ).length;

  const beginReplace = (field: string) => {
    setEditingField(field);
    setDraftValue('');
    setBanner(null);
  };

  const cancelReplace = () => {
    setEditingField(null);
    setDraftValue('');
  };

  const submitReplace = async () => {
    if (!activeField) {
      return;
    }

    const multiValue = isMultiValueSecret(activeField.field);
    const normalizedValue = multiValue
      ? draftValue
          .split(/\r?\n/)
          .map((value) => value.trim())
          .filter(Boolean)
      : draftValue.trim();

    if ((multiValue && normalizedValue.length === 0) || (!multiValue && normalizedValue.length === 0)) {
      setBanner({
        variant: 'destructive',
        title: 'Secret update blocked',
        description: multiValue
          ? 'Provide at least one secret value before saving.'
          : 'Provide a replacement value before saving.',
      });
      return;
    }

    setSavingField(activeField.field);
    setBanner(null);

    try {
      const response = await updateConfig({
        updates: {
          [activeField.field]: {
            action: 'replace',
            value: normalizedValue,
          },
        },
      });
      startTransition(() => {
        onConfigChange(response);
        setEditingField(null);
        setDraftValue('');
        setBanner({
          variant: 'success',
          title: 'Secret saved',
          description: `${getSecretFieldLabel(activeField.field)} was updated in the persisted config. Future runs will use it.`,
        });
      });
    } catch (updateError) {
      const details = getConfigUpdateErrorDetails(updateError);
      setBanner({
        variant: 'destructive',
        title: 'Secret update failed',
        description: details.message,
      });
    } finally {
      setSavingField(null);
    }
  };

  const confirmClear = async () => {
    if (!clearTarget) {
      return;
    }

    setSavingField(clearTarget.field);
    setBanner(null);

    try {
      const response = await updateConfig({
        updates: {
          [clearTarget.field]: {
            action: 'clear',
          },
        },
      });
      startTransition(() => {
        onConfigChange(response);
        setClearField(null);
        setEditingField((current) => (current === clearTarget.field ? null : current));
        setDraftValue('');
        setBanner({
          variant: 'success',
          title: 'Secret cleared',
          description: `${getSecretFieldLabel(clearTarget.field)} was removed from the persisted config. Future runs will no longer load it from saved settings.`,
        });
      });
    } catch (updateError) {
      const details = getConfigUpdateErrorDetails(updateError);
      setBanner({
        variant: 'destructive',
        title: 'Secret clear failed',
        description: details.message,
      });
      setClearField(null);
    } finally {
      setSavingField(null);
    }
  };

  return (
    <>
      <Card className="border-border/80 bg-card/95">
        <CardHeader className="space-y-2">
          <div className="flex flex-wrap items-center gap-2">
            <CardTitle className="text-base">Secrets</CardTitle>
            <Badge variant="info">Persisted config only</Badge>
            <Badge variant="secondary">Future runs</Badge>
          </div>
          <CardDescription>
            Secret values stay masked in the browser. Replace and clear actions use the same saved-versus-runtime model as the rest of settings.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-3 md:grid-cols-3">
            <SecretSummaryTile
              eyebrow="Saved config"
              title={`${persistedSecretCount}/${config.secret_fields.length} configured`}
              description="Saved secrets are available to future runs when no env value shadows them."
            />
            <SecretSummaryTile
              eyebrow="Runtime now"
              title={`${runtimeSecretCount}/${config.secret_fields.length} active`}
              description="Runtime can still have a secret even when nothing is stored in the persisted config."
            />
            <SecretSummaryTile
              eyebrow="Overrides"
              title={
                overriddenSecretCount > 0
                  ? `${overriddenSecretCount} env-shadowed`
                  : 'No active secret overrides'
              }
              description={
                overriddenSecretCount > 0
                  ? 'Shadowed secret fields stay read-only here until the environment changes.'
                  : 'Every secret field here can be replaced or cleared from saved config.'
              }
            />
          </div>

          {banner ? (
            <Alert variant={banner.variant} className="py-2.5">
              <AlertTitle>{banner.title}</AlertTitle>
              <AlertDescription>{banner.description}</AlertDescription>
            </Alert>
          ) : (
            <Alert variant="default" className="py-2.5">
              <AlertTitle>Secret impact</AlertTitle>
              <AlertDescription>
                Secret edits never reveal the current value. Saving here only updates the persisted config used by future runs.
              </AlertDescription>
            </Alert>
          )}

          <div className="space-y-3">
            {config.secret_fields.map((field) => {
              const multiValue = isMultiValueSecret(field.field);
              const overridden = overriddenFields.has(field.field);
              const isEditing = editingField === field.field;
              const isSaving = savingField === field.field;
              const overrideSources = config.override_sources[field.field] ?? [];

              return (
                <div
                  key={field.field}
                  className="rounded-2xl border border-border bg-background px-4 py-4"
                >
                  <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                    <div className="space-y-2">
                      <div className="flex flex-wrap items-center gap-2">
                        <div className="font-medium">{getSecretFieldLabel(field.field)}</div>
                        <Badge variant="outline">{multiValue ? 'Multi-value' : 'Single value'}</Badge>
                        {overridden ? <Badge variant="warning">Runtime override</Badge> : null}
                      </div>
                      <div className="text-xs text-muted-foreground break-all">{field.field}</div>
                    </div>

                    <div className="flex shrink-0 gap-2">
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        disabled={overridden || isSaving}
                        onClick={() => beginReplace(field.field)}
                      >
                        Replace
                      </Button>
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        className="text-destructive hover:bg-destructive hover:text-white"
                        disabled={overridden || isSaving || !field.persisted_present}
                        onClick={() => setClearField(field.field)}
                      >
                        Clear
                      </Button>
                    </div>
                  </div>

                  <div className="mt-4 grid gap-3 md:grid-cols-3">
                    <SecretStatusCard
                      label="Saved config"
                      value={formatPresence(field.persisted_present, field.persisted_count, 'Not configured')}
                      tone="default"
                    />
                    <SecretStatusCard
                      label="Runtime now"
                      value={formatPresence(field.effective_present, field.effective_count, 'Not active')}
                      tone={overridden ? 'warning' : 'default'}
                    />
                    <SecretStatusCard
                      label="Effect"
                      value={
                        overridden
                          ? `Read-only while ${overrideSources.join(', ') || 'the environment'} stays active.`
                          : 'Replace or clear updates the persisted config for future runs.'
                      }
                      tone={overridden ? 'warning' : 'default'}
                    />
                  </div>

                  {isEditing ? (
                    <div className="mt-4 space-y-3 rounded-xl border border-border bg-card p-3">
                      <div className="space-y-1">
                        <label className="block text-sm font-medium" htmlFor={`secret-${field.field}`}>
                          {multiValue ? 'One secret per line' : 'Replacement value'}
                        </label>
                        <p className="text-xs text-muted-foreground">
                          Saving updates the persisted config only. Runtime env overrides still win until removed.
                        </p>
                      </div>
                      {multiValue ? (
                        <Textarea
                          id={`secret-${field.field}`}
                          className="min-h-[120px]"
                          disabled={isSaving}
                          value={draftValue}
                          onChange={(event) => setDraftValue(event.target.value)}
                          placeholder="Paste each key on its own line"
                        />
                      ) : (
                        <Input
                          id={`secret-${field.field}`}
                          type="password"
                          disabled={isSaving}
                          value={draftValue}
                          onChange={(event) => setDraftValue(event.target.value)}
                          placeholder="Enter a replacement value"
                        />
                      )}
                      <div className="flex gap-2">
                        <Button
                          type="button"
                          size="sm"
                          disabled={isSaving}
                          onClick={submitReplace}
                        >
                          {isSaving ? 'Saving…' : 'Save secret'}
                        </Button>
                        <Button
                          type="button"
                          variant="outline"
                          size="sm"
                          disabled={isSaving}
                          onClick={cancelReplace}
                        >
                          Cancel
                        </Button>
                      </div>
                    </div>
                  ) : null}
                </div>
              );
            })}
          </div>
        </CardContent>
      </Card>

      <AlertDialog
        open={clearTarget !== null}
        onOpenChange={(open) => {
          if (!open) {
            setClearField(null);
          }
        }}
        title="Clear persisted secret?"
        description={
          clearTarget ? (
            <>
              This removes the saved value for <strong>{getSecretFieldLabel(clearTarget.field)}</strong>.
              Runtime environment overrides, if present, remain active until those env vars change.
            </>
          ) : null
        }
        confirmLabel="Clear secret"
        destructive
        loading={clearTarget !== null && savingField === clearTarget.field}
        loadingLabel="Clearing…"
        onConfirm={confirmClear}
      />
    </>
  );
}

function SecretSummaryTile({
  eyebrow,
  title,
  description,
}: {
  eyebrow: string;
  title: string;
  description: string;
}) {
  return (
    <div className="rounded-2xl border border-border bg-background/60 p-4">
      <div className="text-[11px] uppercase tracking-[0.22em] text-muted-foreground">{eyebrow}</div>
      <div className="mt-2 text-base font-semibold text-foreground">{title}</div>
      <p className="mt-1 text-sm text-muted-foreground">{description}</p>
    </div>
  );
}

function SecretStatusCard({
  label,
  value,
  tone,
}: {
  label: string;
  value: string;
  tone: 'default' | 'warning';
}) {
  return (
    <div
      className={
        tone === 'warning'
          ? 'rounded-xl border border-amber-200/80 bg-amber-50/80 px-3 py-2 text-amber-900 dark:border-amber-900/60 dark:bg-amber-950/30 dark:text-amber-100'
          : 'rounded-xl border border-border/80 bg-card/80 px-3 py-2 text-foreground'
      }
    >
      <div className={tone === 'warning' ? 'uppercase tracking-[0.16em] opacity-70' : 'uppercase tracking-[0.16em] text-muted-foreground'}>
        {label}
      </div>
      <div className="mt-1 text-sm font-medium">{value}</div>
    </div>
  );
}
