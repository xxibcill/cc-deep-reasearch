'use client'

import { useState, useEffect, useCallback } from 'react'
import { AlertCircle, AlertTriangle, ArrowRight, CheckCircle2, Clock, Loader2, X } from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { cn } from '@/lib/utils'
import { getNextAction } from '@/lib/content-gen-api'
import type {
  NextActionRecommendation,
  NextActionResponse,
  NextActionType,
} from '@/types/content-gen'

const ACTION_CONFIG: Record<NextActionType, { label: string; color: string; bgColor: string; icon: typeof CheckCircle2 }> = {
  produce: { label: 'Produce', color: 'text-success', bgColor: 'bg-success/10', icon: CheckCircle2 },
  reframe: { label: 'Reframe', color: 'text-blue-500', bgColor: 'bg-blue-500/10', icon: ArrowRight },
  gather_evidence: { label: 'Gather Evidence', color: 'text-orange-500', bgColor: 'bg-orange-500/10', icon: Clock },
  hold: { label: 'Hold', color: 'text-muted-foreground', bgColor: 'bg-muted/50', icon: Clock },
  archive: { label: 'Archive', color: 'text-warning', bgColor: 'bg-warning/10', icon: X },
}

interface NextActionCardProps {
  ideaId: string
  strategy?: Record<string, unknown> | null
  onApplySuggestedFields?: (ideaId: string, fields: Record<string, string>) => void
}

export function NextActionCard({ ideaId, strategy, onApplySuggestedFields }: NextActionCardProps) {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [recommendation, setRecommendation] = useState<NextActionRecommendation | null>(null)
  const [itemSummary, setItemSummary] = useState<string>('')
  const [expanded, setExpanded] = useState(false)

  const loadRecommendation = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const response = await getNextAction({ idea_id: ideaId, strategy: strategy ?? null })
      setRecommendation(response.recommendation)
      setItemSummary(response.item_summary)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load recommendation')
    } finally {
      setLoading(false)
    }
  }, [ideaId, strategy])

  useEffect(() => {
    void loadRecommendation()
  }, [loadRecommendation])

  if (loading) {
    return (
      <div className="flex items-center gap-2 rounded-[0.95rem] border border-border/75 bg-card/70 p-4">
        <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
        <p className="text-sm text-muted-foreground">Getting next-action recommendation...</p>
      </div>
    )
  }

  if (error) {
    return (
      <Alert variant="destructive" className="rounded-[0.95rem]">
        <AlertDescription>{error}</AlertDescription>
      </Alert>
    )
  }

  if (!recommendation) {
    return null
  }

  const config = ACTION_CONFIG[recommendation.action]
  const Icon = config.icon

  return (
    <div className="rounded-[0.95rem] border border-border/75 bg-card/70 overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 bg-card/80 border-b border-border/60">
        <div className="flex items-center gap-2">
          <Icon className={cn('h-4 w-4', config.color)} />
          <span className="text-sm font-semibold text-foreground">Next Action</span>
          <Badge variant="outline" className={cn('text-xs', config.color, config.bgColor)}>
            {config.label}
          </Badge>
          {recommendation.confidence >= 0.8 && (
            <Badge variant="success" className="text-xs bg-success/10 text-success border-success/20">
              High confidence
            </Badge>
          )}
          {recommendation.confidence < 0.5 && (
            <Badge variant="outline" className="text-xs text-muted-foreground border-muted">
              Uncertain
            </Badge>
          )}
        </div>
        <Button
          type="button"
          variant="ghost"
          size="sm"
          onClick={() => setExpanded((v) => !v)}
          className="h-7 px-2 text-xs"
        >
          {expanded ? 'Collapse' : 'Details'}
        </Button>
      </div>

      {/* Rationale */}
      <div className="px-4 py-3">
        <p className="text-sm text-foreground/88 leading-relaxed">{recommendation.rationale}</p>
      </div>

      {/* Expanded details */}
      {expanded && (
        <div className="px-4 pb-3 space-y-3">
          {/* Blockers */}
          {recommendation.blockers.length > 0 && (
            <div className="space-y-2">
              <p className="text-[10px] font-mono uppercase tracking-[0.18em] text-muted-foreground">
                Blockers
              </p>
              <div className="flex flex-col gap-1.5">
                {recommendation.blockers.map((blocker, i) => (
                  <div key={i} className="flex items-start gap-2">
                    <AlertTriangle className="h-3.5 w-3.5 text-warning shrink-0 mt-0.5" />
                    <span className="text-xs text-muted-foreground">{blocker}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Suggested field changes */}
          {Object.keys(recommendation.suggested_fields).length > 0 && (
            <div className="space-y-2">
              <p className="text-[10px] font-mono uppercase tracking-[0.18em] text-muted-foreground">
                Suggested improvements
              </p>
              <div className="space-y-1.5">
                {Object.entries(recommendation.suggested_fields).map(([field, suggestion]) => (
                  <div key={field} className="flex items-start gap-2">
                    <ArrowRight className="h-3.5 w-3.5 text-primary/60 shrink-0 mt-0.5" />
                    <div className="flex-1 min-w-0">
                      <span className="text-xs font-mono text-primary/80">{field}</span>
                      <span className="text-xs text-muted-foreground ml-1.5">{suggestion}</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Apply suggested fields button */}
          {Object.keys(recommendation.suggested_fields).length > 0 && onApplySuggestedFields && (
            <div className="pt-1">
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => onApplySuggestedFields(ideaId, recommendation.suggested_fields)}
                className="h-8 gap-1.5 text-xs"
              >
                <CheckCircle2 className="h-3.5 w-3.5" />
                Apply suggested fields
              </Button>
            </div>
          )}
        </div>
      )}
    </div>
  )
}