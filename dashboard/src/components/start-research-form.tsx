'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { ChevronDown, ChevronUp, RotateCcw } from 'lucide-react'
import { startResearchRun } from '@/lib/api'
import type { ResearchRunRequest, AgentPromptOverride } from '@/types/telemetry'

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
  const [showAdvanced, setShowAdvanced] = useState(false)
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

      // Redirect to the live monitor route while the session is still running.
      router.push(`/session/${response.run_id}/monitor`)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to start research run')
      setIsSubmitting(false)
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div>
        <label htmlFor="query" className="block text-sm font-medium mb-2">
          Research Query
        </label>
        <textarea
          id="query"
          value={formData.query}
          onChange={(e) => setFormData((prev) => ({ ...prev, query: e.target.value }))}
          placeholder="What would you like to research?"
          className="w-full min-h-[100px] px-3 py-2 border rounded-md resize-y focus:outline-none focus:ring-2 focus:ring-primary"
          disabled={isSubmitting}
        />
      </div>

      <div className="flex flex-col gap-4">
        <div>
          <label htmlFor="depth" className="block text-sm font-medium mb-2">
            Research Depth
          </label>
          <select
            id="depth"
            value={formData.depth}
            onChange={(e) =>
              setFormData((prev) => ({ ...prev, depth: e.target.value as ResearchDepth }))
            }
            className="w-full px-3 py-2 border rounded-md focus:outline-none focus:ring-2 focus:ring-primary"
            disabled={isSubmitting}
          >
            <option value="quick">Quick (3-5 sources)</option>
            <option value="standard">Standard (10-15 sources)</option>
            <option value="deep">Deep (20+ sources)</option>
          </select>
        </div>

        <div>
          <label htmlFor="minSources" className="block text-sm font-medium mb-2">
            Minimum Sources (optional)
          </label>
          <input
            id="minSources"
            type="number"
            min="1"
            max="100"
            value={formData.minSources}
            onChange={(e) => setFormData((prev) => ({ ...prev, minSources: e.target.value }))}
            placeholder="Auto"
            className="w-full px-3 py-2 border rounded-md focus:outline-none focus:ring-2 focus:ring-primary"
            disabled={isSubmitting}
          />
        </div>
      </div>

      {/* Advanced Settings - Prompt Editor */}
      <div className="border rounded-md">
        <button
          type="button"
          onClick={() => setShowAdvanced(!showAdvanced)}
          className="w-full flex items-center justify-between px-4 py-3 text-sm font-medium text-left hover:bg-muted/50 transition-colors"
          disabled={isSubmitting}
        >
          <span>Advanced Settings (Agent Prompts)</span>
          {showAdvanced ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
        </button>

        {showAdvanced && (
          <div className="px-4 pb-4 space-y-4 border-t">
            <p className="text-sm text-muted-foreground pt-3">
              Customize prompts for LLM-backed agents. Prompt prefixes are prepended to the default
              prompts, allowing you to extend behavior without replacing defaults.
            </p>
            <p className="text-xs text-muted-foreground">
              V1 support is limited to Analyzer, Deep Analyzer, and Report Quality Evaluator.
            </p>

            {SUPPORTED_AGENTS.map((agent) => (
              <div key={agent.id} className="space-y-2">
                <div className="flex items-center justify-between">
                  <div>
                    <label htmlFor={`prompt-${agent.id}`} className="text-sm font-medium">
                      {agent.label} Prompt Prefix
                    </label>
                    <p className="text-xs text-muted-foreground">{agent.description}</p>
                  </div>
                  <button
                    type="button"
                    onClick={() => resetPromptPrefix(agent.id)}
                    className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground transition-colors"
                    disabled={isSubmitting}
                  >
                    <RotateCcw className="h-3 w-3" />
                    Reset
                  </button>
                </div>
                <textarea
                  id={`prompt-${agent.id}`}
                  value={promptPrefixes[agent.id]}
                  onChange={(e) => handlePromptPrefixChange(agent.id, e.target.value)}
                  placeholder={`Optional prefix to prepend to ${agent.label.toLowerCase()} prompts...`}
                  className="w-full min-h-[80px] px-3 py-2 border rounded-md resize-y text-sm focus:outline-none focus:ring-2 focus:ring-primary"
                  disabled={isSubmitting}
                />
              </div>
            ))}

            {hasPromptOverrides() && (
              <div className="p-2 bg-muted/50 rounded-md">
                <p className="text-xs text-muted-foreground">
                  <strong>Note:</strong> Prompt overrides will be applied to this research run and
                  recorded in session metadata.
                </p>
              </div>
            )}
          </div>
        )}
      </div>

      {error && (
        <div className="p-3 text-sm text-red-600 bg-red-50 border border-red-200 rounded-md">
          {error}
        </div>
      )}

      <button
        type="submit"
        disabled={isSubmitting || !formData.query.trim()}
        className="w-full py-2 px-4 bg-black text-white rounded-md hover:bg-black/90 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
      >
        {isSubmitting ? 'Starting Research...' : 'Start Research'}
      </button>
    </form>
  )
}
