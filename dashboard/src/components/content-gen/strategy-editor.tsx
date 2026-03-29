'use client'

import { useState, useEffect } from 'react'
import { Save } from 'lucide-react'
import type { StrategyMemory } from '@/types/content-gen'
import { getStrategy, updateStrategy } from '@/lib/content-gen-api'

export function StrategyEditor() {
  const [strategy, setStrategy] = useState<StrategyMemory | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState(false)

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
      setSuccess(false)
      const patch: Record<string, unknown> = {}
      if (strategy.niche) patch.niche = strategy.niche
      if (strategy.content_pillars?.length) patch.content_pillars = strategy.content_pillars
      if (strategy.tone_rules?.length) patch.tone_rules = strategy.tone_rules
      if (strategy.platforms?.length) patch.platforms = strategy.platforms
      if (strategy.forbidden_claims?.length) patch.forbidden_claims = strategy.forbidden_claims
      if (strategy.proof_standards?.length) patch.proof_standards = strategy.proof_standards
      await updateStrategy(patch)
      setSuccess(true)
      setTimeout(() => setSuccess(false), 2000)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save strategy')
    } finally {
      setSaving(false)
    }
  }

  if (loading) return <div className="text-muted-foreground">Loading strategy...</div>
  if (!strategy) return <div className="text-muted-foreground">No strategy found</div>

  const listField = (label: string, field: keyof StrategyMemory) => {
    const value = (strategy[field] as string[] | undefined) || []
    return (
      <div>
        <label className="block text-sm font-medium mb-1">{label}</label>
        <input
          type="text"
          value={value.join(', ')}
          onChange={(e) => {
            const parts = e.target.value.split(',').map((s) => s.trim()).filter(Boolean)
            setStrategy((prev) => (prev ? { ...prev, [field]: parts } : prev))
          }}
          className="w-full px-3 py-2 border rounded-md focus:outline-none focus:ring-2 focus:ring-primary text-sm"
          placeholder="Comma-separated values"
        />
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <div>
        <label className="block text-sm font-medium mb-1">Niche</label>
        <input
          type="text"
          value={strategy.niche || ''}
          onChange={(e) => setStrategy((prev) => (prev ? { ...prev, niche: e.target.value } : prev))}
          className="w-full px-3 py-2 border rounded-md focus:outline-none focus:ring-2 focus:ring-primary text-sm"
          placeholder="e.g. Personal finance for millennials"
        />
      </div>

      {listField('Content Pillars', 'content_pillars')}
      {listField('Tone Rules', 'tone_rules')}
      {listField('Platforms', 'platforms')}
      {listField('Forbidden Claims', 'forbidden_claims')}
      {listField('Proof Standards', 'proof_standards')}

      {error && <p className="text-sm text-red-600">{error}</p>}
      {success && <p className="text-sm text-green-600">Strategy saved</p>}

      <button
        onClick={handleSave}
        disabled={saving}
        className="flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-md hover:bg-primary/90 disabled:opacity-50 transition-colors text-sm"
      >
        <Save className="h-4 w-4" />
        {saving ? 'Saving...' : 'Save Strategy'}
      </button>
    </div>
  )
}
