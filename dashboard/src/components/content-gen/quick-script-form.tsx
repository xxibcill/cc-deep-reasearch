'use client'

import { useState } from 'react'
import { Loader2 } from 'lucide-react'
import { ScriptViewer } from '@/components/content-gen/script-viewer'
import { runScripting } from '@/lib/content-gen-api'

interface QuickScriptFormProps {
  onSuccess?: () => void
}

interface FieldDef {
  key: string
  label: string
  placeholder: string
  required?: boolean
  rows?: number
}

const FIELDS: FieldDef[] = [
  { key: 'raw_idea', label: 'Raw idea', placeholder: 'What the video is about in plain words', required: true, rows: 2 },
  { key: 'viewer_outcome', label: 'What this video should help the viewer do', placeholder: 'Specific outcome' },
  { key: 'target_audience', label: 'Target audience', placeholder: 'Who this is for' },
  { key: 'platform', label: 'Platform', placeholder: 'TikTok / Reels / Shorts / X / LinkedIn / Other' },
  { key: 'desired_length', label: 'Desired length', placeholder: '20 sec / 30 sec / 45 sec / other' },
  { key: 'tone', label: 'Tone', placeholder: 'Sharp / calm / premium / funny / intense / direct / other' },
  { key: 'angle', label: 'What kind of angle you want most', placeholder: 'Contrarian / mistake / framework / insight / story / myth vs truth / no preference' },
  { key: 'must_include', label: 'Must include', placeholder: 'Any facts, claims, examples, phrases, CTA, product, offer, story, proof', rows: 2 },
  { key: 'must_avoid', label: 'Must avoid', placeholder: 'Words, tone, claims, topics, style you do not want' },
  { key: 'cta_goal', label: 'CTA goal', placeholder: 'Follow / comment / DM / click / save / share / buy / no CTA' },
  { key: 'source_material', label: 'Optional source material', placeholder: 'Paste notes, transcript, bullets, proof points, data, story details', rows: 3 },
  { key: 'constraints', label: 'Optional constraints', placeholder: 'Brand rules, compliance limits, banned claims, pronunciation notes, etc.', rows: 2 },
]

export function QuickScriptForm({ onSuccess }: QuickScriptFormProps) {
  const [fields, setFields] = useState<Record<string, string>>(() =>
    Object.fromEntries(FIELDS.map((f) => [f.key, '']))
  )
  const [result, setResult] = useState<{ content: string; run_id?: string } | null>(null)
  const [isRunning, setIsRunning] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [progress, setProgress] = useState<string | null>(null)

  const buildPrompt = (): string => {
    const lines: string[] = []
    for (const f of FIELDS) {
      const val = fields[f.key].trim()
      if (val) lines.push(`${f.label}:\n${val}`)
    }
    return lines.join('\n\n')
  }

  const isValid = fields.raw_idea.trim().length > 0

  const handleRun = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!isValid) return

    const prompt = buildPrompt()
    setIsRunning(true)
    setError(null)
    setResult(null)
    setProgress('Starting 10-step scripting pipeline...')

    try {
      const response = await runScripting(prompt)
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

  const setField = (key: string, value: string) =>
    setFields((prev) => ({ ...prev, [key]: value }))

  return (
    <form onSubmit={handleRun} className="space-y-4">
      {FIELDS.map((f) => (
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
        <div className="text-sm text-error bg-error-muted/20 border border-error/20 rounded-sm px-3 py-2">
          {error}
        </div>
      )}

      {result && (
        <div className="space-y-3 animate-fade-in pt-2 border-t border-border">
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
