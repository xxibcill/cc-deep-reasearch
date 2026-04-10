'use client'

import { useEffect, useState } from 'react'
import { Check, Save } from 'lucide-react'

import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { FormDescription, FormField, FormLabel, FormMessage } from '@/components/ui/form-field'
import { Input } from '@/components/ui/input'
import { getStrategy, updateStrategy } from '@/lib/content-gen-api'
import type { StrategyMemory } from '@/types/content-gen'

export function StrategyEditor() {
  const [strategy, setStrategy] = useState<StrategyMemory | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [saved, setSaved] = useState(false)

  useEffect(() => {
    void loadStrategy()
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

  if (loading) return <div className="text-sm text-muted-foreground">Loading strategy...</div>
  if (!strategy) return <div className="text-sm text-muted-foreground">No strategy found</div>

  const renderListField = (label: string, field: keyof StrategyMemory) => {
    const value = (strategy[field] as string[] | undefined) || []

    return (
      <FormField>
        <FormLabel htmlFor={`strategy-${field}`}>{label}</FormLabel>
        <FormDescription>Enter comma-separated values to update this strategy list.</FormDescription>
        <Input
          id={`strategy-${field}`}
          type="text"
          value={value.join(', ')}
          onChange={(e) => {
            const parts = e.target.value
              .split(',')
              .map((segment) => segment.trim())
              .filter(Boolean)
            setStrategy((prev) => (prev ? { ...prev, [field]: parts } : prev))
          }}
          placeholder="Comma-separated values"
        />
      </FormField>
    )
  }

  return (
    <div className="space-y-5">
      <FormField>
        <FormLabel htmlFor="strategy-niche">Niche</FormLabel>
        <FormDescription>
          Set the core niche or market this content studio should optimize for.
        </FormDescription>
        <Input
          id="strategy-niche"
          type="text"
          value={strategy.niche || ''}
          onChange={(e) => setStrategy((prev) => (prev ? { ...prev, niche: e.target.value } : prev))}
          placeholder="e.g. Personal finance for millennials"
        />
      </FormField>

      {renderListField('Content Pillars', 'content_pillars')}
      {renderListField('Tone Rules', 'tone_rules')}
      {renderListField('Platforms', 'platforms')}
      {renderListField('Forbidden Claims', 'forbidden_claims')}
      {renderListField('Proof Standards', 'proof_standards')}

      {error ? (
        <Alert variant="destructive">
          <AlertTitle>Strategy save failed</AlertTitle>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      ) : null}

      <div className="flex flex-wrap items-center gap-3">
        <Button
          type="button"
          onClick={handleSave}
          disabled={saving}
          className="bg-warning text-background hover:bg-warning/90"
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
        </Button>
        {saved ? <FormMessage tone="success">Strategy updated.</FormMessage> : null}
      </div>
    </div>
  )
}
