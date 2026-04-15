'use client'

import { useState } from 'react'
import { AlertCircle, CheckCircle2, GitBranch, Loader2, Sparkles, Plus } from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { cn } from '@/lib/utils'
import {
  generateBacklogFromBrief,
  applyBacklogFromBrief,
} from '@/lib/content-gen-api'
import type {
  GeneratedBacklogItem,
  BriefToBacklogResponse,
} from '@/types/content-gen'

interface BriefToBacklogPanelProps {
  briefId: string
  briefName: string
  onItemsApplied?: () => void
}

export function BriefToBacklogPanel({
  briefId,
  briefName,
  onItemsApplied,
}: BriefToBacklogPanelProps) {
  const [generating, setGenerating] = useState(false)
  const [applying, setApplying] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [response, setResponse] = useState<BriefToBacklogResponse | null>(null)
  const [selectedItems, setSelectedItems] = useState<Set<number>>(new Set())
  const [applyError, setApplyError] = useState<string | null>(null)
  const [applied, setApplied] = useState(false)

  const handleGenerate = async () => {
    setGenerating(true)
    setError(null)
    setResponse(null)
    setSelectedItems(new Set())
    setApplied(false)

    try {
      const result = await generateBacklogFromBrief(briefId)
      setResponse(result)
      // Select all items by default
      setSelectedItems(new Set(result.items.map((_, i) => i)))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to generate backlog items')
    } finally {
      setGenerating(false)
    }
  }

  const toggleItem = (index: number) => {
    setSelectedItems((prev) => {
      const next = new Set(prev)
      if (next.has(index)) {
        next.delete(index)
      } else {
        next.add(index)
      }
      return next
    })
  }

  const handleApply = async () => {
    if (!response || selectedItems.size === 0 || applying) return

    setApplying(true)
    setApplyError(null)

    try {
      const itemsToApply = response.items.filter((_, i) => selectedItems.has(i))
      const result = await applyBacklogFromBrief(briefId, itemsToApply)

      if (result.errors?.length > 0) {
        setApplyError(result.errors.join(', '))
      } else {
        setApplied(true)
        setResponse(null)
        onItemsApplied?.()
      }
    } catch (err) {
      setApplyError(err instanceof Error ? err.message : 'Failed to apply backlog items')
    } finally {
      setApplying(false)
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <GitBranch className="h-4 w-4 text-primary" />
          <span className="text-sm font-medium text-foreground">Generate Backlog from Brief</span>
        </div>
        {!response && !applied && (
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => void handleGenerate()}
            disabled={generating}
            className="gap-1.5"
          >
            {generating ? (
              <>
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
                Generating...
              </>
            ) : (
              <>
                <Sparkles className="h-3.5 w-3.5" />
                Generate Items
              </>
            )}
          </Button>
        )}
      </div>

      {error && (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {applied && (
        <Alert variant="success" className="rounded-[1rem]">
          <CheckCircle2 className="h-4 w-4 text-success" />
          <AlertDescription>
            Successfully added {selectedItems.size} backlog item{selectedItems.size === 1 ? '' : 's'}.
          </AlertDescription>
        </Alert>
      )}

      {response && response.items.length > 0 && !applied && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <p className="text-sm text-muted-foreground">
              {response.items.length} item{response.items.length === 1 ? '' : 's'} generated
            </p>
            <div className="flex items-center gap-2">
              <span className="text-xs text-muted-foreground">
                {selectedItems.size} selected
              </span>
              <Button
                type="button"
                variant="default"
                size="sm"
                onClick={() => void handleApply()}
                disabled={applying || selectedItems.size === 0}
                className="gap-1.5 bg-success hover:bg-success/90"
              >
                {applying ? (
                  <>
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                    Applying...
                  </>
                ) : (
                  <>
                    <Plus className="h-3.5 w-3.5" />
                    Add {selectedItems.size} to Backlog
                  </>
                )}
              </Button>
            </div>
          </div>

          {response.warnings.length > 0 && (
            <Alert variant="warning" className="rounded-[0.8rem]">
              <AlertCircle className="h-4 w-4 text-warning" />
              <AlertDescription className="text-xs">
                {response.warnings.join(' ')}
              </AlertDescription>
            </Alert>
          )}

          <div className="space-y-3">
            {response.items.map((item, index) => (
              <Card
                key={index}
                className={cn(
                  'rounded-[1rem] cursor-pointer transition-all',
                  selectedItems.has(index)
                    ? 'border-primary/50 bg-primary/5'
                    : 'border-border/70 hover:border-primary/30'
                )}
                onClick={() => toggleItem(index)}
              >
                <CardContent className="p-4">
                  <div className="flex items-start gap-3">
                    <div
                      className={cn(
                        'w-5 h-5 rounded border-2 flex items-center justify-center shrink-0 mt-0.5',
                        selectedItems.has(index)
                          ? 'bg-primary border-primary'
                          : 'border-muted-foreground/30'
                      )}
                    >
                      {selectedItems.has(index) && (
                        <CheckCircle2 className="h-3 w-3 text-primary-foreground" />
                      )}
                    </div>
                    <div className="flex-1 min-w-0 space-y-2">
                      <div className="flex items-center gap-2 flex-wrap">
                        <p className="text-sm font-medium text-foreground">{item.title}</p>
                        <Badge variant="outline" className="text-xs">
                          {item.category}
                        </Badge>
                        <Badge variant="outline" className="text-xs capitalize">
                          {item.content_type || 'video'}
                        </Badge>
                      </div>
                      {item.one_line_summary && (
                        <p className="text-xs text-muted-foreground/80">{item.one_line_summary}</p>
                      )}
                      {item.audience && (
                        <p className="text-xs">
                          <span className="font-mono text-muted-foreground">Audience: </span>
                          <span className="text-foreground/80">{item.audience}</span>
                        </p>
                      )}
                      {item.problem && (
                        <p className="text-xs">
                          <span className="font-mono text-muted-foreground">Problem: </span>
                          <span className="text-foreground/80">{item.problem}</span>
                        </p>
                      )}
                      {item.hook && (
                        <p className="text-xs">
                          <span className="font-mono text-muted-foreground">Hook: </span>
                          <span className="text-foreground/80">{item.hook}</span>
                        </p>
                      )}
                      {item.reason && (
                        <p className="text-xs text-muted-foreground/60 italic">
                          {item.reason}
                        </p>
                      )}
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>

          {applyError && (
            <Alert variant="destructive">
              <AlertDescription>{applyError}</AlertDescription>
            </Alert>
          )}
        </div>
      )}

      {response && response.items.length === 0 && !applied && (
        <div className="rounded-xl border border-dashed border-border bg-card/70 py-12 text-center">
          <p className="text-sm text-muted-foreground">No backlog items could be generated.</p>
          {response.warnings.length > 0 && (
            <p className="mt-1 text-xs text-muted-foreground/60">{response.warnings.join(' ')}</p>
          )}
        </div>
      )}
    </div>
  )
}
