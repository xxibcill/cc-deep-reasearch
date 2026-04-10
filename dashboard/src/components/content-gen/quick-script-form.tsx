'use client'

import { useEffect, useState } from 'react'
import { Loader2 } from 'lucide-react'

import { QuickScriptResultPanel } from '@/components/content-gen/quick-script-result-panel'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { FormDescription, FormField, FormLabel, FormMessage } from '@/components/ui/form-field'
import { NativeSelect } from '@/components/ui/native-select'
import { Textarea } from '@/components/ui/textarea'
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
  const showCustomIterations = runMode === 'iterative'

  useEffect(() => {
    setFields(mergeQuickScriptFields(initialValues))
    setResult(null)
    setError(null)
    setProgress(null)
    setMarkdownDraft('')
    setMarkdownStatus(null)
  }, [initialValues])

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
          : 'Running scripting pipeline using workspace iteration settings...',
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

  const setField = (key: string, value: string) => {
    setFields((prev) => ({ ...prev, [key]: value }))
  }

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

  return (
    <form onSubmit={handleRun} className="space-y-5">
      <Card className="rounded-xl border-border bg-card/95 shadow-sm">
        <CardHeader className="space-y-2 pb-4">
          <CardTitle className="text-base">Run controls</CardTitle>
          <CardDescription>
            Choose the route and iteration behavior for this scripting run. The backend can still
            fall back according to workspace routing rules if the selected transport is unavailable.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-4 md:grid-cols-3">
            <FormField>
              <FormLabel htmlFor="quick-script-route">LLM route</FormLabel>
              <NativeSelect
                id="quick-script-route"
                value={selectedRoute}
                onChange={(e) => setSelectedRoute(e.target.value as QuickScriptRoute)}
                disabled={isRunning}
              >
                {QUICK_SCRIPT_ROUTE_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </NativeSelect>
            </FormField>

            <FormField>
              <FormLabel htmlFor="quick-script-mode">Iteration mode</FormLabel>
              <NativeSelect
                id="quick-script-mode"
                value={runMode}
                onChange={(e) => setRunMode(e.target.value as RunMode)}
                disabled={isRunning}
              >
                <option value="default">Workspace default</option>
                <option value="single_pass">Single pass</option>
                <option value="iterative">Iterative refinement</option>
              </NativeSelect>
            </FormField>

            {showCustomIterations ? (
              <FormField>
                <FormLabel htmlFor="quick-script-iterations">Max iterations</FormLabel>
                <NativeSelect
                  id="quick-script-iterations"
                  value={maxIterations}
                  onChange={(e) => setMaxIterations(e.target.value)}
                  disabled={isRunning}
                >
                  {[1, 2, 3, 4, 5].map((count) => (
                    <option key={count} value={String(count)}>
                      {count}
                    </option>
                  ))}
                </NativeSelect>
              </FormField>
            ) : (
              <div className="hidden md:block" />
            )}
          </div>
        </CardContent>
      </Card>

      <Card className="rounded-xl border-border bg-card/95 shadow-sm">
        <CardHeader className="space-y-2 pb-4">
          <CardTitle className="text-base">Markdown transfer</CardTitle>
          <CardDescription>
            Copy the current inputs as Markdown or paste Markdown here to refill the form.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex flex-wrap gap-2">
            <Button type="button" variant="outline" onClick={handleCopyMarkdown} disabled={isRunning}>
              Copy as Markdown
            </Button>
            <Button type="button" variant="outline" onClick={handleApplyMarkdown} disabled={isRunning}>
              Apply pasted Markdown
            </Button>
          </div>

          <FormField>
            <FormLabel htmlFor="quick-script-markdown">Markdown draft</FormLabel>
            <Textarea
              id="quick-script-markdown"
              value={markdownDraft}
              onChange={(e) => setMarkdownDraft(e.target.value)}
              placeholder={`# Quick Script Input

## Raw idea
What the video is about

## Target audience
Who this is for`}
              rows={8}
              className="font-mono"
              disabled={isRunning}
            />
            {markdownStatus ? <FormMessage>{markdownStatus}</FormMessage> : null}
          </FormField>
        </CardContent>
      </Card>

      {QUICK_SCRIPT_FIELDS.map((field) => (
        <FormField key={field.key}>
          <FormLabel htmlFor={`qs-${field.key}`} required={field.required}>
            {field.label}
          </FormLabel>
          {field.key === 'raw_idea' ? (
            <FormDescription>
              This is the only required field. Everything else is optional guidance for the script
              generator.
            </FormDescription>
          ) : null}
          <Textarea
            id={`qs-${field.key}`}
            value={fields[field.key]}
            onChange={(e) => setField(field.key, e.target.value)}
            placeholder={field.placeholder}
            rows={field.rows ?? 1}
            className="resize-y"
            disabled={isRunning}
          />
        </FormField>
      ))}

      <Button
        type="submit"
        disabled={isRunning || !isValid}
        className="bg-warning text-background hover:bg-warning/90"
      >
        {isRunning ? (
          <>
            <Loader2 className="h-4 w-4 animate-spin" />
            Running...
          </>
        ) : (
          'Generate Script'
        )}
      </Button>

      {progress ? (
        <Alert variant="warning" className="flex items-start gap-3">
          <Loader2 className="mt-0.5 h-4 w-4 shrink-0 animate-spin" />
          <div className="space-y-1">
            <AlertTitle>Running scripting</AlertTitle>
            <AlertDescription>{progress}</AlertDescription>
          </div>
        </Alert>
      ) : null}

      {error ? (
        <Alert variant="destructive">
          <AlertTitle>Scripting failed</AlertTitle>
          <AlertDescription className="whitespace-pre-wrap break-words">{error}</AlertDescription>
        </Alert>
      ) : null}

      {result ? (
        <div className="space-y-3 border-t border-border pt-2 animate-fade-in">
          <QuickScriptResultPanel result={result} />
        </div>
      ) : null}
    </form>
  )
}
