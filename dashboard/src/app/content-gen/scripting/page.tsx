'use client'

import { useState } from 'react'
import Link from 'next/link'
import { ArrowLeft, Loader2, Sparkles } from 'lucide-react'
import { ScriptViewer } from '@/components/content-gen/script-viewer'
import { runScripting } from '@/lib/content-gen-api'

export default function ScriptingPage() {
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
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Scripting failed')
      setProgress(null)
    } finally {
      setIsRunning(false)
    }
  }

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      <div className="flex items-center gap-3">
        <Link
          href="/content-gen"
          className="text-muted-foreground hover:text-foreground transition-colors"
        >
          <ArrowLeft className="h-5 w-5" />
        </Link>
        <div>
          <h1 className="text-xl font-bold">Quick Script</h1>
          <p className="text-sm text-muted-foreground">
            Run the 10-step scripting pipeline for a single idea
          </p>
        </div>
      </div>

      <form onSubmit={handleRun} className="space-y-4">
        <div>
          <label htmlFor="idea" className="block text-sm font-medium mb-2">
            Video Idea
          </label>
          <textarea
            id="idea"
            value={idea}
            onChange={(e) => setIdea(e.target.value)}
            placeholder='e.g. "5 morning habits that changed my productivity"'
            className="w-full min-h-[80px] px-3 py-2 border rounded-md resize-y focus:outline-none focus:ring-2 focus:ring-primary text-sm"
            disabled={isRunning}
          />
        </div>
        <button
          type="submit"
          disabled={isRunning || !idea.trim()}
          className="flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-md hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed transition-colors text-sm"
        >
          {isRunning ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin" />
              Running...
            </>
          ) : (
            <>
              <Sparkles className="h-4 w-4" />
              Generate Script
            </>
          )}
        </button>
      </form>

      {progress && (
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin" />
          {progress}
        </div>
      )}

      {error && <p className="text-sm text-red-600">{error}</p>}

      {result && (
        <div className="space-y-4">
          <ScriptViewer content={result.content} label="Generated Script" />
          {result.run_id && (
            <p className="text-xs text-muted-foreground">
              Run ID: {result.run_id}
            </p>
          )}
        </div>
      )}
    </div>
  )
}
