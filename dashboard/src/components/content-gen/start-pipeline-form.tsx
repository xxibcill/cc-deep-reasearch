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

export function StartPipelineForm() {
  const router = useRouter()
  const [theme, setTheme] = useState('')
  const [fromStage, setFromStage] = useState(0)
  const [toStage, setToStage] = useState(11)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!theme.trim()) {
      setError('Please enter a theme')
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
      router.push(`/content-gen/pipeline/${result.pipeline_id}`)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to start pipeline')
      setIsSubmitting(false)
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div>
        <label htmlFor="theme" className="block text-sm font-medium mb-2">
          Theme
        </label>
        <input
          id="theme"
          type="text"
          value={theme}
          onChange={(e) => setTheme(e.target.value)}
          placeholder='e.g. "productivity tips for remote workers"'
          className="w-full px-3 py-2 border rounded-md focus:outline-none focus:ring-2 focus:ring-primary"
          disabled={isSubmitting}
        />
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div>
          <label htmlFor="from-stage" className="block text-sm font-medium mb-2">
            From Stage
          </label>
          <select
            id="from-stage"
            value={fromStage}
            onChange={(e) => setFromStage(Number(e.target.value))}
            className="w-full px-3 py-2 border rounded-md focus:outline-none focus:ring-2 focus:ring-primary"
            disabled={isSubmitting}
          >
            {PIPELINE_STAGES.map((label, idx) => (
              <option key={idx} value={idx}>
                {idx}: {label}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label htmlFor="to-stage" className="block text-sm font-medium mb-2">
            To Stage
          </label>
          <select
            id="to-stage"
            value={toStage}
            onChange={(e) => setToStage(Number(e.target.value))}
            className="w-full px-3 py-2 border rounded-md focus:outline-none focus:ring-2 focus:ring-primary"
            disabled={isSubmitting}
          >
            {PIPELINE_STAGES.map((label, idx) => (
              <option key={idx} value={idx}>
                {idx}: {label}
              </option>
            ))}
          </select>
        </div>
      </div>

      {error && <p className="text-sm text-red-600">{error}</p>}

      <button
        type="submit"
        disabled={isSubmitting || !theme.trim()}
        className="w-full px-4 py-2 bg-primary text-primary-foreground rounded-md hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
      >
        {isSubmitting ? 'Starting pipeline...' : 'Start Pipeline'}
      </button>
    </form>
  )
}
