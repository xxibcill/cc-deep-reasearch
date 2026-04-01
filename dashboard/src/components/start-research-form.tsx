'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { RotateCcw } from 'lucide-react'
import { startResearchRun } from '@/lib/api'
import type { ResearchRunRequest, AgentPromptOverride } from '@/types/telemetry'

import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { NativeSelect } from '@/components/ui/native-select'
import { Accordion, AccordionItem, AccordionTrigger, AccordionContent } from '@/components/ui/accordion'
import { Alert, AlertDescription } from '@/components/ui/alert'

type ResearchDepth = 'quick' | 'standard' | 'deep'

interface FormData {
  query: string
  depth: ResearchDepth
  minSources: string
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

export function StartResearchForm() {
  const router = useRouter()
  const [formData, setFormData] = useState<FormData>({
    query: '',
    depth: 'deep',
    minSources: '',
  })
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [accordionValue, setAccordionValue] = useState('')
  const [promptPrefixes, setPromptPrefixes] = useState<Record<string, string>>({
    analyzer: '',
    deep_analyzer: '',
    report_quality_evaluator: '',
  })

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

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!formData.query.trim()) {
      setError('Please enter a research query')
      return
    }

    setIsSubmitting(true)
    setError(null)

    try {
      const request: ResearchRunRequest = {
        query: formData.query.trim(),
        depth: formData.depth,
        min_sources: formData.minSources ? parseInt(formData.minSources, 10) : null,
        realtime_enabled: true,
        agent_prompt_overrides: buildPromptOverrides(),
      }

      const response = await startResearchRun(request)

      router.push(`/session/${response.run_id}/monitor`)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to start research run')
      setIsSubmitting(false)
    }
  }

  const handleReset = () => {
    setFormData({
      query: '',
      depth: 'deep',
      minSources: '',
    })
    setPromptPrefixes({
      analyzer: '',
      deep_analyzer: '',
      report_quality_evaluator: '',
    })
    setError(null)
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div className="space-y-2">
        <Label htmlFor="query">Research Query</Label>
        <Textarea
          id="query"
          value={formData.query}
          onChange={(e) => setFormData((prev) => ({ ...prev, query: e.target.value }))}
          placeholder="What would you like to research?"
          className="min-h-[100px] resize-y"
          disabled={isSubmitting}
        />
      </div>

      <div className="flex flex-col gap-4">
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
            <option value="quick">Quick (3-5 sources)</option>
            <option value="standard">Standard (10-15 sources)</option>
            <option value="deep">Deep (20+ sources)</option>
          </NativeSelect>
        </div>

        <div className="space-y-2">
          <Label htmlFor="minSources">Minimum Sources (optional)</Label>
          <Input
            id="minSources"
            type="number"
            min="1"
            max="100"
            value={formData.minSources}
            onChange={(e) => setFormData((prev) => ({ ...prev, minSources: e.target.value }))}
            placeholder="Auto"
            disabled={isSubmitting}
          />
        </div>
      </div>

      <Accordion
        value={accordionValue}
        onValueChange={setAccordionValue}
      >
        <AccordionItem value="advanced">
          <AccordionTrigger value="advanced">Advanced Settings (Agent Prompts)</AccordionTrigger>
          <AccordionContent value="advanced">
            <div className="space-y-4">
              <p className="text-sm text-muted-foreground">
                Customize prompts for LLM-backed agents. Prompt prefixes are prepended to the
                default prompts, allowing you to extend behavior without replacing defaults.
              </p>
              <p className="text-xs text-muted-foreground">
                V1 support is limited to Analyzer, Deep Analyzer, and Report Quality Evaluator.
              </p>

              {SUPPORTED_AGENTS.map((agent) => (
                <div key={agent.id} className="space-y-2">
                  <div className="flex items-center justify-between">
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
                      <RotateCcw className="h-3 w-3 mr-1" />
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

              {hasPromptOverrides() && (
                <Alert variant="warning">
                  <AlertDescription>
                    <strong>Note:</strong> Prompt overrides will be applied to this research run
                    and recorded in session metadata.
                  </AlertDescription>
                </Alert>
              )}
            </div>
          </AccordionContent>
        </AccordionItem>
      </Accordion>

      {error && (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      <div className="flex gap-2">
        <Button type="submit" className="flex-1" disabled={isSubmitting || !formData.query.trim()}>
          {isSubmitting ? 'Starting Research...' : 'Start Research'}
        </Button>
        <Button
          type="button"
          variant="outline"
          onClick={handleReset}
          disabled={isSubmitting}
        >
          Reset
        </Button>
      </div>
    </form>
  )
}
