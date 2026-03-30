'use client'

import { useState } from 'react'
import { Loader2 } from 'lucide-react'
import { ScriptViewer } from '@/components/content-gen/script-viewer'
import { runScripting } from '@/lib/content-gen-api'

interface QuickScriptFormProps {
  onSuccess?: () => void
}

export function QuickScriptForm({ onSuccess }: QuickScriptFormProps) {
  const [idea, setIdea] = useState('')
  const [result, setResult] = useState<{ content: string; run_id?: string } | null>(null)
  const [isRunning, setIsRunning] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [progress, setProgress] = useState<string | null>(null)

  const handleRun = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!idea.trim()) return

    setIsRunning(true)
    setError(null)
    setResult(null)
    setProgress('Starting 10-step scripting pipeline...')

    try {
      const response = await runScripting(idea.trim())
      setResult({
        content: response.script || '',
        run_id: response.run_id,
      })
      setProgress(null)
      onSuccess?.()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Scripting failed')
      setProgress(null)
    } finally {
      setIsRunning(false)
    }
  }

  return (
    <form onSubmit={handleRun} className="space-y-4">
      <div>
        <label htmlFor="qs-idea" className="block text-xs font-mono uppercase tracking-wider text-muted-foreground mb-2">
          Video Idea
        </label>
        <textarea
          id="qs-idea"
          value={idea}
          onChange={(e) => setIdea(e.target.value)}
          placeholder='e.g. "5 morning habits that changed my productivity"'
          className="w-full min-h-[80px] px-3 py-2.5 bg-background border border-border rounded-sm text-sm resize-y
            focus:outline-none focus:border-warning/50 focus:ring-1 focus:ring-warning/20
            placeholder:text-muted-foreground/40 transition-colors"
          disabled={isRunning}
        />
      </div>
      <button
        type="submit"
        disabled={isRunning || !idea.trim()}
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
        <div className="text-sm text-error bg-error-muted/20 border border-error/20 rounded-sm px-3 py-2">
          {error}
        </div>
      )}

      {result && (
        <div className="space-y-3 animate-fade-in">
          <ScriptViewer content={result.content} label="Generated Script" />
          {result.run_id && (
            <p className="text-[11px] font-mono text-muted-foreground tabular-nums">
              {result.run_id}
            </p>
          )}
        </div>
      )}
    </form>
  )
}
