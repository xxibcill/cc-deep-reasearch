'use client'

import { useState, useEffect, useCallback } from 'react'
import { AlertCircle, AlertTriangle, ArrowRight, CheckCircle2, Loader2, Play, RefreshCw } from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { cn } from '@/lib/utils'
import { generateExecutionBrief } from '@/lib/content-gen-api'
import type { ExecutionBrief } from '@/types/content-gen'

interface ExecutionBriefPanelProps {
  ideaId: string
  strategy?: Record<string, unknown> | null
  onPromoteToProduction?: (ideaId: string) => void
  onStartProduction?: (ideaId: string) => Promise<string | null>
}

export function ExecutionBriefPanel({
  ideaId,
  strategy,
  onPromoteToProduction,
  onStartProduction,
}: ExecutionBriefPanelProps) {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [brief, setBrief] = useState<ExecutionBrief | null>(null)
  const [sourceSummary, setSourceSummary] = useState<string>('')
  const [generating, setGenerating] = useState(false)

  const loadBrief = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const response = await generateExecutionBrief({
        idea_id: ideaId,
        strategy: strategy ?? null,
      })
      setBrief(response.brief)
      setSourceSummary(response.source_item_summary)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load execution brief')
    } finally {
      setLoading(false)
    }
  }, [ideaId, strategy])

  useEffect(() => {
    void loadBrief()
  }, [loadBrief])

  const handleRegenerate = async () => {
    setGenerating(true)
    setError(null)
    try {
      const response = await generateExecutionBrief({
        idea_id: ideaId,
        strategy: strategy ?? null,
      })
      setBrief(response.brief)
      setSourceSummary(response.source_item_summary)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to regenerate brief')
    } finally {
      setGenerating(false)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center gap-2 rounded-[0.95rem] border border-border/75 bg-card/70 p-4">
        <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
        <p className="text-sm text-muted-foreground">Generating execution brief...</p>
      </div>
    )
  }

  if (error && !brief) {
    return (
      <Alert variant="destructive" className="rounded-[0.95rem]">
        <AlertDescription>{error}</AlertDescription>
      </Alert>
    )
  }

  if (!brief) {
    return null
  }

  const readinessColor = brief.is_ready_for_production ? 'text-success' : 'text-warning'
  const ReadinessIcon = brief.is_ready_for_production ? CheckCircle2 : AlertTriangle

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-sm font-semibold text-foreground">Execution Brief</span>
          <Badge
            variant="outline"
            className={cn(
              'text-xs',
              readinessColor,
              brief.is_ready_for_production ? 'bg-success/10 border-success/20' : 'bg-warning/10 border-warning/20'
            )}
          >
            <ReadinessIcon className="h-3 w-3 mr-1" />
            {brief.is_ready_for_production ? 'Ready for production' : 'Not ready yet'}
          </Badge>
        </div>
        <Button
          type="button"
          variant="ghost"
          size="sm"
          onClick={() => void handleRegenerate()}
          disabled={generating}
          className="h-8 gap-1.5"
        >
          {generating ? (
            <Loader2 className="h-3.5 w-3.5 animate-spin" />
          ) : (
            <RefreshCw className="h-3.5 w-3.5" />
          )}
          Regenerate
        </Button>
      </div>

      {/* Readiness summary */}
      <div className={cn('rounded-[0.8rem] border px-4 py-3', brief.is_ready_for_production ? 'border-success/30 bg-success/5' : 'border-warning/30 bg-warning/5')}>
        <p className="text-xs text-foreground/80">{brief.readiness_summary}</p>
      </div>

      {/* Brief sections */}
      <div className="space-y-4">
        {/* Hook Direction */}
        <div className="rounded-[0.8rem] border border-border/70 bg-card/50 p-4">
          <p className="text-[10px] font-mono uppercase tracking-[0.18em] text-muted-foreground mb-2">Hook Direction</p>
          <p className="text-sm text-foreground/88 leading-relaxed">{brief.hook_direction}</p>
        </div>

        {/* Audience + Problem */}
        <div className="grid gap-3 sm:grid-cols-2">
          <div className="rounded-[0.8rem] border border-border/70 bg-card/50 p-4">
            <p className="text-[10px] font-mono uppercase tracking-[0.18em] text-muted-foreground mb-2">Audience</p>
            <p className="text-sm text-foreground/88 leading-relaxed">{brief.audience}</p>
          </div>
          <div className="rounded-[0.8rem] border border-border/70 bg-card/50 p-4">
            <p className="text-[10px] font-mono uppercase tracking-[0.18em] text-muted-foreground mb-2">Problem Statement</p>
            <p className="text-sm text-foreground/88 leading-relaxed">{brief.problem_statement}</p>
          </div>
        </div>

        {/* Evidence Requirements */}
        {brief.evidence_requirements.length > 0 && (
          <div className="rounded-[0.8rem] border border-border/70 bg-card/50 p-4">
            <p className="text-[10px] font-mono uppercase tracking-[0.18em] text-muted-foreground mb-2">Evidence Requirements</p>
            <div className="space-y-1.5">
              {brief.evidence_requirements.map((req, i) => (
                <div key={i} className="flex items-start gap-2">
                  <ArrowRight className="h-3.5 w-3.5 text-primary/60 shrink-0 mt-0.5" />
                  <span className="text-xs text-foreground/80">{req}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Proof Gaps */}
        {brief.proof_gaps.length > 0 && (
          <div className="rounded-[0.8rem] border border-warning/30 bg-warning/5 p-4">
            <p className="text-[10px] font-mono uppercase tracking-[0.18em] text-warning mb-2">Proof Gaps</p>
            <div className="space-y-1.5">
              {brief.proof_gaps.map((gap, i) => (
                <div key={i} className="flex items-start gap-2">
                  <AlertTriangle className="h-3.5 w-3.5 text-warning shrink-0 mt-0.5" />
                  <span className="text-xs text-foreground/80">{gap}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Research Questions */}
        {brief.research_questions.length > 0 && (
          <div className="rounded-[0.8rem] border border-border/70 bg-card/50 p-4">
            <p className="text-[10px] font-mono uppercase tracking-[0.18em] text-muted-foreground mb-2">Research Questions</p>
            <div className="space-y-1.5">
              {brief.research_questions.map((q, i) => (
                <div key={i} className="flex items-start gap-2">
                  <span className="text-primary/60 font-mono text-xs">?</span>
                  <span className="text-xs text-foreground/80">{q}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Production Risks */}
        {brief.risks_before_production.length > 0 && (
          <div className="rounded-[0.8rem] border border-error/20 bg-error/5 p-4">
            <p className="text-[10px] font-mono uppercase tracking-[0.18em] text-error mb-2">Production Risks</p>
            <div className="space-y-1.5">
              {brief.risks_before_production.map((risk, i) => (
                <div key={i} className="flex items-start gap-2">
                  <AlertCircle className="h-3.5 w-3.5 text-error shrink-0 mt-0.5" />
                  <span className="text-xs text-foreground/80">{risk}</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Promotion actions */}
      {brief.is_ready_for_production && (onPromoteToProduction || onStartProduction) && (
        <div className="flex items-center gap-3 pt-2 border-t border-border/60">
          <p className="text-xs text-muted-foreground">Ready to move forward</p>
          <div className="ml-auto flex items-center gap-2">
            {onPromoteToProduction && (
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => onPromoteToProduction(ideaId)}
                className="h-8 gap-1.5"
              >
                <CheckCircle2 className="h-3.5 w-3.5" />
                Promote
              </Button>
            )}
            {onStartProduction && (
              <Button
                type="button"
                variant="default"
                size="sm"
                onClick={() => void onStartProduction(ideaId)}
                className="h-8 gap-1.5"
              >
                <Play className="h-3.5 w-3.5" />
                Start Production
              </Button>
            )}
          </div>
        </div>
      )}
    </div>
  )
}