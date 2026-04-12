'use client'

import { useEffect, useRef, useState } from 'react'
import { Check, Save, Upload, Download, Copy, CheckCheck } from 'lucide-react'

import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { FormDescription, FormField, FormLabel, FormMessage } from '@/components/ui/form-field'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { getStrategy, updateStrategy } from '@/lib/content-gen-api'
import type { StrategyMemory } from '@/types/content-gen'

export function StrategyEditor() {
  const [strategy, setStrategy] = useState<StrategyMemory | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [saved, setSaved] = useState(false)
  const [importing, setImporting] = useState(false)
  const [importError, setImportError] = useState<string | null>(null)
  const [copied, setCopied] = useState(false)
  const [showImport, setShowImport] = useState(false)
  const [importText, setImportText] = useState('')
  const [jsonValid, setJsonValid] = useState<boolean | null>(null)

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

  const handleExport = () => {
    if (!strategy) return
    const blob = new Blob([JSON.stringify(strategy, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `strategy-${Date.now()}.json`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
  }

  const handleCopyToClipboard = async () => {
    if (!strategy) return
    try {
      await navigator.clipboard.writeText(JSON.stringify(strategy, null, 2))
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      setImportError('Failed to copy to clipboard')
    }
  }

  const handleImport = () => {
    try {
      setImporting(true)
      setImportError(null)
      const parsed = JSON.parse(importText) as StrategyMemory

      // Basic validation
      if (typeof parsed.niche !== 'string' && !Array.isArray(parsed.content_pillars)) {
        throw new Error('Invalid strategy format')
      }

      setStrategy(parsed)
      setShowImport(false)
      setImportText('')
      setJsonValid(null)
    } catch (err) {
      setImportError(err instanceof Error ? err.message : 'Failed to import strategy')
    } finally {
      setImporting(false)
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

      {importError ? (
        <Alert variant="destructive">
          <AlertTitle>Strategy import failed</AlertTitle>
          <AlertDescription>{importError}</AlertDescription>
        </Alert>
      ) : null}

      <div className="space-y-3">
        {showImport && (
          <div className="space-y-2">
            <FormLabel htmlFor="import-textarea">Paste strategy JSON</FormLabel>
            <Textarea
              id="import-textarea"
              value={importText}
              onChange={(e) => {
                const val = e.target.value
                setImportText(val)
                setImportError(null)
                if (!val.trim()) {
                  setJsonValid(null)
                } else {
                  try {
                    JSON.parse(val)
                    setJsonValid(true)
                  } catch {
                    setJsonValid(false)
                  }
                }
              }}
              placeholder='{"niche": "...", "content_pillars": [...]}'
              rows={8}
              className={`font-mono text-xs ${jsonValid === false ? 'border-error' : jsonValid === true ? 'border-success' : ''}`}
            />
            <div className="flex gap-2">
              <Button type="button" onClick={handleImport} disabled={importing || jsonValid !== true}>
                <Upload className="h-4 w-4" />
                {importing ? 'Importing...' : 'Import'}
              </Button>
              <Button type="button" variant="ghost" onClick={() => { setShowImport(false); setImportText(''); setImportError(null); setJsonValid(null); }}>
                Cancel
              </Button>
            </div>
          </div>
        )}

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
          <Button type="button" variant="outline" onClick={handleExport} disabled={!strategy}>
            <Download className="h-4 w-4" />
            Download
          </Button>
          <Button type="button" variant="outline" onClick={handleCopyToClipboard} disabled={!strategy}>
            {copied ? <CheckCheck className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
            {copied ? 'Copied' : 'Copy'}
          </Button>
          {!showImport && (
            <Button type="button" variant="outline" onClick={() => setShowImport(true)}>
              <Upload className="h-4 w-4" />
              Import
            </Button>
          )}
        </div>
      </div>
    </div>
  )
}
