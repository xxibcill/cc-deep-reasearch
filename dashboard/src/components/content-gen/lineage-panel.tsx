'use client'

import { useEffect, useState, useRef } from 'react'
import { ArrowRight, GitBranch, GitCompare, Loader2 } from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { lifecycleStateBadgeVariant, lifecycleStateLabel, provenanceLabel } from '@/components/content-gen/brief-shared'
import type { ManagedOpportunityBrief } from '@/types/content-gen'

interface LineagePanelProps {
  brief: ManagedOpportunityBrief
  siblingBriefs: ManagedOpportunityBrief[]
  onLoadSiblings: () => void
  onCompareWith: (briefId: string) => void
  onNavigateToBrief: (briefId: string) => void
}

export function LineagePanel({
  brief,
  siblingBriefs,
  onLoadSiblings,
  onCompareWith,
  onNavigateToBrief,
}: LineagePanelProps) {
  const [loading, setLoading] = useState(false)
  const loadedRef = useRef(false)

  useEffect(() => {
    if (!loadedRef.current && siblingBriefs.length === 0) {
      loadedRef.current = true
      setLoading(true)
      Promise.resolve(onLoadSiblings()).then(() => setLoading(false)).catch(() => setLoading(false))
    }
    return () => {
      loadedRef.current = false
    }
  }, [brief.brief_id, onLoadSiblings, siblingBriefs.length])

  const isSource = !brief.source_brief_id
  const siblings = siblingBriefs.filter((b) => b.brief_id !== brief.brief_id)

  return (
    <div className="space-y-6">
      {brief.source_brief_id && (
        <Card className="rounded-[1rem]">
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-2">
              <ArrowRight className="h-4 w-4 text-muted-foreground" />
              Branched From
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center justify-between">
              <div className="space-y-1">
                <p className="text-sm font-medium text-foreground">
                  {siblingBriefs.find((b) => b.brief_id === brief.source_brief_id)?.title || brief.source_brief_id}
                </p>
                <p className="text-xs font-mono text-muted-foreground">{brief.source_brief_id}</p>
                {brief.branch_reason && (
                  <p className="text-xs text-muted-foreground/80 mt-1">
                    Reason: {brief.branch_reason}
                  </p>
                )}
              </div>
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => brief.source_brief_id && onNavigateToBrief(brief.source_brief_id)}
                className="gap-1.5"
              >
                View Source
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      <Card className="rounded-[1rem]">
        <CardHeader>
          <CardTitle className="text-base flex items-center gap-2">
            <GitBranch className="h-4 w-4 text-primary" />
            {isSource ? 'Branches' : 'Siblings'}
          </CardTitle>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="flex items-center gap-2 py-8 text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" />
              <span className="text-sm">Loading lineage...</span>
            </div>
          ) : siblings.length === 0 ? (
            <div className="text-center py-8">
              <GitBranch className="h-8 w-8 mx-auto text-muted-foreground/40 mb-2" />
              <p className="text-sm text-muted-foreground">
                {isSource
                  ? 'No branches created from this brief yet.'
                  : 'No other briefs share this lineage.'}
              </p>
            </div>
          ) : (
            <div className="space-y-3">
              {siblings.map((sibling) => (
                <div
                  key={sibling.brief_id}
                  className="flex items-center justify-between rounded-lg border border-border/70 p-3 hover:border-primary/30 transition-colors"
                >
                  <div className="space-y-1 min-w-0 flex-1">
                    <div className="flex items-center gap-2 flex-wrap">
                      <p className="text-sm font-medium text-foreground truncate">{sibling.title}</p>
                      <Badge variant={lifecycleStateBadgeVariant(sibling.lifecycle_state)} className="text-xs">
                        {lifecycleStateLabel(sibling.lifecycle_state)}
                      </Badge>
                      {sibling.source_brief_id === brief.brief_id && (
                        <Badge variant="outline" className="text-xs">Branch</Badge>
                      )}
                    </div>
                    <p className="text-xs font-mono text-muted-foreground">{sibling.brief_id}</p>
                    {sibling.branch_reason && (
                      <p className="text-xs text-muted-foreground/80 truncate">{sibling.branch_reason}</p>
                    )}
                    <p className="text-xs text-muted-foreground/60">
                      {sibling.revision_count} revision{sibling.revision_count === 1 ? '' : 's'} ·{' '}
                      {provenanceLabel(sibling.provenance)}
                    </p>
                  </div>
                  <div className="flex items-center gap-1 shrink-0 ml-4">
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      onClick={() => onCompareWith(sibling.brief_id)}
                      className="h-8 gap-1 text-xs"
                      title="Compare with this brief"
                    >
                      <GitCompare className="h-3 w-3" />
                      Compare
                    </Button>
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      onClick={() => onNavigateToBrief(sibling.brief_id)}
                      className="h-8 gap-1 text-xs"
                      title="View brief"
                    >
                      View
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {isSource && (
        <Alert variant="default" className="rounded-[1rem]">
          <AlertDescription className="text-xs text-muted-foreground">
            <GitBranch className="h-3 w-3 inline mr-1" />
            Use the <strong>Branch</strong> button to create derivative briefs for different themes,
            channels, or experiments. Branched briefs track their lineage back to this source.
          </AlertDescription>
        </Alert>
      )}
    </div>
  )
}