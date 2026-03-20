'use client';

import Link from 'next/link';
import { startTransition, useEffect, useState, type ReactNode } from 'react';

import { Button } from '@/components/ui/button';
import {
  getApiErrorMessage,
  getConfig,
  getConfigUpdateErrorDetails,
  updateConfig,
} from '@/lib/api';
import type { ConfigResponse } from '@/types/config';

type FormState = {
  searchProviders: string;
  searchDepth: string;
  enableCrossRef: boolean;
  teamSize: string;
  parallelExecution: boolean;
  outputFormat: string;
  outputSaveDir: string;
  routeAnalyzer: string;
  routeDeepAnalyzer: string;
  routeReportQualityEvaluator: string;
  routeReporter: string;
  routeDefault: string;
  // Cache settings
  cacheEnabled: boolean;
  cacheTtlSeconds: string;
  cacheMaxEntries: string;
};

type FieldDefinition = {
  path: string;
  label: string;
  description: string;
};

const FIELD_DEFINITIONS: FieldDefinition[] = [
  {
    path: 'search.providers',
    label: 'Search providers',
    description: 'Comma-separated provider IDs used for new runs.',
  },
  {
    path: 'search.depth',
    label: 'Search depth',
    description: 'Default depth for runtime search planning.',
  },
  {
    path: 'research.enable_cross_ref',
    label: 'Cross-reference analysis',
    description: 'Enable cross-source comparison in reports.',
  },
  {
    path: 'search_team.team_size',
    label: 'Team size',
    description: 'Number of concurrent research agents available to a run.',
  },
  {
    path: 'search_team.parallel_execution',
    label: 'Parallel execution',
    description: 'Allow the search team to fan out work in parallel.',
  },
  {
    path: 'output.format',
    label: 'Output format',
    description: 'Default persisted report format.',
  },
  {
    path: 'output.save_dir',
    label: 'Report directory',
    description: 'Directory where saved reports are written.',
  },
  {
    path: 'llm.route_defaults.analyzer',
    label: 'Analyzer route',
    description: 'Default transport for the analyzer agent.',
  },
  {
    path: 'llm.route_defaults.deep_analyzer',
    label: 'Deep analyzer route',
    description: 'Default transport for deep-analysis passes.',
  },
  {
    path: 'llm.route_defaults.report_quality_evaluator',
    label: 'Quality evaluator route',
    description: 'Default transport for report quality scoring.',
  },
  {
    path: 'llm.route_defaults.reporter',
    label: 'Reporter route',
    description: 'Default transport for report generation.',
  },
  {
    path: 'llm.route_defaults.default',
    label: 'Fallback route',
    description: 'Default transport for agents without an explicit mapping.',
  },
  {
    path: 'search_cache.enabled',
    label: 'Enable search cache',
    description: 'Cache search results to reduce API calls and costs.',
  },
  {
    path: 'search_cache.ttl_seconds',
    label: 'Cache TTL (seconds)',
    description: 'Time-to-live for cached search results in seconds.',
  },
  {
    path: 'search_cache.max_entries',
    label: 'Max cache entries',
    description: 'Maximum number of entries to keep in the cache.',
  },
];

const DEFAULT_ROUTE_OPTION = 'anthropic';
const ROUTE_OPTIONS = ['openrouter', 'cerebras', 'anthropic', 'heuristic'] as const;
const ROUTE_OPTION_SET = new Set<string>(ROUTE_OPTIONS);
const DEPTH_OPTIONS = ['quick', 'standard', 'deep'];
const OUTPUT_OPTIONS = ['markdown', 'json', 'html'];

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

function normalizeRouteOption(value: unknown): string {
  const route = typeof value === 'string' ? value : '';
  return ROUTE_OPTION_SET.has(route) ? route : DEFAULT_ROUTE_OPTION;
}

function normalizeFormState(config: ConfigResponse): FormState {
  const source = config.persisted_config;
  return {
    searchProviders: Array.isArray(readPath(source, 'search.providers'))
      ? ((readPath(source, 'search.providers') as string[]) ?? []).join(', ')
      : '',
    searchDepth: String(readPath(source, 'search.depth') ?? 'deep'),
    enableCrossRef: Boolean(readPath(source, 'research.enable_cross_ref')),
    teamSize: String(readPath(source, 'search_team.team_size') ?? 4),
    parallelExecution: Boolean(readPath(source, 'search_team.parallel_execution')),
    outputFormat: String(readPath(source, 'output.format') ?? 'markdown'),
    outputSaveDir: String(readPath(source, 'output.save_dir') ?? './reports'),
    routeAnalyzer: normalizeRouteOption(readPath(source, 'llm.route_defaults.analyzer')),
    routeDeepAnalyzer: normalizeRouteOption(readPath(source, 'llm.route_defaults.deep_analyzer')),
    routeReportQualityEvaluator: normalizeRouteOption(
      readPath(source, 'llm.route_defaults.report_quality_evaluator')
    ),
    routeReporter: normalizeRouteOption(readPath(source, 'llm.route_defaults.reporter')),
    routeDefault: normalizeRouteOption(readPath(source, 'llm.route_defaults.default')),
    // Cache settings
    cacheEnabled: Boolean(readPath(source, 'search_cache.enabled')),
    cacheTtlSeconds: String(readPath(source, 'search_cache.ttl_seconds') ?? 3600),
    cacheMaxEntries: String(readPath(source, 'search_cache.max_entries') ?? 1000),
  };
}

export function ConfigEditor() {
  const [config, setConfig] = useState<ConfigResponse | null>(null);
  const [form, setForm] = useState<FormState | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [saveMessage, setSaveMessage] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});

  useEffect(() => {
    let mounted = true;

    const load = async () => {
      setLoading(true);
      setLoadError(null);

      try {
        const response = await getConfig();
        if (!mounted) {
          return;
        }
        startTransition(() => {
          setConfig(response);
          setForm(normalizeFormState(response));
          setFieldErrors({});
        });
      } catch (error) {
        if (mounted) {
          setLoadError(getApiErrorMessage(error, 'Failed to load configuration.'));
        }
      } finally {
        if (mounted) {
          setLoading(false);
        }
      }
    };

    void load();

    return () => {
      mounted = false;
    };
  }, []);

  if (loading) {
    return <div className="rounded-3xl border border-border bg-card p-8">Loading settings…</div>;
  }

  if (loadError || !config || !form) {
    return (
      <div className="rounded-3xl border border-destructive/30 bg-card p-8">
        <p className="text-sm text-destructive">{loadError ?? 'Configuration is unavailable.'}</p>
      </div>
    );
  }

  const overriddenFields = new Set(config.overridden_fields);
  const overrideSources = config.override_sources;

  const handleSave = async () => {
    setSaving(true);
    setSaveError(null);
    setSaveMessage(null);
    setFieldErrors({});

    try {
      const response = await updateConfig({
        updates: {
          'search.providers': form.searchProviders
            .split(',')
            .map((value) => value.trim())
            .filter(Boolean),
          'search.depth': form.searchDepth,
          'research.enable_cross_ref': form.enableCrossRef,
          'search_team.team_size': Number(form.teamSize),
          'search_team.parallel_execution': form.parallelExecution,
          'output.format': form.outputFormat,
          'output.save_dir': form.outputSaveDir,
          'llm.route_defaults.analyzer': form.routeAnalyzer,
          'llm.route_defaults.deep_analyzer': form.routeDeepAnalyzer,
          'llm.route_defaults.report_quality_evaluator': form.routeReportQualityEvaluator,
          'llm.route_defaults.reporter': form.routeReporter,
          'llm.route_defaults.default': form.routeDefault,
          // Cache settings
          'search_cache.enabled': form.cacheEnabled,
          'search_cache.ttl_seconds': Number(form.cacheTtlSeconds),
          'search_cache.max_entries': Number(form.cacheMaxEntries),
        },
      });

      startTransition(() => {
        setConfig(response);
        setForm(normalizeFormState(response));
        setSaveMessage('Configuration saved.');
      });
    } catch (error) {
      const details = getConfigUpdateErrorDetails(error);
      setSaveError(details.message);

      const nextFieldErrors: Record<string, string> = {};
      for (const item of details.fields) {
        nextFieldErrors[item.field] = item.message;
      }
      for (const item of details.conflicts) {
        nextFieldErrors[item.field] = `${item.message} (${item.env_vars.join(', ')})`;
      }
      setFieldErrors(nextFieldErrors);
    } finally {
      setSaving(false);
    }
  };

  const updateField = <K extends keyof FormState>(key: K, value: FormState[K]) => {
    setForm((current) => (current ? { ...current, [key]: value } : current));
  };

  return (
    <div className="space-y-5">
      <header className="rounded-2xl border border-border bg-card/95 p-6 shadow-sm">
        <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
          <div className="space-y-1">
            <p className="text-xs uppercase tracking-[0.28em] text-muted-foreground">Dashboard Settings</p>
            <h1 className="text-2xl font-semibold tracking-tight">Config editor</h1>
            <p className="max-w-2xl text-sm text-muted-foreground">
              Edit the persisted YAML config used by the CLI and future research runs. Runtime
              environment overrides stay in effect until those env vars change.
            </p>
          </div>
          <div className="rounded-xl border border-border bg-background/70 px-3 py-2 text-sm shrink-0">
            <div>Path: {config.config_path}</div>
            <div>File: {config.file_exists ? 'Present' : 'Missing, defaults active'}</div>
          </div>
        </div>
      </header>

      <div className="grid gap-5 lg:grid-cols-[1fr_320px]">
        <div className="space-y-5 rounded-2xl border border-border bg-card p-6 shadow-sm">
          <section className="space-y-3">
            <h2 className="text-lg font-semibold">Research defaults</h2>
            <div className="grid gap-4 sm:grid-cols-2">
              <FieldShell definition={FIELD_DEFINITIONS[0]} error={fieldErrors['search.providers']} overridden={overriddenFields.has('search.providers')} effectiveValue={String(readPath(config.effective_config, 'search.providers') ?? '')} persistedValue={String(readPath(config.persisted_config, 'search.providers') ?? '')} overrideSource={overrideSources['search.providers']}>
                <input
                  className="h-9 w-full rounded-lg border border-border bg-background px-3 text-sm"
                  disabled={saving || overriddenFields.has('search.providers')}
                  value={form.searchProviders}
                  onChange={(event) => updateField('searchProviders', event.target.value)}
                />
              </FieldShell>
              <FieldShell definition={FIELD_DEFINITIONS[1]} error={fieldErrors['search.depth']} overridden={overriddenFields.has('search.depth')} effectiveValue={String(readPath(config.effective_config, 'search.depth') ?? '')} persistedValue={String(readPath(config.persisted_config, 'search.depth') ?? '')} overrideSource={overrideSources['search.depth']}>
                <select
                  className="h-9 w-full rounded-lg border border-border bg-background px-3 text-sm"
                  disabled={saving || overriddenFields.has('search.depth')}
                  value={form.searchDepth}
                  onChange={(event) => updateField('searchDepth', event.target.value)}
                >
                  {DEPTH_OPTIONS.map((option) => (
                    <option key={option} value={option}>
                      {option}
                    </option>
                  ))}
                </select>
              </FieldShell>
              <FieldShell definition={FIELD_DEFINITIONS[2]} error={fieldErrors['research.enable_cross_ref']} overridden={overriddenFields.has('research.enable_cross_ref')} effectiveValue={String(readPath(config.effective_config, 'research.enable_cross_ref') ?? '')} persistedValue={String(readPath(config.persisted_config, 'research.enable_cross_ref') ?? '')} overrideSource={overrideSources['research.enable_cross_ref']}>
                <label className="flex items-center gap-2.5 rounded-lg border border-border bg-background px-3 py-2 text-sm">
                  <input
                    checked={form.enableCrossRef}
                    className="h-4 w-4"
                    disabled={saving || overriddenFields.has('research.enable_cross_ref')}
                    type="checkbox"
                    onChange={(event) => updateField('enableCrossRef', event.target.checked)}
                  />
                  Enable cross-reference analysis
                </label>
              </FieldShell>
            </div>
          </section>

          <section className="space-y-3">
            <h2 className="text-lg font-semibold">Execution and output</h2>
            <div className="grid gap-4 sm:grid-cols-2">
              <FieldShell definition={FIELD_DEFINITIONS[3]} error={fieldErrors['search_team.team_size']} overridden={overriddenFields.has('search_team.team_size')} effectiveValue={String(readPath(config.effective_config, 'search_team.team_size') ?? '')} persistedValue={String(readPath(config.persisted_config, 'search_team.team_size') ?? '')} overrideSource={overrideSources['search_team.team_size']}>
                <input
                  className="w-full rounded-xl border border-border bg-background px-3 py-2 text-sm"
                  disabled={saving || overriddenFields.has('search_team.team_size')}
                  min={2}
                  max={8}
                  type="number"
                  value={form.teamSize}
                  onChange={(event) => updateField('teamSize', event.target.value)}
                />
              </FieldShell>
              <FieldShell definition={FIELD_DEFINITIONS[4]} error={fieldErrors['search_team.parallel_execution']} overridden={overriddenFields.has('search_team.parallel_execution')} effectiveValue={String(readPath(config.effective_config, 'search_team.parallel_execution') ?? '')} persistedValue={String(readPath(config.persisted_config, 'search_team.parallel_execution') ?? '')} overrideSource={overrideSources['search_team.parallel_execution']}>
                <label className="flex items-center gap-2.5 rounded-lg border border-border bg-background px-3 py-2 text-sm">
                  <input
                    checked={form.parallelExecution}
                    className="h-4 w-4"
                    disabled={saving || overriddenFields.has('search_team.parallel_execution')}
                    type="checkbox"
                    onChange={(event) => updateField('parallelExecution', event.target.checked)}
                  />
                  Run the search team in parallel
                </label>
              </FieldShell>
              <FieldShell definition={FIELD_DEFINITIONS[5]} error={fieldErrors['output.format']} overridden={overriddenFields.has('output.format')} effectiveValue={String(readPath(config.effective_config, 'output.format') ?? '')} persistedValue={String(readPath(config.persisted_config, 'output.format') ?? '')} overrideSource={overrideSources['output.format']}>
                <select
                  className="w-full rounded-xl border border-border bg-background px-3 py-2 text-sm"
                  disabled={saving || overriddenFields.has('output.format')}
                  value={form.outputFormat}
                  onChange={(event) => updateField('outputFormat', event.target.value)}
                >
                  {OUTPUT_OPTIONS.map((option) => (
                    <option key={option} value={option}>
                      {option}
                    </option>
                  ))}
                </select>
              </FieldShell>
              <FieldShell definition={FIELD_DEFINITIONS[6]} error={fieldErrors['output.save_dir']} overridden={overriddenFields.has('output.save_dir')} effectiveValue={String(readPath(config.effective_config, 'output.save_dir') ?? '')} persistedValue={String(readPath(config.persisted_config, 'output.save_dir') ?? '')} overrideSource={overrideSources['output.save_dir']}>
                <input
                  className="w-full rounded-xl border border-border bg-background px-3 py-2 text-sm"
                  disabled={saving || overriddenFields.has('output.save_dir')}
                  value={form.outputSaveDir}
                  onChange={(event) => updateField('outputSaveDir', event.target.value)}
                />
              </FieldShell>
            </div>
          </section>

          <section className="space-y-3">
            <h2 className="text-lg font-semibold">LLM routing defaults</h2>
            <div className="grid gap-4 sm:grid-cols-2">
              <RouteField definition={FIELD_DEFINITIONS[7]} field="llm.route_defaults.analyzer" value={form.routeAnalyzer} onChange={(value) => updateField('routeAnalyzer', value)} disabled={saving} error={fieldErrors['llm.route_defaults.analyzer']} overriddenFields={overriddenFields} config={config} overrideSources={overrideSources} />
              <RouteField definition={FIELD_DEFINITIONS[8]} field="llm.route_defaults.deep_analyzer" value={form.routeDeepAnalyzer} onChange={(value) => updateField('routeDeepAnalyzer', value)} disabled={saving} error={fieldErrors['llm.route_defaults.deep_analyzer']} overriddenFields={overriddenFields} config={config} overrideSources={overrideSources} />
              <RouteField definition={FIELD_DEFINITIONS[9]} field="llm.route_defaults.report_quality_evaluator" value={form.routeReportQualityEvaluator} onChange={(value) => updateField('routeReportQualityEvaluator', value)} disabled={saving} error={fieldErrors['llm.route_defaults.report_quality_evaluator']} overriddenFields={overriddenFields} config={config} overrideSources={overrideSources} />
              <RouteField definition={FIELD_DEFINITIONS[10]} field="llm.route_defaults.reporter" value={form.routeReporter} onChange={(value) => updateField('routeReporter', value)} disabled={saving} error={fieldErrors['llm.route_defaults.reporter']} overriddenFields={overriddenFields} config={config} overrideSources={overrideSources} />
              <RouteField definition={FIELD_DEFINITIONS[11]} field="llm.route_defaults.default" value={form.routeDefault} onChange={(value) => updateField('routeDefault', value)} disabled={saving} error={fieldErrors['llm.route_defaults.default']} overriddenFields={overriddenFields} config={config} overrideSources={overrideSources} />
            </div>
          </section>

          <section className="space-y-3">
            <h2 className="text-lg font-semibold">Search cache</h2>
            <p className="text-sm text-muted-foreground">
              Cache search results to reduce API calls and costs. Cached results are reused for identical queries.
            </p>
            <div className="grid gap-4 sm:grid-cols-3">
              <FieldShell definition={FIELD_DEFINITIONS[12]} error={fieldErrors['search_cache.enabled']} overridden={overriddenFields.has('search_cache.enabled')} effectiveValue={String(readPath(config.effective_config, 'search_cache.enabled') ?? false)} persistedValue={String(readPath(config.persisted_config, 'search_cache.enabled') ?? false)} overrideSource={overrideSources['search_cache.enabled']}>
                <label className="flex items-center gap-2.5 rounded-lg border border-border bg-background px-3 py-2 text-sm">
                  <input
                    checked={form.cacheEnabled}
                    className="h-4 w-4"
                    disabled={saving || overriddenFields.has('search_cache.enabled')}
                    type="checkbox"
                    onChange={(event) => updateField('cacheEnabled', event.target.checked)}
                  />
                  Enable search cache
                </label>
              </FieldShell>
              <FieldShell definition={FIELD_DEFINITIONS[13]} error={fieldErrors['search_cache.ttl_seconds']} overridden={overriddenFields.has('search_cache.ttl_seconds')} effectiveValue={String(readPath(config.effective_config, 'search_cache.ttl_seconds') ?? 3600)} persistedValue={String(readPath(config.persisted_config, 'search_cache.ttl_seconds') ?? 3600)} overrideSource={overrideSources['search_cache.ttl_seconds']}>
                <input
                  className="w-full rounded-xl border border-border bg-background px-3 py-2 text-sm"
                  disabled={saving || overriddenFields.has('search_cache.ttl_seconds')}
                  min={1}
                  type="number"
                  value={form.cacheTtlSeconds}
                  onChange={(event) => updateField('cacheTtlSeconds', event.target.value)}
                />
              </FieldShell>
              <FieldShell definition={FIELD_DEFINITIONS[14]} error={fieldErrors['search_cache.max_entries']} overridden={overriddenFields.has('search_cache.max_entries')} effectiveValue={String(readPath(config.effective_config, 'search_cache.max_entries') ?? 1000)} persistedValue={String(readPath(config.persisted_config, 'search_cache.max_entries') ?? 1000)} overrideSource={overrideSources['search_cache.max_entries']}>
                <input
                  className="w-full rounded-xl border border-border bg-background px-3 py-2 text-sm"
                  disabled={saving || overriddenFields.has('search_cache.max_entries')}
                  min={1}
                  type="number"
                  value={form.cacheMaxEntries}
                  onChange={(event) => updateField('cacheMaxEntries', event.target.value)}
                />
              </FieldShell>
            </div>
          </section>

          <footer className="flex flex-col gap-3 border-t border-border pt-5 sm:flex-row sm:items-center sm:justify-between">
            <div className="text-sm text-muted-foreground">
              {saveError ? <span className="text-destructive">{saveError}</span> : saveMessage}
            </div>
            <div className="flex gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setForm(normalizeFormState(config))}
                type="button"
              >
                Reset
              </Button>
              <Button size="sm" disabled={saving} onClick={handleSave} type="button">
                {saving ? 'Saving…' : 'Save config'}
              </Button>
            </div>
          </footer>
        </div>

        <aside className="space-y-5">
          <div className="rounded-2xl border border-border bg-card p-5 shadow-sm">
            <h2 className="text-base font-semibold">Override status</h2>
            <p className="mt-1.5 text-sm text-muted-foreground">
              Fields with active env overrides are read-only here because runtime still prefers the
              environment.
            </p>
            <div className="mt-4 space-y-2 text-sm">
              {config.overridden_fields.length === 0 ? (
                <div className="rounded-2xl border border-border bg-background px-4 py-3">
                  No active environment overrides.
                </div>
              ) : (
                config.overridden_fields.map((field) => (
                  <div key={field} className="rounded-2xl border border-amber-300/70 bg-amber-50 px-4 py-3 text-amber-950">
                    <div className="font-medium">{field}</div>
                    <div className="mt-1 text-xs">{(overrideSources[field] ?? []).join(', ')}</div>
                  </div>
                ))
              )}
            </div>
          </div>

          <div className="rounded-2xl border border-border bg-card p-5 shadow-sm">
            <h2 className="text-base font-semibold">Secret fields</h2>
            <div className="mt-3 space-y-2 text-sm">
              {config.secret_fields.map((field) => (
                <div key={field.field} className="rounded-2xl border border-border bg-background px-4 py-3">
                  <div className="font-medium">{field.field}</div>
                  <div className="mt-1 text-muted-foreground">
                    Persisted: {field.persisted_present ? `${field.persisted_count} configured` : 'none'}
                  </div>
                  <div className="text-muted-foreground">
                    Effective: {field.effective_present ? `${field.effective_count} active` : 'none'}
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="rounded-2xl border border-border bg-card p-5 shadow-sm">
            <h2 className="text-base font-semibold">Navigation</h2>
            <div className="mt-3">
              <Link
                className="inline-flex h-9 items-center justify-center rounded-md border border-border bg-background px-4 py-2 text-sm font-medium transition-colors hover:bg-accent hover:text-accent-foreground"
                href="/"
              >
                Back to sessions
              </Link>
            </div>
          </div>
        </aside>
      </div>
    </div>
  );
}

function RouteField({
  definition,
  field,
  value,
  onChange,
  disabled,
  error,
  overriddenFields,
  config,
  overrideSources,
}: {
  definition: FieldDefinition;
  field: string;
  value: string;
  onChange: (value: string) => void;
  disabled: boolean;
  error?: string;
  overriddenFields: Set<string>;
  config: ConfigResponse;
  overrideSources: Record<string, string[]>;
}) {
  const overridden = overriddenFields.has(field);
  return (
    <FieldShell
      definition={definition}
      error={error}
      overridden={overridden}
      effectiveValue={String(readPath(config.effective_config, field) ?? '')}
      persistedValue={String(readPath(config.persisted_config, field) ?? '')}
      overrideSource={overrideSources[field]}
    >
      <select
        className="h-9 w-full rounded-lg border border-border bg-background px-3 text-sm"
        disabled={disabled || overridden}
        value={value}
        onChange={(event) => onChange(event.target.value)}
      >
        {ROUTE_OPTIONS.map((option) => (
          <option key={option} value={option}>
            {option}
          </option>
        ))}
      </select>
    </FieldShell>
  );
}

function FieldShell({
  definition,
  error,
  overridden,
  effectiveValue,
  persistedValue,
  overrideSource,
  children,
}: {
  definition: FieldDefinition;
  error?: string;
  overridden: boolean;
  effectiveValue: string;
  persistedValue: string;
  overrideSource?: string[];
  children: ReactNode;
}) {
  return (
    <div className="space-y-2 rounded-xl border border-border bg-muted/30 p-3">
      <div className="flex items-start justify-between gap-2">
        <div>
          <div className="text-sm font-medium">{definition.label}</div>
          <div className="text-xs text-muted-foreground">{definition.description}</div>
        </div>
        {overridden ? (
          <span className="shrink-0 rounded-full bg-amber-100 px-2 py-0.5 text-[11px] font-medium uppercase tracking-wide text-amber-900 dark:bg-amber-900 dark:text-amber-100">
            Env override
          </span>
        ) : null}
      </div>
      {children}
      {overridden ? (
        <p className="text-xs text-amber-900">
          Saved: <span className="font-medium">{persistedValue}</span>. Runtime:{' '}
          <span className="font-medium">{effectiveValue}</span>. Source:{' '}
          {(overrideSource ?? []).join(', ')}
        </p>
      ) : null}
      {error ? <p className="text-xs text-destructive">{error}</p> : null}
    </div>
  );
}
