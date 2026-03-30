'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { startPipeline } from '@/lib/content-gen-api'

const PIPELINE_STAGES = [
  'Load Strategy',
  'Build Backlog',
  'Score Ideas',
  'Generate Angles',
  'Build Research',
  'Run Scripting',
  'Visual Translation',
  'Production Brief',
  'Packaging',
  'Human QC',
  'Publish Queue',
  'Performance',
]

export function StartPipelineForm({ onSuccess }: { onSuccess?: (pipelineId: string) => void } = {}) {
  const router = useRouter()
  const [theme, setTheme] = useState('')
  const [fromStage, setFromStage] = useState(0)
  const [toStage, setToStage] = useState(11)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!theme.trim()) {
      setError('Enter a theme to start')
      return
    }

    setIsSubmitting(true)
    setError(null)

    try {
      const result = await startPipeline({
        theme: theme.trim(),
        from_stage: fromStage,
        to_stage: toStage,
      })
      if (onSuccess) {
        onSuccess(result.pipeline_id)
      } else {
        router.push(`/content-gen/pipeline/${result.pipeline_id}`)
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to start pipeline')
      setIsSubmitting(false)
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-5">
      {/* Theme input */}
      <div>
        <label htmlFor="theme" className="block text-xs font-mono uppercase tracking-wider text-muted-foreground mb-2">
          Theme
        </label>
        <input
          id="theme"
          type="text"
          value={theme}
          onChange={(e) => setTheme(e.target.value)}
          placeholder='e.g. "productivity tips for remote workers"'
          className="w-full px-3 py-2.5 bg-background border border-border rounded-sm text-sm
            focus:outline-none focus:border-warning/50 focus:ring-1 focus:ring-warning/20
            placeholder:text-muted-foreground/40 transition-colors"
          disabled={isSubmitting}
        />
      </div>

      {/* Stage range */}
      <div className="grid grid-cols-2 gap-4">
        <div>
          <label htmlFor="from-stage" className="block text-xs font-mono uppercase tracking-wider text-muted-foreground mb-2">
            From
          </label>
          <select
            id="from-stage"
            value={fromStage}
            onChange={(e) => setFromStage(Number(e.target.value))}
            className="w-full px-3 py-2.5 bg-background border border-border rounded-sm text-sm
              focus:outline-none focus:border-warning/50 focus:ring-1 focus:ring-warning/20
              disabled:opacity-50 transition-colors"
            disabled={isSubmitting}
          >
            {PIPELINE_STAGES.map((label, idx) => (
              <option key={idx} value={idx}>
                {String(idx).padStart(2, '0')} — {label}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label htmlFor="to-stage" className="block text-xs font-mono uppercase tracking-wider text-muted-foreground mb-2">
            To
          </label>
          <select
            id="to-stage"
            value={toStage}
            onChange={(e) => setToStage(Number(e.target.value))}
            className="w-full px-3 py-2.5 bg-background border border-border rounded-sm text-sm
              focus:outline-none focus:border-warning/50 focus:ring-1 focus:ring-warning/20
              disabled:opacity-50 transition-colors"
            disabled={isSubmitting}
          >
            {PIPELINE_STAGES.map((label, idx) => (
              <option key={idx} value={idx}>
                {String(idx).padStart(2, '0')} — {label}
              </option>
            ))}
          </select>
        </div>
      </div>

      {error && (
        <p className="text-sm text-error">{error}</p>
      )}

      {/* Submit */}
      <button
        type="submit"
        disabled={isSubmitting || !theme.trim()}
        className="w-full px-4 py-2.5 bg-warning/15 border border-warning/30 text-warning rounded-sm text-sm font-medium font-display
          hover:bg-warning/25 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
      >
        {isSubmitting ? 'Starting...' : 'Start Pipeline'}
      </button>
    </form>
  )
}
