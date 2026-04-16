'use client'

import { useEffect, useState } from 'react'
import { Loader2 } from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Card, CardContent } from '@/components/ui/card'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogBody, DialogFooter } from '@/components/ui/dialog'
import { lifecycleStateBadgeVariant, lifecycleStateLabel, formatBriefTimestamp } from '@/components/content-gen/brief-shared'
import { compareBriefs } from '@/lib/content-gen-api'
import type { ManagedOpportunityBrief, BriefRevision, CompareBriefsResponse } from '@/types/content-gen'

interface CompareBriefsDialogProps {
  briefId: string
  otherBriefId: string
  onClose: () => void
}

const COMPARE_FIELDS = [
  'theme',
  'goal',
  'primary_audience_segment',
  'content_objective',
  'sub_angles',
  'success_criteria',
] as const

export function CompareBriefsDialog({
  briefId,
  otherBriefId,
  onClose,
}: CompareBriefsDialogProps) {
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<CompareBriefsResponse | null>(null)

  useEffect(() => {
    setLoading(true)
    setError(null)
    compareBriefs(briefId, otherBriefId)
      .then((data) => {
        setResult(data)
        setLoading(false)
      })
      .catch((err) => {
        setError(err instanceof Error ? err.message : 'Failed to compare briefs')
        setLoading(false)
      })
  }, [briefId, otherBriefId])

  return (
    <Dialog open={true} onOpenChange={() => onClose()}>
      <DialogContent className="max-w-4xl max-h-[85vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Compare Briefs</DialogTitle>
        </DialogHeader>
        <DialogBody>
          {loading && (
            <div className="flex items-center gap-2 py-16 text-muted-foreground justify-center">
              <Loader2 className="h-5 w-5 animate-spin" />
              <span className="text-sm">Comparing briefs...</span>
            </div>
          )}

          {error && (
            <Alert variant="destructive">
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}

          {result && !loading && (
            <div className="space-y-6">
              <div className="grid grid-cols-2 gap-4">
                <BriefSummaryCard brief={result.brief_a} revision={result.revision_a} label="Brief A" />
                <BriefSummaryCard brief={result.brief_b} revision={result.revision_b} label="Brief B" />
              </div>

              <div className="space-y-4">
                <h3 className="text-sm font-medium text-foreground">Field Comparison</h3>
                {COMPARE_FIELDS.map((field) => {
                  const aVal = result.revision_a ? String(result.revision_a[field] || '') : ''
                  const bVal = result.revision_b ? String(result.revision_b[field] || '') : ''
                  const aList = Array.isArray(result.revision_a?.[field]) ? result.revision_a![field] : null
                  const bList = Array.isArray(result.revision_b?.[field]) ? result.revision_b![field] : null
                  const changed = aVal !== bVal

                  return (
                    <div key={field} className="space-y-2">
                      <p className="text-xs font-mono uppercase tracking-[0.18em] text-muted-foreground capitalize">
                        {field.replace(/_/g, ' ')} {changed && <span className="text-warning">(changed)</span>}
                      </p>
                      <div className="grid grid-cols-2 gap-4">
                        <div className={`rounded-lg border p-3 ${changed ? 'border-warning/50 bg-warning/5' : 'border-border'}`}>
                          <p className="text-[10px] font-mono text-muted-foreground mb-2">
                            {result.brief_a.title} {result.revision_a && `(v${result.revision_a.version})`}
                          </p>
                          {aList ? (
                            <ul className="space-y-1">
                              {aList.map((item: string, i: number) => (
                                <li key={i} className="text-sm text-foreground/88">• {item}</li>
                              ))}
                              {aList.length === 0 && <li className="text-sm text-muted-foreground">—</li>}
                            </ul>
                          ) : (
                            <p className="text-sm whitespace-pre-wrap">{aVal || '—'}</p>
                          )}
                        </div>
                        <div className={`rounded-lg border p-3 ${changed ? 'border-primary/50 bg-primary/5' : 'border-border'}`}>
                          <p className="text-[10px] font-mono text-muted-foreground mb-2">
                            {result.brief_b.title} {result.revision_b && `(v${result.revision_b.version})`}
                          </p>
                          {bList ? (
                            <ul className="space-y-1">
                              {bList.map((item: string, i: number) => (
                                <li key={i} className="text-sm text-foreground/88">• {item}</li>
                              ))}
                              {bList.length === 0 && <li className="text-sm text-muted-foreground">—</li>}
                            </ul>
                          ) : (
                            <p className="text-sm whitespace-pre-wrap">{bVal || '—'}</p>
                          )}
                        </div>
                      </div>
                    </div>
                  )
                })}
              </div>
            </div>
          )}
        </DialogBody>
        <DialogFooter>
          <Button type="button" variant="outline" onClick={() => onClose()}>
            Close
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

function BriefSummaryCard({
  brief,
  revision,
  label,
}: {
  brief: ManagedOpportunityBrief
  revision: BriefRevision | null
  label: string
}) {
  return (
    <Card className="rounded-[1rem]">
      <CardContent className="p-4 space-y-3">
        <div className="flex items-center gap-2">
          <span className="text-xs font-mono text-muted-foreground">{label}</span>
          <Badge variant={lifecycleStateBadgeVariant(brief.lifecycle_state)} className="text-xs">
            {lifecycleStateLabel(brief.lifecycle_state)}
          </Badge>
        </div>
        <div className="space-y-1">
          <p className="text-sm font-medium text-foreground">{brief.title}</p>
          <p className="text-xs font-mono text-muted-foreground">{brief.brief_id}</p>
        </div>
        {revision && (
          <div className="pt-2 border-t border-border/50 space-y-1">
            <p className="text-xs text-muted-foreground">
              Revision v{revision.version} · {formatBriefTimestamp(revision.created_at)}
            </p>
            {brief.source_brief_id && (
              <p className="text-xs text-muted-foreground/70">
                Branched from: {brief.source_brief_id}
              </p>
            )}
            {brief.branch_reason && (
              <p className="text-xs text-muted-foreground/70">
                Reason: {brief.branch_reason}
              </p>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  )
}