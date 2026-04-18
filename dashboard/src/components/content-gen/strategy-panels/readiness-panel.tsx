'use client'

import { useEffect, useState } from 'react'
import { Loader2, AlertCircle, AlertTriangle, Check } from 'lucide-react'
import type { StrategyReadinessResult } from '@/types/content-gen'
import { getStrategyReadiness } from '@/lib/content-gen-api'
import { Badge } from '@/components/ui/badge'

function ReadinessIcon({ severity }: { severity: string }) {
  if (severity === 'blocking') return <AlertCircle className="h-4 w-4 text-error" />
  if (severity === 'warning') return <AlertTriangle className="h-4 w-4 text-warning" />
  return <Check className="h-4 w-4 text-success" />
}

export function ReadinessPanel() {
  const [readiness, setReadiness] = useState<StrategyReadinessResult | null>(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    void loadReadiness()
  }, [])

  const loadReadiness = async () => {
    try {
      setLoading(true)
      const data = await getStrategyReadiness()
      setReadiness(data)
    } catch {
      // readiness is optional, don't block on errors
    } finally {
      setLoading(false)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center gap-2 text-xs text-muted-foreground">
        <Loader2 className="h-3.5 w-3.5 animate-spin" />
        Checking strategy readiness…
      </div>
    )
  }

  if (!readiness) return null

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm font-medium">
            Strategy Readiness:{' '}
            <span
              className={
                readiness.readiness === 'healthy'
                  ? 'text-success'
                  : readiness.readiness === 'incomplete'
                    ? 'text-warning'
                    : 'text-error'
              }
            >
              {readiness.readiness}
            </span>
          </p>
          <p className="text-xs text-muted-foreground">{readiness.summary}</p>
        </div>
        <div className="text-right">
          <p className="text-2xl font-bold">{Math.round(readiness.overall_score * 100)}%</p>
          <p className="text-xs text-muted-foreground">completeness</p>
        </div>
      </div>

      {readiness.issues.length > 0 && (
        <div className="space-y-2">
          {readiness.issues.map((issue) => (
            <div
              key={issue.code}
              className="flex items-start gap-2.5 rounded-lg border border-border/70 bg-background/55 px-3 py-2.5"
            >
              <ReadinessIcon severity={issue.severity} />
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <p className="text-xs font-medium">{issue.label}</p>
                  <Badge variant="outline" className="text-[10px] uppercase tracking-wider">
                    {issue.severity}
                  </Badge>
                </div>
                <p className="text-xs text-muted-foreground mt-0.5">{issue.detail}</p>
                {issue.suggestion && (
                  <p className="text-xs text-muted-foreground mt-1 italic">Tip: {issue.suggestion}</p>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}