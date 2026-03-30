'use client'

import { useState, useEffect } from 'react'
import { Save, Check } from 'lucide-react'
import type { StrategyMemory } from '@/types/content-gen'
import { getStrategy, updateStrategy } from '@/lib/content-gen-api'

export function StrategyEditor() {
  const [strategy, setStrategy] = useState<StrategyMemory | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [saved, setSaved] = useState(false)

  useEffect(() => {
    loadStrategy()
  }, [])

  const loadStrategy = async () => {
    try {
      setLoading(true)
      const data = await getStrategy()
      setStrategy(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load strategy')
    } finally {
      setLoading(false)
    }
  }

  const handleSave = async () => {
    if (!strategy) return
    try {
      setSaving(true)
      setError(null)
      setSaved(false)
      const patch: Record<string, unknown> = {}
      if (strategy.niche) patch.niche = strategy.niche
      if (strategy.content_pillars?.length) patch.content_pillars = strategy.content_pillars
      if (strategy.tone_rules?.length) patch.tone_rules = strategy.tone_rules
      if (strategy.platforms?.length) patch.platforms = strategy.platforms
      if (strategy.forbidden_claims?.length) patch.forbidden_claims = strategy.forbidden_claims
      if (strategy.proof_standards?.length) patch.proof_standards = strategy.proof_standards
      await updateStrategy(patch)
      setSaved(true)
      setTimeout(() => setSaved(false), 2000)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save strategy')
    } finally {
      setSaving(false)
    }
  }

  if (loading) return <div className="text-muted-foreground text-sm">Loading strategy...</div>
  if (!strategy) return <div className="text-muted-foreground text-sm">No strategy found</div>

  const listField = (label: string, field: keyof StrategyMemory) => {
    const value = (strategy[field] as string[] | undefined) || []
    return (
      <div>
        <label className="block text-xs font-mono uppercase tracking-wider text-muted-foreground mb-1.5">
          {label}
        </label>
        <input
          type="text"
          value={value.join(', ')}
          onChange={(e) => {
            const parts = e.target.value.split(',').map((s) => s.trim()).filter(Boolean)
            setStrategy((prev) => (prev ? { ...prev, [field]: parts } : prev))
          }}
          className="w-full px-3 py-2 bg-background border border-border rounded-sm text-sm
            focus:outline-none focus:border-warning/50 focus:ring-1 focus:ring-warning/20
            placeholder:text-muted-foreground/40 transition-colors"
          placeholder="Comma-separated values"
        />
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <div>
        <label className="block text-xs font-mono uppercase tracking-wider text-muted-foreground mb-1.5">
          Niche
        </label>
        <input
          type="text"
          value={strategy.niche || ''}
          onChange={(e) => setStrategy((prev) => (prev ? { ...prev, niche: e.target.value } : prev))}
          className="w-full px-3 py-2 bg-background border border-border rounded-sm text-sm
            focus:outline-none focus:border-warning/50 focus:ring-1 focus:ring-warning/20
            placeholder:text-muted-foreground/40 transition-colors"
          placeholder="e.g. Personal finance for millennials"
        />
      </div>

      {listField('Content Pillars', 'content_pillars')}
      {listField('Tone Rules', 'tone_rules')}
      {listField('Platforms', 'platforms')}
      {listField('Forbidden Claims', 'forbidden_claims')}
      {listField('Proof Standards', 'proof_standards')}

      {error && <p className="text-sm text-error">{error}</p>}

      <button
        onClick={handleSave}
        disabled={saving}
        className="flex items-center gap-2 px-4 py-2 bg-warning/15 border border-warning/30 text-warning rounded-sm text-sm font-medium font-display
          hover:bg-warning/25 disabled:opacity-50 transition-colors"
      >
        {saved ? (
          <>
            <Check className="h-4 w-4" />
            Saved
          </>
        ) : (
          <>
            <Save className="h-4 w-4" />
            {saving ? 'Saving...' : 'Save Strategy'}
          </>
        )}
      </button>
    </div>
  )
}
