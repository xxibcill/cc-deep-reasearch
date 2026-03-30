'use client'

import { useState } from 'react'
import { Loader2 } from 'lucide-react'
import { QuickScriptResultPanel } from '@/components/content-gen/quick-script-result-panel'
import { runScripting } from '@/lib/content-gen-api'
import {
  QUICK_SCRIPT_FIELDS,
  buildQuickScriptMarkdown,
  buildQuickScriptPrompt,
  mergeQuickScriptFields,
  parseQuickScriptMarkdown,
  type QuickScriptFields,
} from '@/lib/quick-script'
import type { RunScriptingRequest, RunScriptingResponse } from '@/types/content-gen'

interface QuickScriptFormProps {
  onSuccess?: () => void
  initialValues?: Partial<QuickScriptFields> | null
}

type RunMode = 'default' | 'single_pass' | 'iterative'
type QuickScriptRoute = 'default' | 'anthropic' | 'openrouter' | 'cerebras' | 'heuristic'

const QUICK_SCRIPT_ROUTE_OPTIONS: Array<{
  value: QuickScriptRoute
  label: string
}> = [
  { value: 'default', label: 'Workspace default' },
  { value: 'anthropic', label: 'Anthropic' },
  { value: 'openrouter', label: 'OpenRouter' },
  { value: 'cerebras', label: 'Cerebras' },
  { value: 'heuristic', label: 'Heuristic' },
]

export function QuickScriptForm({ onSuccess, initialValues }: QuickScriptFormProps) {
  const [fields, setFields] = useState(() => mergeQuickScriptFields(initialValues))
  const [runMode, setRunMode] = useState<RunMode>('default')
  const [selectedRoute, setSelectedRoute] = useState<QuickScriptRoute>('default')
  const [maxIterations, setMaxIterations] = useState('3')
  const [result, setResult] = useState<RunScriptingResponse | null>(null)
  const [isRunning, setIsRunning] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [progress, setProgress] = useState<string | null>(null)
  const [markdownDraft, setMarkdownDraft] = useState('')
  const [markdownStatus, setMarkdownStatus] = useState<string | null>(null)

  const isValid = fields.raw_idea.trim().length > 0
  const markdownValue = buildQuickScriptMarkdown(fields)

  const handleRun = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!isValid) return

    const prompt = buildQuickScriptPrompt(fields)
    const request: RunScriptingRequest = { idea: prompt }
    if (selectedRoute !== 'default') {
      request.llm_route = selectedRoute
    }
    if (runMode === 'single_pass') {
      request.iterative_mode = false
    } else if (runMode === 'iterative') {
      request.iterative_mode = true
      request.max_iterations = Number(maxIterations)
    }

    setIsRunning(true)
    setError(null)
    setResult(null)
    setProgress(
      runMode === 'iterative'
        ? `Running iterative scripting pipeline (up to ${maxIterations} passes)...`
        : runMode === 'single_pass'
          ? 'Running single-pass scripting pipeline...'
          : 'Running scripting pipeline using workspace iteration settings...'
    )

    try {
      const response = await runScripting(request)
      setResult(response)
      setProgress(null)
      onSuccess?.()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Scripting failed')
      setProgress(null)
    } finally {
      setIsRunning(false)
    }
  }

  const setField = (key: string, value: string) =>
    setFields((prev) => ({ ...prev, [key]: value }))

  const handleCopyMarkdown = async () => {
    setMarkdownStatus(null)

    if (!markdownValue.trim()) {
      setMarkdownStatus('Add at least one field before exporting Markdown.')
      return
    }

    setMarkdownDraft(markdownValue)

    try {
      await navigator.clipboard.writeText(markdownValue)
      setMarkdownStatus('Copied Markdown to clipboard.')
    } catch {
      setMarkdownStatus('Clipboard was unavailable. Copy the Markdown from the box below.')
    }
  }

  const handleApplyMarkdown = () => {
    if (!markdownDraft.trim()) {
      setMarkdownStatus('Paste Markdown into the box first.')
      return
    }

    setFields(parseQuickScriptMarkdown(markdownDraft))
    setMarkdownStatus('Applied Markdown to the form.')
  }

  const showCustomIterations = runMode === 'iterative'

  return (
    <form onSubmit={handleRun} className="space-y-4">
      <div className="space-y-3 rounded-sm border border-border bg-background px-4 py-3">
        <div className="space-y-1">
          <p className="text-xs font-mono uppercase tracking-wider text-muted-foreground">
            Run controls
          </p>
          <p className="text-sm text-muted-foreground">
            Choose the scripting route and whether this run follows the workspace default, forces one pass, or uses iterative refinement.
          </p>
        </div>
        <div className="grid gap-3 md:grid-cols-3">
          <label className="block text-xs font-mono uppercase tracking-wider text-muted-foreground">
            LLM route
            <select
              value={selectedRoute}
              onChange={(e) => setSelectedRoute(e.target.value as QuickScriptRoute)}
              className="mt-1.5 h-10 w-full rounded-sm border border-border bg-background px-3 text-sm text-foreground"
              disabled={isRunning}
            >
              {QUICK_SCRIPT_ROUTE_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>

          <label className="block text-xs font-mono uppercase tracking-wider text-muted-foreground">
            Iteration mode
            <select
              value={runMode}
              onChange={(e) => setRunMode(e.target.value as RunMode)}
              className="mt-1.5 h-10 w-full rounded-sm border border-border bg-background px-3 text-sm text-foreground"
              disabled={isRunning}
            >
              <option value="default">Workspace default</option>
              <option value="single_pass">Single pass</option>
              <option value="iterative">Iterative refinement</option>
            </select>
          </label>

          {showCustomIterations && (
            <label className="block text-xs font-mono uppercase tracking-wider text-muted-foreground">
              Max iterations
              <select
                value={maxIterations}
                onChange={(e) => setMaxIterations(e.target.value)}
                className="mt-1.5 h-10 w-full rounded-sm border border-border bg-background px-3 text-sm text-foreground"
                disabled={isRunning}
              >
                {[1, 2, 3, 4, 5].map((count) => (
                  <option key={count} value={String(count)}>
                    {count}
                  </option>
                ))}
              </select>
            </label>
          )}
        </div>
        <p className="text-xs leading-relaxed text-muted-foreground">
          The selected route becomes this run&apos;s primary transport. If that route is unavailable, the backend can still fall back according to workspace routing rules.
        </p>
      </div>

      <div className="space-y-3 rounded-sm border border-border bg-background px-4 py-3">
        <div className="space-y-1">
          <p className="text-xs font-mono uppercase tracking-wider text-muted-foreground">
            Markdown transfer
          </p>
          <p className="text-sm text-muted-foreground">
            Copy the current scripting inputs as Markdown, or paste Markdown here to refill the form.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            onClick={handleCopyMarkdown}
            className="rounded-sm border border-border bg-surface px-3 py-2 text-sm text-foreground/80 transition-colors hover:bg-surface-raised hover:text-foreground"
            disabled={isRunning}
          >
            Copy as Markdown
          </button>
          <button
            type="button"
            onClick={handleApplyMarkdown}
            className="rounded-sm border border-border bg-surface px-3 py-2 text-sm text-foreground/80 transition-colors hover:bg-surface-raised hover:text-foreground"
            disabled={isRunning}
          >
            Apply Pasted Markdown
          </button>
        </div>
        <textarea
          value={markdownDraft}
          onChange={(e) => setMarkdownDraft(e.target.value)}
          placeholder={`# Quick Script Input

## Raw idea
What the video is about

## Target audience
Who this is for`}
          rows={8}
          className="w-full px-3 py-2 bg-background border border-border rounded-sm text-sm font-mono resize-y
            focus:outline-none focus:border-warning/50 focus:ring-1 focus:ring-warning/20
            placeholder:text-muted-foreground/40 transition-colors"
          disabled={isRunning}
        />
        {markdownStatus && (
          <div className="text-sm text-muted-foreground">
            {markdownStatus}
          </div>
        )}
      </div>

      {QUICK_SCRIPT_FIELDS.map((f) => (
        <div key={f.key}>
          <label
            htmlFor={`qs-${f.key}`}
            className="block text-xs font-mono uppercase tracking-wider text-muted-foreground mb-1.5"
          >
            {f.label}
            {f.required && <span className="text-warning ml-0.5">*</span>}
          </label>
          <textarea
            id={`qs-${f.key}`}
            value={fields[f.key]}
            onChange={(e) => setField(f.key, e.target.value)}
            placeholder={f.placeholder}
            rows={f.rows ?? 1}
            className="w-full px-3 py-2 bg-background border border-border rounded-sm text-sm resize-y
              focus:outline-none focus:border-warning/50 focus:ring-1 focus:ring-warning/20
              placeholder:text-muted-foreground/40 transition-colors"
            disabled={isRunning}
          />
        </div>
      ))}

      <button
        type="submit"
        disabled={isRunning || !isValid}
        className="flex items-center gap-2 px-4 py-2.5 bg-warning/15 border border-warning/30 text-warning rounded-sm text-sm font-medium font-display
          hover:bg-warning/25 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
      >
        {isRunning ? (
          <>
            <Loader2 className="h-4 w-4 animate-spin" />
            Running...
          </>
        ) : (
          'Generate Script'
        )}
      </button>

      {progress && (
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin text-warning" />
          {progress}
        </div>
      )}

      {error && (
        <div className="whitespace-pre-wrap break-words text-sm text-error bg-error-muted/20 border border-error/20 rounded-sm px-3 py-2">
          {error}
        </div>
      )}

      {result && (
        <div className="space-y-3 animate-fade-in pt-2 border-t border-border">
          <QuickScriptResultPanel result={result} />
        </div>
      )}
    </form>
  )
}
