'use client'

import Link from 'next/link'
import { startTransition, useEffect, useState } from 'react'
import type { ReactNode } from 'react'

import { ConfigSecretsPanel } from '@/components/config-secrets-panel'
import { HelpCallout } from '@/components/ui/help-callout'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button, buttonVariants } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { CheckboxRow, SettingFieldShell } from '@/components/ui/form-field'
import { Input } from '@/components/ui/input'
import { NativeSelect } from '@/components/ui/native-select'
import { useNotifications } from '@/components/ui/notification-center'
import { getApiErrorMessage, getConfig, getConfigUpdateErrorDetails, updateConfig } from '@/lib/api'
import type { ConfigResponse } from '@/types/config'

type FormState = {
  searchProviders: string
  searchDepth: string
  enableCrossRef: boolean
  teamSize: string
  parallelExecution: boolean
  outputFormat: string
  outputSaveDir: string
  routeAnalyzer: string
  routeDeepAnalyzer: string
  routeReportQualityEvaluator: string
  routeReporter: string
  routeDefault: string
  cacheEnabled: boolean
  cacheTtlSeconds: string
  cacheMaxEntries: string
}

type FieldDefinition = {
  path: string
  label: string
  description: string
}

type FormBinding = {
  path: string
  key: keyof FormState
}

type BannerState = {
  variant: 'info' | 'success' | 'destructive'
  title: string
  description: string
} | null

const FIELD_DEFINITIONS: FieldDefinition[] = [
  {
    path: 'search.providers',
    label: 'Search providers',
    description: 'Comma-separated provider IDs queued for new runs.',
  },
  {
    path: 'search.depth',
    label: 'Search depth',
    description: 'Default depth used when a new run plans its search work.',
  },
  {
    path: 'research.enable_cross_ref',
    label: 'Cross-reference analysis',
    description: 'Compare sources against each other in generated reports.',
  },
  {
    path: 'search_team.team_size',
    label: 'Team size',
    description: 'How many research agents a new run can use.',
  },
  {
    path: 'search_team.parallel_execution',
    label: 'Parallel execution',
    description: 'Let the search team fan out work in parallel.',
  },
  {
    path: 'output.format',
    label: 'Output format',
    description: 'Default report format written for future runs.',
  },
  {
    path: 'output.save_dir',
    label: 'Report directory',
    description: 'Destination directory for saved reports.',
  },
  {
    path: 'llm.route_defaults.analyzer',
    label: 'Analyzer route',
    description: 'Default provider route for the analyzer agent.',
  },
  {
    path: 'llm.route_defaults.deep_analyzer',
    label: 'Deep analyzer route',
    description: 'Default provider route for deeper analysis passes.',
  },
  {
    path: 'llm.route_defaults.report_quality_evaluator',
    label: 'Quality evaluator route',
    description: 'Default provider route for report scoring.',
  },
  {
    path: 'llm.route_defaults.reporter',
    label: 'Reporter route',
    description: 'Default provider route for report generation.',
  },
  {
    path: 'llm.route_defaults.default',
    label: 'Fallback route',
    description: 'Provider route used when an agent has no explicit mapping.',
  },
  {
    path: 'search_cache.enabled',
    label: 'Enable search cache',
    description: 'Reuse identical query results to reduce API calls and cost.',
  },
  {
    path: 'search_cache.ttl_seconds',
    label: 'Cache TTL (seconds)',
    description: 'How long cached search results stay valid.',
  },
  {
    path: 'search_cache.max_entries',
    label: 'Max cache entries',
    description: 'Upper limit for cached search results kept on disk.',
  },
]

const FRIENDLY_FIELD_LABELS: Record<string, string> = {
  ...Object.fromEntries(FIELD_DEFINITIONS.map((definition) => [definition.path, definition.label])),
  'tavily.api_keys': 'Tavily API keys',
  'llm.openrouter.api_key': 'OpenRouter API key',
  'llm.openrouter.api_keys': 'OpenRouter API keys',
  'llm.cerebras.api_key': 'Cerebras API key',
  'llm.cerebras.api_keys': 'Cerebras API keys',
  'llm.anthropic.api_key': 'Anthropic API key',
  'llm.anthropic.api_keys': 'Anthropic API keys',
}

const FORM_BINDINGS: FormBinding[] = [
  { path: 'search.providers', key: 'searchProviders' },
  { path: 'search.depth', key: 'searchDepth' },
  { path: 'research.enable_cross_ref', key: 'enableCrossRef' },
  { path: 'search_team.team_size', key: 'teamSize' },
  { path: 'search_team.parallel_execution', key: 'parallelExecution' },
  { path: 'output.format', key: 'outputFormat' },
  { path: 'output.save_dir', key: 'outputSaveDir' },
  { path: 'llm.route_defaults.analyzer', key: 'routeAnalyzer' },
  { path: 'llm.route_defaults.deep_analyzer', key: 'routeDeepAnalyzer' },
  { path: 'llm.route_defaults.report_quality_evaluator', key: 'routeReportQualityEvaluator' },
  { path: 'llm.route_defaults.reporter', key: 'routeReporter' },
  { path: 'llm.route_defaults.default', key: 'routeDefault' },
  { path: 'search_cache.enabled', key: 'cacheEnabled' },
  { path: 'search_cache.ttl_seconds', key: 'cacheTtlSeconds' },
  { path: 'search_cache.max_entries', key: 'cacheMaxEntries' },
]

const RESEARCH_DEFAULT_PATHS = ['search.providers', 'search.depth', 'research.enable_cross_ref']

const EXECUTION_AND_OUTPUT_PATHS = [
  'search_team.team_size',
  'search_team.parallel_execution',
  'output.format',
  'output.save_dir',
  'search_cache.enabled',
  'search_cache.ttl_seconds',
  'search_cache.max_entries',
]

const MODEL_ROUTING_PATHS = [
  'llm.route_defaults.analyzer',
  'llm.route_defaults.deep_analyzer',
  'llm.route_defaults.report_quality_evaluator',
  'llm.route_defaults.reporter',
  'llm.route_defaults.default',
]

const DEFAULT_ROUTE_OPTION = 'anthropic'
const ROUTE_OPTIONS = ['openrouter', 'cerebras', 'anthropic', 'heuristic'] as const
const ROUTE_OPTION_SET = new Set<string>(ROUTE_OPTIONS)
const DEPTH_OPTIONS = ['quick', 'standard', 'deep']
const OUTPUT_OPTIONS = ['markdown', 'json', 'html']

function readPath(source: Record<string, unknown>, path: string): unknown {
  let current: unknown = source
  for (const segment of path.split('.')) {
    if (!current || typeof current !== 'object' || !(segment in current)) {
      return undefined
    }
    current = (current as Record<string, unknown>)[segment]
  }
  return current
}

function formatConfigValue(value: unknown): string {
  if (Array.isArray(value)) {
    return value.length > 0 ? value.join(', ') : 'None'
  }
  if (typeof value === 'boolean') {
    return value ? 'Enabled' : 'Disabled'
  }
  if (value === null || value === undefined) {
    return 'Not set'
  }
  const normalized = String(value).trim()
  return normalized.length > 0 ? normalized : 'Not set'
}

function normalizeRouteOption(value: unknown): string {
  const route = typeof value === 'string' ? value : ''
  return ROUTE_OPTION_SET.has(route) ? route : DEFAULT_ROUTE_OPTION
}

function normalizeFormState(config: ConfigResponse): FormState {
  const source = config.persisted_config
  const searchProviders = readPath(source, 'search.providers')
  return {
    searchProviders: Array.isArray(searchProviders) ? searchProviders.join(', ') : '',
    searchDepth: String(readPath(source, 'search.depth') ?? 'deep'),
    enableCrossRef: Boolean(readPath(source, 'research.enable_cross_ref')),
    teamSize: String(readPath(source, 'search_team.team_size') ?? 4),
    parallelExecution: Boolean(readPath(source, 'search_team.parallel_execution')),
    outputFormat: String(readPath(source, 'output.format') ?? 'markdown'),
    outputSaveDir: String(readPath(source, 'output.save_dir') ?? './reports'),
    routeAnalyzer: normalizeRouteOption(readPath(source, 'llm.route_defaults.analyzer')),
    routeDeepAnalyzer: normalizeRouteOption(readPath(source, 'llm.route_defaults.deep_analyzer')),
    routeReportQualityEvaluator: normalizeRouteOption(
      readPath(source, 'llm.route_defaults.report_quality_evaluator'),
    ),
    routeReporter: normalizeRouteOption(readPath(source, 'llm.route_defaults.reporter')),
    routeDefault: normalizeRouteOption(readPath(source, 'llm.route_defaults.default')),
    cacheEnabled: Boolean(readPath(source, 'search_cache.enabled')),
    cacheTtlSeconds: String(readPath(source, 'search_cache.ttl_seconds') ?? 3600),
    cacheMaxEntries: String(readPath(source, 'search_cache.max_entries') ?? 1000),
  }
}

function getDirtyFieldPaths(form: FormState, baseline: FormState): string[] {
  return FORM_BINDINGS.filter(({ key }) => form[key] !== baseline[key]).map(({ path }) => path)
}

function formatFieldValue(
  config: ConfigResponse,
  source: 'persisted_config' | 'effective_config',
  path: string,
): string {
  return formatConfigValue(readPath(config[source], path))
}

function summarizeDirtyFields(paths: string[]): string {
  if (paths.length === 0) {
    return 'No unsaved changes.'
  }

  const labels = paths.map((path) => FRIENDLY_FIELD_LABELS[path] ?? path)
  if (labels.length <= 3) {
    return labels.join(', ')
  }
  return `${labels.slice(0, 3).join(', ')}, +${labels.length - 3} more`
}

function countLockedFields(paths: string[], overriddenFields: Set<string>): number {
  return paths.filter((path) => overriddenFields.has(path)).length
}

function pluralize(count: number, singular: string, plural = `${singular}s`): string {
  return count === 1 ? singular : plural
}

export function ConfigEditor() {
  const { notify } = useNotifications()
  const [config, setConfig] = useState<ConfigResponse | null>(null)
  const [form, setForm] = useState<FormState | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({})
  const [banner, setBanner] = useState<BannerState>(null)

  useEffect(() => {
    let mounted = true

    const load = async () => {
      setLoading(true)
      setLoadError(null)

      try {
        const response = await getConfig()
        if (!mounted) {
          return
        }
        startTransition(() => {
          setConfig(response)
          setForm(normalizeFormState(response))
          setFieldErrors({})
        })
      } catch (error) {
        if (mounted) {
          setLoadError(getApiErrorMessage(error, 'Failed to load configuration.'))
        }
      } finally {
        if (mounted) {
          setLoading(false)
        }
      }
    }

    void load()

    return () => {
      mounted = false
    }
  }, [])

  if (loading) {
    return (
      <Card className="border-border/80 bg-card/95">
        <CardHeader>
          <CardTitle className="text-base">Settings</CardTitle>
          <CardDescription>
            Loading persisted settings and runtime override metadata.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Alert variant="default">
            <AlertTitle>Loading settings</AlertTitle>
            <AlertDescription>
              The dashboard is fetching the latest settings snapshot.
            </AlertDescription>
          </Alert>
        </CardContent>
      </Card>
    )
  }

  if (loadError || !config || !form) {
    return (
      <Card className="border-border/80 bg-card/95">
        <CardHeader>
          <CardTitle className="text-base">Settings</CardTitle>
          <CardDescription>
            The settings workspace cannot render without a config payload.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Alert variant="destructive">
            <AlertTitle>Configuration unavailable</AlertTitle>
            <AlertDescription>{loadError ?? 'Configuration is unavailable.'}</AlertDescription>
          </Alert>
        </CardContent>
      </Card>
    )
  }

  const overriddenFields = new Set(config.overridden_fields)
  const overrideSources = config.override_sources
  const baseline = normalizeFormState(config)
  const dirtyFieldPaths = getDirtyFieldPaths(form, baseline)
  const dirtyFieldCount = dirtyFieldPaths.length
  const lockedFieldCount = FORM_BINDINGS.filter(({ path }) => overriddenFields.has(path)).length
  const overriddenSecretCount = config.secret_fields.filter((field) =>
    overriddenFields.has(field.field),
  ).length
  const configuredSecretCount = config.secret_fields.filter(
    (field) => field.persisted_present,
  ).length

  const handleSave = async () => {
    const changedFieldPaths = getDirtyFieldPaths(form, baseline)
    if (changedFieldPaths.length === 0) {
      return
    }

    setSaving(true)
    setBanner(null)
    setFieldErrors({})

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
          'search_cache.enabled': form.cacheEnabled,
          'search_cache.ttl_seconds': Number(form.cacheTtlSeconds),
          'search_cache.max_entries': Number(form.cacheMaxEntries),
        },
      })

      startTransition(() => {
        setConfig(response)
        setForm(normalizeFormState(response))
        setBanner({
          variant: 'success',
          title: 'Settings saved',
          description:
            `Saved ${changedFieldPaths.length} ${pluralize(changedFieldPaths.length, 'setting')} to the persisted config. ` +
            `Future runs will use the updated values.` +
            (response.overridden_fields.length > 0
              ? ` ${response.overridden_fields.length} runtime ${pluralize(response.overridden_fields.length, 'override')} still ${response.overridden_fields.length === 1 ? 'remains' : 'remain'} in control until the environment changes.`
              : ''),
        })
      })
      notify({
        variant: 'success',
        title: 'Settings saved',
        description: `Saved ${changedFieldPaths.length} ${pluralize(changedFieldPaths.length, 'setting')} for future runs.`,
      })
    } catch (error) {
      const details = getConfigUpdateErrorDetails(error)
      setBanner({
        variant: 'destructive',
        title: 'Save failed',
        description: details.message,
      })
      notify({
        variant: 'destructive',
        persistent: true,
        title: 'Settings save failed',
        description: details.message,
      })

      const nextFieldErrors: Record<string, string> = {}
      for (const item of details.fields) {
        nextFieldErrors[item.field] = item.message
      }
      for (const item of details.conflicts) {
        nextFieldErrors[item.field] = `${item.message} (${item.env_vars.join(', ')})`
      }
      setFieldErrors(nextFieldErrors)
    } finally {
      setSaving(false)
    }
  }

  const handleReset = () => {
    const dirtyCountBeforeReset = dirtyFieldPaths.length
    setForm(baseline)
    setFieldErrors({})
    setBanner({
      variant: 'info',
      title: 'Draft cleared',
      description:
        dirtyCountBeforeReset > 0
          ? `Reset ${dirtyCountBeforeReset} unsaved ${pluralize(dirtyCountBeforeReset, 'change')} back to the persisted config. Runtime overrides stay locked until their environment values change.`
          : 'Cleared validation feedback and restored the current persisted settings snapshot.',
    })
  }

  const updateField = <K extends keyof FormState>(key: K, value: FormState[K]) => {
    setForm((current) => (current ? { ...current, [key]: value } : current))
  }

  return (
    <div className="space-y-5">
      <HelpCallout
        id="settings-overrides"
        title="Runtime overrides"
        content="Fields marked as runtime overrides are locked because environment values take priority. Save changes to persisted config for future runs."
      />
      <header className="rounded-2xl border border-border bg-card/95 p-6 shadow-sm">
        <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
          <div className="space-y-2">
            <p className="text-xs uppercase tracking-[0.28em] text-muted-foreground">
              Dashboard Settings
            </p>
            <h1 className="text-2xl font-semibold tracking-tight">Settings</h1>
            <p className=" text-sm text-muted-foreground">
              Manage the saved defaults used for future runs, see where runtime environment values
              still take priority, and update masked secrets without exposing them in the browser.
            </p>
          </div>
          <div className="grid gap-2 rounded-2xl border border-border bg-background/70 px-4 py-3 text-sm sm:grid-cols-2 xl:min-w-[320px]">
            <div>
              <div className="text-xs uppercase tracking-[0.18em] text-muted-foreground">
                Config path
              </div>
              <div className="mt-1 break-all">{config.config_path}</div>
            </div>
            <div>
              <div className="text-xs uppercase tracking-[0.18em] text-muted-foreground">
                File status
              </div>
              <div className="mt-1">
                {config.file_exists ? 'Present' : 'Missing, defaults active'}
              </div>
            </div>
          </div>
        </div>
      </header>

      <div className="grid gap-4 md:grid-cols-3">
        <SummaryTile
          eyebrow="Future runs"
          title={
            dirtyFieldCount > 0
              ? `${dirtyFieldCount} unsaved ${pluralize(dirtyFieldCount, 'change')}`
              : 'Saved defaults are current'
          }
          description={
            dirtyFieldCount > 0
              ? `Draft edits: ${summarizeDirtyFields(dirtyFieldPaths)}`
              : 'Editable settings here only affect new runs after you save.'
          }
        />
        <SummaryTile
          eyebrow="Runtime overrides"
          title={
            config.overridden_fields.length === 0
              ? 'Runtime matches saved settings'
              : `${config.overridden_fields.length} active ${pluralize(config.overridden_fields.length, 'override')}`
          }
          description={
            config.overridden_fields.length === 0
              ? 'No active env values are shadowing dashboard-editable settings.'
              : `${lockedFieldCount} editable field ${lockedFieldCount === 1 ? 'is' : 'are'} locked here because runtime still prefers the environment.`
          }
        />
        <SummaryTile
          eyebrow="Secrets"
          title={`${configuredSecretCount}/${config.secret_fields.length} saved`}
          description={
            overriddenSecretCount > 0
              ? `${overriddenSecretCount} secret ${pluralize(overriddenSecretCount, 'field')} ${overriddenSecretCount === 1 ? 'is' : 'are'} currently shadowed by env values.`
              : 'Secret replace and clear flows update the persisted config without revealing values.'
          }
        />
      </div>

      <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_320px]">
        <div className="space-y-5">
          <SettingsSectionCard
            title="Research defaults"
            description="Saved search behavior and report analysis defaults applied when a new run starts."
            totalCount={RESEARCH_DEFAULT_PATHS.length}
            lockedCount={countLockedFields(RESEARCH_DEFAULT_PATHS, overriddenFields)}
          >
            <div className="grid gap-4 sm:grid-cols-2">
              <SettingFieldShell
                label={FIELD_DEFINITIONS[0].label}
                description={FIELD_DEFINITIONS[0].description}
                error={fieldErrors['search.providers']}
                overridden={overriddenFields.has('search.providers')}
                dirty={dirtyFieldPaths.includes('search.providers')}
                draftValue={formatConfigValue(form.searchProviders)}
                effectiveValue={formatFieldValue(config, 'effective_config', 'search.providers')}
                persistedValue={formatFieldValue(config, 'persisted_config', 'search.providers')}
                overrideSource={overrideSources['search.providers']}
              >
                <Input
                  className="h-9"
                  disabled={saving || overriddenFields.has('search.providers')}
                  value={form.searchProviders}
                  onChange={(event) => updateField('searchProviders', event.target.value)}
                />
              </SettingFieldShell>
              <SettingFieldShell
                label={FIELD_DEFINITIONS[1].label}
                description={FIELD_DEFINITIONS[1].description}
                error={fieldErrors['search.depth']}
                overridden={overriddenFields.has('search.depth')}
                dirty={dirtyFieldPaths.includes('search.depth')}
                draftValue={formatConfigValue(form.searchDepth)}
                effectiveValue={formatFieldValue(config, 'effective_config', 'search.depth')}
                persistedValue={formatFieldValue(config, 'persisted_config', 'search.depth')}
                overrideSource={overrideSources['search.depth']}
              >
                <NativeSelect
                  className="h-9"
                  disabled={saving || overriddenFields.has('search.depth')}
                  value={form.searchDepth}
                  onChange={(event) => updateField('searchDepth', event.target.value)}
                >
                  {DEPTH_OPTIONS.map((option) => (
                    <option key={option} value={option}>
                      {option}
                    </option>
                  ))}
                </NativeSelect>
              </SettingFieldShell>
              <SettingFieldShell
                label={FIELD_DEFINITIONS[2].label}
                description={FIELD_DEFINITIONS[2].description}
                error={fieldErrors['research.enable_cross_ref']}
                overridden={overriddenFields.has('research.enable_cross_ref')}
                dirty={dirtyFieldPaths.includes('research.enable_cross_ref')}
                draftValue={formatConfigValue(form.enableCrossRef)}
                effectiveValue={formatFieldValue(
                  config,
                  'effective_config',
                  'research.enable_cross_ref',
                )}
                persistedValue={formatFieldValue(
                  config,
                  'persisted_config',
                  'research.enable_cross_ref',
                )}
                overrideSource={overrideSources['research.enable_cross_ref']}
              >
                <CheckboxRow
                  checked={form.enableCrossRef}
                  disabled={saving || overriddenFields.has('research.enable_cross_ref')}
                  id="config-enable-cross-ref"
                  label="Enable cross-reference analysis"
                  onCheckedChange={(checked) => updateField('enableCrossRef', checked)}
                />
              </SettingFieldShell>
            </div>
          </SettingsSectionCard>

          <SettingsSectionCard
            title="Execution and output"
            description="Saved execution capacity, report output, and cache behavior for future runs."
            totalCount={EXECUTION_AND_OUTPUT_PATHS.length}
            lockedCount={countLockedFields(EXECUTION_AND_OUTPUT_PATHS, overriddenFields)}
          >
            <div className="grid gap-4 sm:grid-cols-2">
              <SettingFieldShell
                label={FIELD_DEFINITIONS[3].label}
                description={FIELD_DEFINITIONS[3].description}
                error={fieldErrors['search_team.team_size']}
                overridden={overriddenFields.has('search_team.team_size')}
                dirty={dirtyFieldPaths.includes('search_team.team_size')}
                draftValue={formatConfigValue(form.teamSize)}
                effectiveValue={formatFieldValue(
                  config,
                  'effective_config',
                  'search_team.team_size',
                )}
                persistedValue={formatFieldValue(
                  config,
                  'persisted_config',
                  'search_team.team_size',
                )}
                overrideSource={overrideSources['search_team.team_size']}
              >
                <Input
                  disabled={saving || overriddenFields.has('search_team.team_size')}
                  min={2}
                  max={8}
                  type="number"
                  value={form.teamSize}
                  onChange={(event) => updateField('teamSize', event.target.value)}
                />
              </SettingFieldShell>
              <SettingFieldShell
                label={FIELD_DEFINITIONS[4].label}
                description={FIELD_DEFINITIONS[4].description}
                error={fieldErrors['search_team.parallel_execution']}
                overridden={overriddenFields.has('search_team.parallel_execution')}
                dirty={dirtyFieldPaths.includes('search_team.parallel_execution')}
                draftValue={formatConfigValue(form.parallelExecution)}
                effectiveValue={formatFieldValue(
                  config,
                  'effective_config',
                  'search_team.parallel_execution',
                )}
                persistedValue={formatFieldValue(
                  config,
                  'persisted_config',
                  'search_team.parallel_execution',
                )}
                overrideSource={overrideSources['search_team.parallel_execution']}
              >
                <CheckboxRow
                  checked={form.parallelExecution}
                  disabled={saving || overriddenFields.has('search_team.parallel_execution')}
                  id="config-parallel-execution"
                  label="Run the search team in parallel"
                  onCheckedChange={(checked) => updateField('parallelExecution', checked)}
                />
              </SettingFieldShell>
              <SettingFieldShell
                label={FIELD_DEFINITIONS[5].label}
                description={FIELD_DEFINITIONS[5].description}
                error={fieldErrors['output.format']}
                overridden={overriddenFields.has('output.format')}
                dirty={dirtyFieldPaths.includes('output.format')}
                draftValue={formatConfigValue(form.outputFormat)}
                effectiveValue={formatFieldValue(config, 'effective_config', 'output.format')}
                persistedValue={formatFieldValue(config, 'persisted_config', 'output.format')}
                overrideSource={overrideSources['output.format']}
              >
                <NativeSelect
                  disabled={saving || overriddenFields.has('output.format')}
                  value={form.outputFormat}
                  onChange={(event) => updateField('outputFormat', event.target.value)}
                >
                  {OUTPUT_OPTIONS.map((option) => (
                    <option key={option} value={option}>
                      {option}
                    </option>
                  ))}
                </NativeSelect>
              </SettingFieldShell>
              <SettingFieldShell
                label={FIELD_DEFINITIONS[6].label}
                description={FIELD_DEFINITIONS[6].description}
                error={fieldErrors['output.save_dir']}
                overridden={overriddenFields.has('output.save_dir')}
                dirty={dirtyFieldPaths.includes('output.save_dir')}
                draftValue={formatConfigValue(form.outputSaveDir)}
                effectiveValue={formatFieldValue(config, 'effective_config', 'output.save_dir')}
                persistedValue={formatFieldValue(config, 'persisted_config', 'output.save_dir')}
                overrideSource={overrideSources['output.save_dir']}
              >
                <Input
                  disabled={saving || overriddenFields.has('output.save_dir')}
                  value={form.outputSaveDir}
                  onChange={(event) => updateField('outputSaveDir', event.target.value)}
                />
              </SettingFieldShell>
            </div>

            <div className="space-y-3 rounded-2xl border border-border/80 bg-background/50 p-4">
              <div className="space-y-1">
                <div className="text-sm font-medium">Search cache defaults</div>
                <div className="text-sm text-muted-foreground">
                  Cache settings live with other execution defaults because they change how future
                  runs fan out and reuse search work.
                </div>
              </div>
              <div className="grid gap-4 sm:grid-cols-3">
                <SettingFieldShell
                  label={FIELD_DEFINITIONS[12].label}
                  description={FIELD_DEFINITIONS[12].description}
                  error={fieldErrors['search_cache.enabled']}
                  overridden={overriddenFields.has('search_cache.enabled')}
                  dirty={dirtyFieldPaths.includes('search_cache.enabled')}
                  draftValue={formatConfigValue(form.cacheEnabled)}
                  effectiveValue={formatFieldValue(
                    config,
                    'effective_config',
                    'search_cache.enabled',
                  )}
                  persistedValue={formatFieldValue(
                    config,
                    'persisted_config',
                    'search_cache.enabled',
                  )}
                  overrideSource={overrideSources['search_cache.enabled']}
                >
                  <CheckboxRow
                    checked={form.cacheEnabled}
                    disabled={saving || overriddenFields.has('search_cache.enabled')}
                    id="config-cache-enabled"
                    label="Enable search cache"
                    onCheckedChange={(checked) => updateField('cacheEnabled', checked)}
                  />
                </SettingFieldShell>
                <SettingFieldShell
                  label={FIELD_DEFINITIONS[13].label}
                  description={FIELD_DEFINITIONS[13].description}
                  error={fieldErrors['search_cache.ttl_seconds']}
                  overridden={overriddenFields.has('search_cache.ttl_seconds')}
                  dirty={dirtyFieldPaths.includes('search_cache.ttl_seconds')}
                  draftValue={formatConfigValue(form.cacheTtlSeconds)}
                  effectiveValue={formatFieldValue(
                    config,
                    'effective_config',
                    'search_cache.ttl_seconds',
                  )}
                  persistedValue={formatFieldValue(
                    config,
                    'persisted_config',
                    'search_cache.ttl_seconds',
                  )}
                  overrideSource={overrideSources['search_cache.ttl_seconds']}
                >
                  <Input
                    disabled={saving || overriddenFields.has('search_cache.ttl_seconds')}
                    min={1}
                    type="number"
                    value={form.cacheTtlSeconds}
                    onChange={(event) => updateField('cacheTtlSeconds', event.target.value)}
                  />
                </SettingFieldShell>
                <SettingFieldShell
                  label={FIELD_DEFINITIONS[14].label}
                  description={FIELD_DEFINITIONS[14].description}
                  error={fieldErrors['search_cache.max_entries']}
                  overridden={overriddenFields.has('search_cache.max_entries')}
                  dirty={dirtyFieldPaths.includes('search_cache.max_entries')}
                  draftValue={formatConfigValue(form.cacheMaxEntries)}
                  effectiveValue={formatFieldValue(
                    config,
                    'effective_config',
                    'search_cache.max_entries',
                  )}
                  persistedValue={formatFieldValue(
                    config,
                    'persisted_config',
                    'search_cache.max_entries',
                  )}
                  overrideSource={overrideSources['search_cache.max_entries']}
                >
                  <Input
                    disabled={saving || overriddenFields.has('search_cache.max_entries')}
                    min={1}
                    type="number"
                    value={form.cacheMaxEntries}
                    onChange={(event) => updateField('cacheMaxEntries', event.target.value)}
                  />
                </SettingFieldShell>
              </div>
            </div>
          </SettingsSectionCard>

          <SettingsSectionCard
            title="Model routing"
            description="Saved provider routing for each agent role. Runtime overrides stay visible and read-only here."
            totalCount={MODEL_ROUTING_PATHS.length}
            lockedCount={countLockedFields(MODEL_ROUTING_PATHS, overriddenFields)}
          >
            <div className="grid gap-4 sm:grid-cols-2">
              <RouteField
                definition={FIELD_DEFINITIONS[7]}
                field="llm.route_defaults.analyzer"
                value={form.routeAnalyzer}
                onChange={(value) => updateField('routeAnalyzer', value)}
                disabled={saving}
                error={fieldErrors['llm.route_defaults.analyzer']}
                dirty={dirtyFieldPaths.includes('llm.route_defaults.analyzer')}
                overriddenFields={overriddenFields}
                config={config}
                overrideSources={overrideSources}
              />
              <RouteField
                definition={FIELD_DEFINITIONS[8]}
                field="llm.route_defaults.deep_analyzer"
                value={form.routeDeepAnalyzer}
                onChange={(value) => updateField('routeDeepAnalyzer', value)}
                disabled={saving}
                error={fieldErrors['llm.route_defaults.deep_analyzer']}
                dirty={dirtyFieldPaths.includes('llm.route_defaults.deep_analyzer')}
                overriddenFields={overriddenFields}
                config={config}
                overrideSources={overrideSources}
              />
              <RouteField
                definition={FIELD_DEFINITIONS[9]}
                field="llm.route_defaults.report_quality_evaluator"
                value={form.routeReportQualityEvaluator}
                onChange={(value) => updateField('routeReportQualityEvaluator', value)}
                disabled={saving}
                error={fieldErrors['llm.route_defaults.report_quality_evaluator']}
                dirty={dirtyFieldPaths.includes('llm.route_defaults.report_quality_evaluator')}
                overriddenFields={overriddenFields}
                config={config}
                overrideSources={overrideSources}
              />
              <RouteField
                definition={FIELD_DEFINITIONS[10]}
                field="llm.route_defaults.reporter"
                value={form.routeReporter}
                onChange={(value) => updateField('routeReporter', value)}
                disabled={saving}
                error={fieldErrors['llm.route_defaults.reporter']}
                dirty={dirtyFieldPaths.includes('llm.route_defaults.reporter')}
                overriddenFields={overriddenFields}
                config={config}
                overrideSources={overrideSources}
              />
              <RouteField
                definition={FIELD_DEFINITIONS[11]}
                field="llm.route_defaults.default"
                value={form.routeDefault}
                onChange={(value) => updateField('routeDefault', value)}
                disabled={saving}
                error={fieldErrors['llm.route_defaults.default']}
                dirty={dirtyFieldPaths.includes('llm.route_defaults.default')}
                overriddenFields={overriddenFields}
                config={config}
                overrideSources={overrideSources}
              />
            </div>
          </SettingsSectionCard>

          <ConfigSecretsPanel config={config} onConfigChange={setConfig} />

          <Card className="border-border/80 bg-card/95">
            <CardHeader className="space-y-2">
              <div className="flex flex-wrap items-center gap-2">
                <CardTitle className="text-base">Runtime override status</CardTitle>
                <Badge variant={config.overridden_fields.length === 0 ? 'secondary' : 'warning'}>
                  {config.overridden_fields.length === 0
                    ? 'No overrides'
                    : `${config.overridden_fields.length} active`}
                </Badge>
              </div>
              <CardDescription>
                Overridden fields are called out next to the control itself. This section gives the
                full runtime lock list in one place.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              {config.overridden_fields.length === 0 ? (
                <Alert variant="success">
                  <AlertTitle>Runtime matches saved settings</AlertTitle>
                  <AlertDescription>
                    Operators can edit every dashboard-exposed setting. New saves will affect future
                    runs without any env-shadowed exceptions.
                  </AlertDescription>
                </Alert>
              ) : (
                <>
                  <Alert variant="warning">
                    <AlertTitle>Environment values still win at runtime</AlertTitle>
                    <AlertDescription>
                      These fields stay read-only here. The dashboard keeps the saved value visible
                      so you can see what will take over once the env override is removed.
                    </AlertDescription>
                  </Alert>
                  <div className="space-y-2">
                    {config.overridden_fields.map((field) => (
                      <div
                        key={field}
                        className="rounded-2xl border border-border bg-background/60 px-4 py-3"
                      >
                        <div className="flex flex-col gap-2 md:flex-row md:items-start md:justify-between">
                          <div className="space-y-1">
                            <div className="flex flex-wrap items-center gap-2">
                              <div className="font-medium">
                                {FRIENDLY_FIELD_LABELS[field] ?? field}
                              </div>
                              <Badge variant="warning">Runtime override</Badge>
                            </div>
                            <div className="text-xs text-muted-foreground break-all">{field}</div>
                          </div>
                          <div className="text-xs text-muted-foreground">
                            {(overrideSources[field] ?? []).join(', ') ||
                              'Environment source not reported.'}
                          </div>
                        </div>
                        <div className="mt-3 grid gap-2 text-xs sm:grid-cols-2">
                          <div className="rounded-xl border border-border/80 bg-card/80 px-3 py-2">
                            <div className="uppercase tracking-[0.16em] text-muted-foreground">
                              Saved config
                            </div>
                            <div className="mt-1 font-medium text-foreground">
                              {formatFieldValue(config, 'persisted_config', field)}
                            </div>
                          </div>
                          <div className="rounded-xl border border-amber-200/80 bg-amber-50/80 px-3 py-2 text-amber-900 dark:border-amber-900/60 dark:bg-amber-950/30 dark:text-amber-100">
                            <div className="uppercase tracking-[0.16em]">Runtime now</div>
                            <div className="mt-1 font-medium">
                              {formatFieldValue(config, 'effective_config', field)}
                            </div>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </>
              )}
            </CardContent>
          </Card>

          <Card className="border-border/80 bg-card/95">
            <CardHeader className="space-y-2">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <CardTitle className="text-base">Save and reset</CardTitle>
                  <CardDescription>
                    Save writes the persisted config used for future runs. Reset clears only the
                    draft state on this page.
                  </CardDescription>
                </div>
                <Badge variant={dirtyFieldCount > 0 ? 'info' : 'secondary'}>
                  {dirtyFieldCount > 0 ? `${dirtyFieldCount} unsaved` : 'No draft changes'}
                </Badge>
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              {banner ? (
                <Alert variant={banner.variant} className="py-2.5">
                  <AlertTitle>{banner.title}</AlertTitle>
                  <AlertDescription>{banner.description}</AlertDescription>
                </Alert>
              ) : (
                <Alert variant="default" className="py-2.5">
                  <AlertTitle>Current impact</AlertTitle>
                  <AlertDescription>
                    {dirtyFieldCount > 0
                      ? `Draft edits are ready for ${summarizeDirtyFields(dirtyFieldPaths)}. Saving updates the persisted config for future runs only.`
                      : 'The form currently matches the persisted config. Active runs keep the settings they started with.'}
                  </AlertDescription>
                </Alert>
              )}

              <div className="grid gap-3 rounded-2xl border border-border/80 bg-background/50 p-4 md:grid-cols-2">
                <div className="space-y-1.5 text-sm">
                  <div className="font-medium">Save</div>
                  <p className="text-muted-foreground">
                    Writes draft changes to the persisted config file. Runtime overrides remain in
                    charge until their environment values change.
                  </p>
                </div>
                <div className="space-y-1.5 text-sm">
                  <div className="font-medium">Reset</div>
                  <p className="text-muted-foreground">
                    Discards unsaved edits and validation messages in the browser. It does not touch
                    the saved config or any runtime environment value.
                  </p>
                </div>
              </div>

              <div className="flex flex-col gap-3 border-t border-border pt-4 sm:flex-row sm:items-center sm:justify-between">
                <p className="text-sm text-muted-foreground">
                  {config.overridden_fields.length > 0
                    ? `${config.overridden_fields.length} runtime ${pluralize(config.overridden_fields.length, 'override')} ${config.overridden_fields.length === 1 ? 'is' : 'are'} still active.`
                    : 'No runtime overrides are currently blocking dashboard edits.'}
                </p>
                <div className="flex gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={handleReset}
                    type="button"
                    disabled={
                      saving || (dirtyFieldCount === 0 && Object.keys(fieldErrors).length === 0)
                    }
                  >
                    Reset draft
                  </Button>
                  <Button
                    size="sm"
                    disabled={saving || dirtyFieldCount === 0}
                    onClick={handleSave}
                    type="button"
                  >
                    {saving ? 'Saving…' : 'Save settings'}
                  </Button>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>

        <aside className="space-y-5">
          <Card className="border-border/80 bg-card/95">
            <CardHeader>
              <CardTitle className="text-base">Operator guide</CardTitle>
              <CardDescription>
                Use the same rule set across normal settings and secrets.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-3 text-sm text-muted-foreground">
              <div className="rounded-2xl border border-border/80 bg-background/60 px-4 py-3">
                <div className="font-medium text-foreground">Editable fields</div>
                <p className="mt-1">Save writes the persisted config that future runs will load.</p>
              </div>
              <div className="rounded-2xl border border-border/80 bg-background/60 px-4 py-3">
                <div className="font-medium text-foreground">Runtime overrides</div>
                <p className="mt-1">
                  Read-only fields stay locked while environment values are active.
                </p>
              </div>
              <div className="rounded-2xl border border-border/80 bg-background/60 px-4 py-3">
                <div className="font-medium text-foreground">Secrets</div>
                <p className="mt-1">
                  Replace and clear flows stay masked and only update the saved config.
                </p>
              </div>
            </CardContent>
          </Card>

          <Card className="border-border/80 bg-card/95">
            <CardHeader>
              <CardTitle className="text-base">Navigation</CardTitle>
              <CardDescription>
                Return to the session workspace after finishing configuration updates.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <Link
                className={`${buttonVariants({ variant: 'outline', size: 'sm' })} w-full`}
                href="/"
              >
                Back to sessions
              </Link>
            </CardContent>
          </Card>
        </aside>
      </div>
    </div>
  )
}

function SummaryTile({
  eyebrow,
  title,
  description,
}: {
  eyebrow: string
  title: string
  description: string
}) {
  return (
    <div className="rounded-2xl border border-border bg-card/95 p-4 shadow-sm">
      <div className="text-[11px] uppercase tracking-[0.22em] text-muted-foreground">{eyebrow}</div>
      <div className="mt-2 text-base font-semibold text-foreground">{title}</div>
      <p className="mt-1 text-sm text-muted-foreground">{description}</p>
    </div>
  )
}

function SettingsSectionCard({
  title,
  description,
  totalCount,
  lockedCount,
  children,
}: {
  title: string
  description: string
  totalCount: number
  lockedCount: number
  children: ReactNode
}) {
  return (
    <Card className="border-border/80 bg-card/95">
      <CardHeader className="space-y-2">
        <div className="flex flex-wrap items-center gap-2">
          <CardTitle className="text-base">{title}</CardTitle>
          <Badge variant="secondary">{totalCount} fields</Badge>
          {lockedCount > 0 ? <Badge variant="warning">{lockedCount} locked</Badge> : null}
        </div>
        <CardDescription>{description}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">{children}</CardContent>
    </Card>
  )
}

function RouteField({
  definition,
  field,
  value,
  onChange,
  disabled,
  error,
  dirty,
  overriddenFields,
  config,
  overrideSources,
}: {
  definition: FieldDefinition
  field: string
  value: string
  onChange: (value: string) => void
  disabled: boolean
  error?: string
  dirty: boolean
  overriddenFields: Set<string>
  config: ConfigResponse
  overrideSources: Record<string, string[]>
}) {
  const overridden = overriddenFields.has(field)
  return (
    <SettingFieldShell
      label={definition.label}
      description={definition.description}
      error={error}
      overridden={overridden}
      dirty={dirty}
      draftValue={formatConfigValue(value)}
      effectiveValue={formatFieldValue(config, 'effective_config', field)}
      persistedValue={formatFieldValue(config, 'persisted_config', field)}
      overrideSource={overrideSources[field]}
    >
      <NativeSelect
        className="h-9"
        disabled={disabled || overridden}
        value={value}
        onChange={(event) => onChange(event.target.value)}
      >
        {ROUTE_OPTIONS.map((option) => (
          <option key={option} value={option}>
            {option}
          </option>
        ))}
      </NativeSelect>
    </SettingFieldShell>
  )
}
