'use client'

import { useState, useEffect } from 'react'
import { Radar, RotateCcw, SearchCheck, Telescope, Sparkles } from 'lucide-react'
import { startResearchRun, listResearchThemes, getApiErrorMessage } from '@/lib/api'
import type { ResearchRunRequest, AgentPromptOverride } from '@/types/telemetry'

import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from '@/components/ui/accordion'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { NativeSelect } from '@/components/ui/native-select'
import { storePendingNotification, useNotifications } from '@/components/ui/notification-center'
import { Textarea } from '@/components/ui/textarea'

type ResearchDepth = 'quick' | 'standard' | 'deep'
type LaunchPresetId = 'factual' | 'standard' | 'deep'
type WorkflowType = 'staged' | 'planner'

interface FormData {
  query: string
  presetId: LaunchPresetId
  depth: ResearchDepth
  minSources: string
  theme: string | null
  workflow: WorkflowType
}

interface LaunchPreset {
  id: LaunchPresetId
  label: string
  description: string
  guidance: string
  depth: ResearchDepth
  minSources: string
  icon: typeof SearchCheck
}

const SUPPORTED_AGENTS = [
  { id: 'analyzer', label: 'Analyzer', description: 'Theme extraction and findings synthesis' },
  { id: 'deep_analyzer', label: 'Deep Analyzer', description: 'Multi-pass deep analysis' },
  {
    id: 'report_quality_evaluator',
    label: 'Report Quality Evaluator',
    description: 'Report quality assessment',
  },
] as const

const DEFAULT_PROMPT_PREFIXES: Record<string, string> = {
  analyzer: '',
  deep_analyzer: '',
  report_quality_evaluator: '',
}

const LAUNCH_PRESETS: LaunchPreset[] = [
  {
    id: 'factual',
    label: 'Quick factual check',
    description: 'Fast verification for a claim, update, or short question.',
    guidance: 'Use this when the operator mainly needs a confident answer fast.',
    depth: 'quick',
    minSources: '3',
    icon: SearchCheck,
  },
  {
    id: 'standard',
    label: 'Standard research pass',
    description: 'Balanced coverage for most day-to-day research requests.',
    guidance: 'This is the default path for a normal investigation with moderate scrutiny.',
    depth: 'standard',
    minSources: '8',
    icon: Radar,
  },
  {
    id: 'deep',
    label: 'Deep investigation',
    description: 'Broader collection and more synthesis room for complex topics.',
    guidance: 'Use this when the question is ambiguous, contested, or high stakes.',
    depth: 'deep',
    minSources: '15',
    icon: Telescope,
  },
]

const DEFAULT_PRESET = LAUNCH_PRESETS[1]
const MAX_QUERY_LENGTH = 2000

export function StartResearchForm() {
  const { notify } = useNotifications()
  const [formData, setFormData] = useState<FormData>({
    query: '',
    presetId: DEFAULT_PRESET.id,
    depth: DEFAULT_PRESET.depth,
    minSources: DEFAULT_PRESET.minSources,
    theme: null,
    workflow: 'staged',
  })
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [queryTouched, setQueryTouched] = useState(false)
  const [sourcesError, setSourcesError] = useState<string | null>(null)
  const [planAccordionValue, setPlanAccordionValue] = useState('')
  const [advancedAccordionValue, setAdvancedAccordionValue] = useState('')
  const [promptPrefixes, setPromptPrefixes] = useState<Record<string, string>>({
    analyzer: '',
    deep_analyzer: '',
    report_quality_evaluator: '',
  })
  const [themes, setThemes] = useState<{ theme: string; display_name: string; description: string }[]>([])
  const [themesLoading, setThemesLoading] = useState(true)

  useEffect(() => {
    let mounted = true
    const loadThemes = async () => {
      try {
        const data = await listResearchThemes()
        if (mounted) {
          setThemes(data.themes)
        }
      } catch (err) {
        console.error('Failed to load themes:', err)
      } finally {
        if (mounted) {
          setThemesLoading(false)
        }
      }
    }
    void loadThemes()
    return () => {
      mounted = false
    }
  }, [])

  const handlePromptPrefixChange = (agentId: string, value: string) => {
    setPromptPrefixes((prev) => ({
      ...prev,
      [agentId]: value,
    }))
  }

  const resetPromptPrefix = (agentId: string) => {
    setPromptPrefixes((prev) => ({
      ...prev,
      [agentId]: DEFAULT_PROMPT_PREFIXES[agentId],
    }))
  }

  const hasPromptOverrides = () => {
    return Object.values(promptPrefixes).some((prefix) => prefix.trim().length > 0)
  }

  const buildPromptOverrides = (): Record<string, AgentPromptOverride> | undefined => {
    if (!hasPromptOverrides()) {
      return undefined
    }

    const overrides: Record<string, AgentPromptOverride> = {}
    for (const [agentId, prefix] of Object.entries(promptPrefixes)) {
      if (prefix.trim()) {
        overrides[agentId] = {
          prompt_prefix: prefix.trim(),
        }
      }
    }
    return Object.keys(overrides).length > 0 ? overrides : undefined
  }

  const validateSources = (value: string) => {
    if (!value) {
      setSourcesError(null)
      return
    }
    const num = parseInt(value, 10)
    if (Number.isNaN(num) || num < 1 || num > 100) {
      setSourcesError('Must be between 1 and 100')
    } else {
      setSourcesError(null)
    }
  }

  const applyPreset = (preset: LaunchPreset) => {
    setFormData((prev) => ({
      ...prev,
      presetId: preset.id,
      depth: preset.depth,
      minSources: preset.minSources,
    }))
    validateSources(preset.minSources)
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setQueryTouched(true)

    if (!formData.query.trim()) {
      setError('Please enter a research query')
      return
    }

    if (sourcesError) return

    setIsSubmitting(true)
    setError(null)

    try {
      const request: ResearchRunRequest = {
        query: formData.query.trim(),
        depth: formData.depth,
        min_sources: formData.minSources ? parseInt(formData.minSources, 10) : null,
        realtime_enabled: true,
        theme: formData.theme,
        agent_prompt_overrides: buildPromptOverrides(),
        workflow: formData.workflow,
      }

      const response = await startResearchRun(request)
      const monitorHref = `/session/${response.run_id}/monitor`
      storePendingNotification({
        variant: 'success',
        durationMs: 10000,
        title: response.status === 'queued' ? 'Run queued' : 'Run started',
        description: `Opened monitor for ${response.run_id}. The dashboard will keep polling until the run settles.`,
        actions: [
          {
            label: 'Open monitor',
            href: monitorHref,
          },
        ],
      })
      window.location.assign(monitorHref)
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to start research run'
      setError(null)
      notify({
        variant: 'destructive',
        persistent: true,
        title: 'Run launch failed',
        description: message,
      })
      setIsSubmitting(false)
    }
  }

  const handleReset = () => {
    setFormData({
      query: '',
      presetId: DEFAULT_PRESET.id,
      depth: DEFAULT_PRESET.depth,
      minSources: DEFAULT_PRESET.minSources,
      theme: null,
      workflow: 'staged',
    })
    setPromptPrefixes({
      analyzer: '',
      deep_analyzer: '',
      report_quality_evaluator: '',
    })
    setError(null)
    setQueryTouched(false)
    setSourcesError(null)
    setPlanAccordionValue('')
    setAdvancedAccordionValue('')
  }

  const selectedPreset =
    LAUNCH_PRESETS.find((preset) => preset.id === formData.presetId) ?? DEFAULT_PRESET
  const presetTuned =
    selectedPreset.depth !== formData.depth || selectedPreset.minSources !== formData.minSources
  const promptOverrideCount = Object.values(promptPrefixes).filter((prefix) => prefix.trim()).length
  const queryEmpty = queryTouched && !formData.query.trim()

  return (
    <form onSubmit={handleSubmit} className="space-y-5">
      <div className="space-y-3">
        <div className="space-y-1">
          <Label>Launch Preset</Label>
          <p className="text-sm leading-6 text-muted-foreground">
            Start with the operator path that matches the question, then expose more controls only
            if the run needs them.
          </p>
        </div>

        <div className="grid gap-3">
          {LAUNCH_PRESETS.map((preset) => {
            const Icon = preset.icon
            const isActive = formData.presetId === preset.id

            return (
              <button
                key={preset.id}
                type="button"
                aria-pressed={isActive}
                onClick={() => applyPreset(preset)}
                className={`rounded-[1rem] border p-4 text-left transition-all ${
                  isActive
                    ? 'border-primary/45 bg-primary/[0.08] shadow-card'
                    : 'border-border/80 bg-surface/62 hover:border-primary/25 hover:bg-surface-raised/72'
                }`}
              >
                <div className="flex items-start justify-between gap-4">
                  <div className="space-y-2">
                    <div className="flex flex-wrap items-center gap-2">
                      <Icon className={`h-4 w-4 ${isActive ? 'text-primary' : 'text-muted-foreground'}`} />
                      <span className="font-display text-[0.95rem] font-semibold uppercase tracking-[0.1em] text-foreground">
                        {preset.label}
                      </span>
                    </div>
                    <p className="text-sm text-foreground">{preset.description}</p>
                    <p className="text-xs leading-5 text-muted-foreground">{preset.guidance}</p>
                  </div>
                  <div className="flex flex-col items-end gap-2 text-right">
                    <Badge variant={isActive ? 'info' : 'outline'}>{preset.depth}</Badge>
                    <span className="text-[0.72rem] uppercase tracking-[0.14em] text-muted-foreground">
                      Min {preset.minSources} sources
                    </span>
                  </div>
                </div>
              </button>
            )
          })}
        </div>

        <Alert variant="info" className="rounded-[1rem]">
          <AlertDescription className="space-y-1">
            <div className="font-medium text-foreground">{selectedPreset.label}</div>
            <div>
              Default plan: <span className="capitalize">{selectedPreset.depth}</span> depth with a{' '}
              {selectedPreset.minSources}-source floor.
              {presetTuned ? ' Research plan details have been customized from the preset.' : ''}
            </div>
          </AlertDescription>
        </Alert>
      </div>

      <div className="space-y-2">
        <Label htmlFor="query">Research Query</Label>
        <Textarea
          id="query"
          value={formData.query}
          onChange={(e) => {
            setFormData((prev) => ({ ...prev, query: e.target.value }))
            if (queryTouched && e.target.value.trim()) setError(null)
          }}
          onBlur={() => setQueryTouched(true)}
          placeholder="What would you like to research, verify, or investigate?"
          className="min-h-[100px] resize-y"
          disabled={isSubmitting}
          aria-invalid={queryEmpty}
        />
        <div className="flex items-center justify-between text-xs">
          {queryEmpty ? (
            <span className="text-error">A research query is required</span>
          ) : (
            <span className="text-muted-foreground">
              Lead with the core question. Add context or constraints after that.
            </span>
          )}
          <span className={formData.query.length > MAX_QUERY_LENGTH ? 'text-error' : 'text-muted-foreground'}>
            {formData.query.length}/{MAX_QUERY_LENGTH}
          </span>
        </div>
      </div>

      <Accordion value={planAccordionValue} onValueChange={setPlanAccordionValue}>
        <AccordionItem value="plan">
          <AccordionTrigger value="plan">Research Plan Details</AccordionTrigger>
          <AccordionContent value="plan">
            <div className="space-y-4">
              <p className="text-sm leading-6 text-muted-foreground">
                Override the preset only when the investigation needs a different evidence budget
                or a stricter source floor.
              </p>

              <div className="grid gap-4">
                <div className="space-y-2">
                  <Label htmlFor="depth">Research Depth</Label>
                  <NativeSelect
                    id="depth"
                    value={formData.depth}
                    onChange={(e) =>
                      setFormData((prev) => ({ ...prev, depth: e.target.value as ResearchDepth }))
                    }
                    disabled={isSubmitting}
                  >
                    <option value="quick">Quick: fastest pass with lighter evidence gathering</option>
                    <option value="standard">Standard: balanced coverage and synthesis</option>
                    <option value="deep">Deep: broader collection for higher-scrutiny topics</option>
                  </NativeSelect>
                </div>

                <div className="space-y-2">
                  <Label htmlFor="workflow">Workflow</Label>
                  <NativeSelect
                    id="workflow"
                    value={formData.workflow}
                    onChange={(e) =>
                      setFormData((prev) => ({ ...prev, workflow: e.target.value as WorkflowType }))
                    }
                    disabled={isSubmitting}
                  >
                    <option value="staged">Staged: sequential phase execution (default)</option>
                    <option value="planner">Planner: task-graph decomposition (beta)</option>
                  </NativeSelect>
                  <p className="text-xs text-muted-foreground">
                    Planner is an opt-in beta workflow using hierarchical task decomposition.
                  </p>
                </div>

                <div className="space-y-2">
                  <Label htmlFor="minSources">Minimum Sources</Label>
                  <Input
                    id="minSources"
                    type="number"
                    min="1"
                    max="100"
                    value={formData.minSources}
                    onChange={(e) => {
                      setFormData((prev) => ({ ...prev, minSources: e.target.value }))
                      validateSources(e.target.value)
                    }}
                    onBlur={() => validateSources(formData.minSources)}
                    placeholder="Auto"
                    disabled={isSubmitting}
                    aria-invalid={Boolean(sourcesError)}
                  />
                  {sourcesError ? (
                    <p className="text-xs text-error">{sourcesError}</p>
                  ) : (
                    <p className="text-xs text-muted-foreground">
                      Leave blank to let the backend decide the source floor automatically.
                    </p>
                  )}
                </div>

                <div className="space-y-2">
                  <Label htmlFor="theme">Research Theme</Label>
                  <NativeSelect
                    id="theme"
                    value={formData.theme ?? ''}
                    onChange={(e) =>
                      setFormData((prev) => ({
                        ...prev,
                        theme: e.target.value || null,
                      }))
                    }
                    disabled={isSubmitting || themesLoading}
                  >
                    <option value="">Auto-detect from query</option>
                    {themes.map((t) => (
                      <option key={t.theme} value={t.theme}>
                        {t.display_name}
                      </option>
                    ))}
                  </NativeSelect>
                  {formData.theme && (
                    <p className="text-xs text-muted-foreground">
                      Theme: {themes.find((t) => t.theme === formData.theme)?.description}
                    </p>
                  )}
                </div>
              </div>
            </div>
          </AccordionContent>
        </AccordionItem>
      </Accordion>

      <Accordion value={advancedAccordionValue} onValueChange={setAdvancedAccordionValue}>
        <AccordionItem value="advanced">
          <AccordionTrigger value="advanced">
            Operator Prompt Overrides {promptOverrideCount > 0 ? `(${promptOverrideCount})` : ''}
          </AccordionTrigger>
          <AccordionContent value="advanced">
            <div className="space-y-4">
              <Alert className="rounded-[0.95rem]">
                <AlertDescription className="text-sm leading-6 text-muted-foreground">
                  Prompt prefixes are prepended to the default agent instructions. Treat them as
                  advanced operator tooling for steering or debugging, not the normal path.
                </AlertDescription>
              </Alert>

              <p className="text-xs text-muted-foreground">
                V1 support is limited to Analyzer, Deep Analyzer, and Report Quality Evaluator.
              </p>

              {SUPPORTED_AGENTS.map((agent) => (
                <div key={agent.id} className="space-y-2">
                  <div className="flex items-center justify-between gap-3">
                    <div>
                      <Label htmlFor={`prompt-${agent.id}`} className="text-sm font-medium">
                        {agent.label} Prompt Prefix
                      </Label>
                      <p className="text-xs text-muted-foreground">{agent.description}</p>
                    </div>
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      onClick={() => resetPromptPrefix(agent.id)}
                      disabled={isSubmitting}
                    >
                      <RotateCcw className="mr-1 h-3 w-3" />
                      Reset
                    </Button>
                  </div>
                  <Textarea
                    id={`prompt-${agent.id}`}
                    value={promptPrefixes[agent.id]}
                    onChange={(e) => handlePromptPrefixChange(agent.id, e.target.value)}
                    placeholder={`Optional prefix to prepend to ${agent.label.toLowerCase()} prompts...`}
                    className="min-h-[80px] resize-y text-sm"
                    disabled={isSubmitting}
                  />
                </div>
              ))}

              {hasPromptOverrides() ? (
                <Alert variant="warning">
                  <AlertDescription>
                    Prompt overrides will be sent with this run and recorded in session metadata.
                  </AlertDescription>
                </Alert>
              ) : null}
            </div>
          </AccordionContent>
        </AccordionItem>
      </Accordion>

      {error ? (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      ) : null}

      <div className="flex items-center gap-2">
        <Button type="submit" className="flex-1" disabled={isSubmitting || !formData.query.trim()}>
          {isSubmitting ? 'Starting Research...' : `Start ${selectedPreset.label}`}
        </Button>
        <Button
          type="button"
          variant="ghost"
          size="sm"
          onClick={handleReset}
          disabled={isSubmitting}
          className="text-muted-foreground"
        >
          <RotateCcw className="mr-1 h-3.5 w-3.5" />
          Clear
        </Button>
      </div>
    </form>
  )
}
