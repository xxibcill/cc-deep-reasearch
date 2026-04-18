'use client'

import { useState } from 'react'
import { Check, Copy, Download, Upload } from 'lucide-react'
import type { StrategyMemory } from '@/types/content-gen'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import {
  Dialog,
  DialogBody,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'

interface ImportExportPanelProps {
  strategy: StrategyMemory
  onImport: (s: StrategyMemory) => void
}

export function ImportExportPanel({ strategy, onImport }: ImportExportPanelProps) {
  const [importText, setImportText] = useState('')
  const [jsonValid, setJsonValid] = useState<boolean | null>(null)
  const [importError, setImportError] = useState<string | null>(null)
  const [confirmOpen, setConfirmOpen] = useState(false)
  const [copied, setCopied] = useState(false)

  const handleExport = () => {
    const nicheSlug = strategy.niche
      ? strategy.niche.toLowerCase().replace(/[^a-z0-9]+/g, '-').slice(0, 40)
      : 'strategy'
    const blob = new Blob([JSON.stringify(strategy, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${nicheSlug}-${new Date().toISOString().slice(0, 10)}.json`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
  }

  const handleCopy = async () => {
    await navigator.clipboard.writeText(JSON.stringify(strategy, null, 2))
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  const handleImportConfirm = () => {
    try {
      const parsed = JSON.parse(importText) as StrategyMemory
      const hasNiche = typeof parsed.niche === 'string' && parsed.niche.trim().length > 0
      const hasPillars = Array.isArray(parsed.content_pillars) && parsed.content_pillars.length > 0
      if (!hasNiche && !hasPillars) {
        throw new Error('Invalid: must have niche (non-empty string) or content_pillars (non-empty array)')
      }
      onImport(parsed)
      setImportText('')
      setJsonValid(null)
      setConfirmOpen(false)
      setImportError(null)
    } catch (err) {
      setImportError(err instanceof Error ? err.message : 'Import failed')
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-2">
        <Button type="button" variant="outline" onClick={handleExport} className="gap-1.5">
          <Download className="h-4 w-4" />
          Export JSON
        </Button>
        <Button type="button" variant="outline" onClick={handleCopy} className="gap-1.5">
          {copied ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
          {copied ? 'Copied' : 'Copy'}
        </Button>
      </div>

      <div className="space-y-2">
        <p className="text-[10px] font-mono uppercase tracking-[0.22em] text-muted-foreground">
          Paste strategy JSON to import
        </p>
        <Textarea
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
                const parsed = JSON.parse(val) as StrategyMemory
                const hasNiche = typeof parsed.niche === 'string' && parsed.niche.trim().length > 0
                const hasPillars = Array.isArray(parsed.content_pillars) && parsed.content_pillars.length > 0
                setJsonValid(hasNiche || hasPillars)
              } catch {
                setJsonValid(false)
              }
            }
          }}
          placeholder='{"niche": "...", "content_pillars": [...]}'
          rows={8}
          className={`font-mono text-xs ${jsonValid === false ? 'border-error' : jsonValid === true ? 'border-success' : ''}`}
        />
        {importError && (
          <Alert variant="destructive">
            <AlertTitle>Import failed</AlertTitle>
            <AlertDescription>{importError}</AlertDescription>
          </Alert>
        )}
        <Button
          type="button"
          variant="outline"
          onClick={() => setConfirmOpen(true)}
          disabled={jsonValid !== true}
          className="gap-1.5"
        >
          <Upload className="h-4 w-4" />
          Import
        </Button>
      </div>

      <Dialog open={confirmOpen} onOpenChange={setConfirmOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Confirm import</DialogTitle>
            <DialogDescription>
              This will replace your current strategy. All fields will be overwritten with the imported data.
              This cannot be undone.
            </DialogDescription>
          </DialogHeader>
          <DialogBody>
            <div className="flex gap-2">
              <Button type="button" onClick={handleImportConfirm} className="gap-1.5 bg-warning text-background hover:bg-warning/90">
                <Upload className="h-4 w-4" />
                Yes, import
              </Button>
              <Button type="button" variant="ghost" onClick={() => setConfirmOpen(false)}>
                Cancel
              </Button>
            </div>
          </DialogBody>
        </DialogContent>
      </Dialog>
    </div>
  )
}