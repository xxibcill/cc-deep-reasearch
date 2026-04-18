'use client'

import type { StrategyMemory } from '@/types/content-gen'
import { Check, AlertTriangle, AlertCircle } from 'lucide-react'

interface SectionHealth {
  label: string
  status: 'complete' | 'warning' | 'missing'
  detail: string
}

function computeHealth(s: StrategyMemory | null): SectionHealth[] {
  if (!s) return []
  const h: SectionHealth[] = []

  h.push({
    label: 'Niche',
    status: s.niche?.trim() ? 'complete' : 'missing',
    detail: s.niche?.trim() ? s.niche : 'No niche set',
  })

  h.push({
    label: 'Content pillars',
    status: s.content_pillars.length > 0 ? 'complete' : 'missing',
    detail: `${s.content_pillars.length} pillar${s.content_pillars.length !== 1 ? 's' : ''} configured`,
  })

  h.push({
    label: 'Audience segments',
    status: s.audience_segments.length > 0 ? 'complete' : 'warning',
    detail:
      s.audience_segments.length > 0
        ? `${s.audience_segments.length} segment${s.audience_segments.length !== 1 ? 's' : ''}`
        : 'No audience segments – recommended for targeting',
  })

  h.push({
    label: 'Platforms',
    status: s.platforms.length > 0 || s.platform_rules.length > 0 ? 'complete' : 'warning',
    detail:
      s.platforms.length > 0
        ? s.platforms.join(', ')
        : s.platform_rules.length > 0
          ? `${s.platform_rules.length} platform rule${s.platform_rules.length !== 1 ? 's' : ''}`
          : 'No platforms set',
  })

  h.push({
    label: 'Tone rules',
    status: s.tone_rules.length > 0 ? 'complete' : 'warning',
    detail: s.tone_rules.length > 0 ? s.tone_rules.join(' | ') : 'No tone rules',
  })

  h.push({
    label: 'Proof & claims',
    status:
      s.proof_standards.length > 0 && s.forbidden_claims.length > 0
        ? 'complete'
        : s.proof_standards.length > 0 || s.forbidden_claims.length > 0
          ? 'warning'
          : 'missing',
    detail:
      s.proof_standards.length > 0 && s.forbidden_claims.length > 0
        ? 'Standards and forbidden claims set'
        : s.proof_standards.length > 0
          ? 'Only proof standards set'
          : s.forbidden_claims.length > 0
            ? 'Only forbidden claims set'
            : 'No proof standards or forbidden claims',
  })

  h.push({
    label: 'Past examples',
    status: s.past_winners.length > 0 || s.past_losers.length > 0 ? 'complete' : 'warning',
    detail:
      s.past_winners.length > 0 && s.past_losers.length > 0
        ? `${s.past_winners.length} winner${s.past_winners.length !== 1 ? 's' : ''}, ${s.past_losers.length} loser${s.past_losers.length !== 1 ? 's' : ''}`
        : s.past_winners.length > 0
          ? `${s.past_winners.length} past winner${s.past_winners.length !== 1 ? 's' : ''}`
          : s.past_losers.length > 0
            ? `${s.past_losers.length} past loser${s.past_losers.length !== 1 ? 's' : ''}`
            : 'No past examples',
  })

  return h
}

function HealthIcon({ status }: { status: SectionHealth['status'] }) {
  if (status === 'complete') return <Check className="h-3.5 w-3.5 text-success" />
  if (status === 'warning') return <AlertTriangle className="h-3.5 w-3.5 text-warning" />
  return <AlertCircle className="h-3.5 w-3.5 text-error" />
}

interface HealthPanelProps {
  strategy: StrategyMemory
}

export function HealthPanel({ strategy }: HealthPanelProps) {
  const health = computeHealth(strategy)

  return (
    <div className="grid gap-3 sm:grid-cols-2">
      {health.map((h) => (
        <div key={h.label} className="flex items-start gap-3 rounded-xl border border-border/70 bg-background/55 px-4 py-3">
          <HealthIcon status={h.status} />
          <div className="min-w-0 flex-1">
            <p className="text-sm font-medium text-foreground">{h.label}</p>
            <p className="text-xs text-muted-foreground truncate">{h.detail}</p>
          </div>
        </div>
      ))}
    </div>
  )
}