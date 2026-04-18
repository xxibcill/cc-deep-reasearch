'use client'

import { useEffect, useState } from 'react'
import { Loader2, AlertTriangle } from 'lucide-react'
import type { OperatingFitnessMetrics } from '@/types/content-gen'
import { getOperatingFitness } from '@/lib/content-gen-api'

interface FitnessData {
  metrics: OperatingFitnessMetrics
  summary: string
}

function FitnessMetricRow({ label, value, unit }: { label: string; value: string | number; unit?: string }) {
  return (
    <div className="flex items-center justify-between py-1">
      <span className="text-xs text-muted-foreground">{label}</span>
      <span className="text-xs font-medium">
        {value}
        {unit && <span className="text-muted-foreground ml-0.5">{unit}</span>}
      </span>
    </div>
  )
}

export function OperatingFitnessPanel() {
  const [fitness, setFitness] = useState<FitnessData | null>(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    void loadFitness()
  }, [])

  const loadFitness = async () => {
    try {
      setLoading(true)
      const data = await getOperatingFitness()
      setFitness(data)
    } catch {
      // fitness is optional
    } finally {
      setLoading(false)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center gap-2 text-xs text-muted-foreground">
        <Loader2 className="h-3.5 w-3.5 animate-spin" />
        Loading operating fitness…
      </div>
    )
  }

  if (!fitness) return null

  const m = fitness.metrics

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2">
        <AlertTriangle className="h-4 w-4 text-muted-foreground" />
        <p className="text-sm font-medium">Operating Fitness</p>
      </div>

      <div className="rounded-lg border border-border/70 bg-background/55 px-3 py-2 space-y-0">
        <FitnessMetricRow label="Kill rate" value={`${Math.round((m.kill_rate ?? 0) * 100)}%`} />
        <FitnessMetricRow label="Publish rate" value={`${Math.round((m.publish_rate ?? 0) * 100)}%`} />
        <FitnessMetricRow label="Avg cycle" value={Math.round(m.avg_cycle_time_ms / 1000)} unit="s" />
        <FitnessMetricRow label="P95 cycle" value={Math.round(m.p95_cycle_time_ms / 1000)} unit="s" />
        <FitnessMetricRow label="Published/wk" value={m.published_per_week?.toFixed(1) ?? '0'} />
      </div>

      {m.drift_summary && (
        <div className="rounded-lg border border-border/70 bg-background/55 px-3 py-2">
          <p className="text-xs font-medium mb-1">Strategy Drift</p>
          <p className="text-xs text-muted-foreground">{m.drift_summary}</p>
          {m.learning_bias_score > 0.1 && (
            <p className="text-xs text-warning mt-1">Hook overrepresentation: {Math.round(m.learning_bias_score * 100)}%</p>
          )}
          {m.rules_needing_review_count > 0 && (
            <p className="text-xs text-warning mt-0.5">{m.rules_needing_review_count} rules need review</p>
          )}
        </div>
      )}
    </div>
  )
}