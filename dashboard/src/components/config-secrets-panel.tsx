'use client';

import { startTransition, useMemo, useState } from 'react';

import { AlertDialog } from '@/components/ui/alert-dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { FormMessage } from '@/components/ui/form-field';
import { Textarea } from '@/components/ui/textarea';
import {
  getConfigUpdateErrorDetails,
  updateConfig,
} from '@/lib/api';
import type { ConfigResponse, SecretFieldMetadata } from '@/types/config';

type ConfigSecretsPanelProps = {
  config: ConfigResponse;
  onConfigChange: (config: ConfigResponse) => void;
};

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

function buildPresenceSummary(secret: SecretFieldMetadata): string {
  if (!secret.persisted_present && !secret.effective_present) {
    return 'Not configured';
  }

  const persisted = secret.persisted_present
    ? `${secret.persisted_count} persisted`
    : 'no persisted value';
  const effective = secret.effective_present
    ? `${secret.effective_count} active at runtime`
    : 'not active at runtime';

  return `${persisted} • ${effective}`;
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
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [savingField, setSavingField] = useState<string | null>(null);
  const [clearField, setClearField] = useState<string | null>(null);

  const activeField = config.secret_fields.find((field) => field.field === editingField) ?? null;
  const clearTarget = config.secret_fields.find((field) => field.field === clearField) ?? null;

  const beginReplace = (field: string) => {
    setEditingField(field);
    setDraftValue('');
    setMessage(null);
    setError(null);
  };

  const cancelReplace = () => {
    setEditingField(null);
    setDraftValue('');
    setError(null);
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
      setError(
        multiValue
          ? 'Provide at least one secret value before saving.'
          : 'Provide a replacement value before saving.'
      );
      return;
    }

    setSavingField(activeField.field);
    setMessage(null);
    setError(null);

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
        setMessage(
          `${getSecretFieldLabel(activeField.field)} updated. Applies to new runs.`
        );
      });
    } catch (updateError) {
      const details = getConfigUpdateErrorDetails(updateError);
      setError(details.message);
    } finally {
      setSavingField(null);
    }
  };

  const confirmClear = async () => {
    if (!clearTarget) {
      return;
    }

    setSavingField(clearTarget.field);
    setMessage(null);
    setError(null);

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
        setMessage(
          `${getSecretFieldLabel(clearTarget.field)} cleared. Applies to new runs.`
        );
      });
    } catch (updateError) {
      const details = getConfigUpdateErrorDetails(updateError);
      setError(details.message);
      setClearField(null);
    } finally {
      setSavingField(null);
    }
  };

  return (
    <>
      <div className="rounded-2xl border border-border bg-card p-5 shadow-sm">
        <div className="flex items-start justify-between gap-3">
          <div>
            <h2 className="text-base font-semibold">Secret fields</h2>
            <p className="mt-1.5 text-sm text-muted-foreground">
              Secrets stay masked. Replacing or clearing a secret updates the persisted config only.
            </p>
          </div>
          <span className="rounded-full border border-border px-2.5 py-0.5 text-xs text-muted-foreground">
            Applies to new runs
          </span>
        </div>

        {message ? (
          <FormMessage tone="success" className="mt-4">{message}</FormMessage>
        ) : null}
        {error ? (
          <FormMessage tone="error" className="mt-4">{error}</FormMessage>
        ) : null}

        <div className="mt-4 space-y-3">
          {config.secret_fields.map((field) => {
            const multiValue = isMultiValueSecret(field.field);
            const overridden = overriddenFields.has(field.field);
            const isEditing = editingField === field.field;
            const isSaving = savingField === field.field;
            const overrideSources = config.override_sources[field.field] ?? [];

            return (
              <div
                key={field.field}
                className="rounded-2xl border border-border bg-background px-4 py-3"
              >
                <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                  <div className="space-y-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <div className="font-medium">{getSecretFieldLabel(field.field)}</div>
                      <span className="rounded-full border border-border px-2 py-0.5 text-[11px] uppercase tracking-wide text-muted-foreground">
                        {multiValue ? 'Multi-value' : 'Single value'}
                      </span>
                      {overridden ? (
                        <span className="rounded-full bg-amber-100 px-2 py-0.5 text-[11px] uppercase tracking-wide text-amber-900">
                          Env override
                        </span>
                      ) : null}
                    </div>
                    <div className="text-sm text-muted-foreground">{field.field}</div>
                    <div className="text-sm text-muted-foreground">
                      {buildPresenceSummary(field)}
                    </div>
                    {overridden ? (
                      <div className="text-xs text-amber-900">
                        Runtime currently uses {overrideSources.join(', ')}.
                      </div>
                    ) : null}
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

                {isEditing ? (
                  <div className="mt-4 space-y-3 rounded-xl border border-border bg-card p-3">
                    <label className="block text-sm font-medium" htmlFor={`secret-${field.field}`}>
                      {multiValue ? 'One secret per line' : 'Replacement value'}
                    </label>
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
      </div>

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
