'use client'

import { useEffect, useState } from 'react'
import { Loader2, AlertTriangle, Check, X } from 'lucide-react'
import type { RuleVersion } from '@/types/content-gen'
import { getRulesForReview, updateRuleLifecycle } from '@/lib/content-gen-api'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'

function RuleStatusBadge({ status }: { status: string }) {
  const variants: Record<string, string> = {
    promoted: 'bg-success/10 text-success border-success/30',
    under_review: 'bg-warning/10 text-warning border-warning/30',
    deprecated: 'bg-error/10 text-error border-error/30',
    expired: 'bg-error/10 text-error border-error/30',
  }
  return (
    <Badge className={`text-[10px] uppercase tracking-wider ${variants[status] ?? ''}`}>
      {status}
    </Badge>
  )
}

export function RulesForReviewPanel() {
  const [rules, setRules] = useState<RuleVersion[]>([])
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    void loadRules()
  }, [])

  const loadRules = async () => {
    try {
      setLoading(true)
      const data = await getRulesForReview()
      setRules(data)
    } catch {
      // governance is optional, don't block on errors
    } finally {
      setLoading(false)
    }
  }

  const handleDeprecate = async (versionId: string) => {
    try {
      await updateRuleLifecycle(versionId, { status: 'deprecated' })
      await loadRules()
    } catch {
      // best effort
    }
  }

  const handlePromote = async (versionId: string) => {
    try {
      await updateRuleLifecycle(versionId, { status: 'promoted' })
      await loadRules()
    } catch {
      // best effort
    }
  }

  if (loading) {
    return (
      <div className="flex items-center gap-2 text-xs text-muted-foreground">
        <Loader2 className="h-3.5 w-3.5 animate-spin" />
        Loading rules for review…
      </div>
    )
  }

  if (!rules || rules.length === 0) return null

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2">
        <AlertTriangle className="h-4 w-4 text-warning" />
        <p className="text-sm font-medium">{rules.length} rule(s) need review</p>
      </div>
      <div className="space-y-2">
        {rules.map((rule) => (
          <div
            key={rule.version_id}
            className="flex items-start justify-between gap-3 rounded-lg border border-border/70 bg-background/55 px-3 py-2.5"
          >
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-2">
                <p className="text-xs font-medium truncate">{rule.change_summary || rule.new_value || rule.kind}</p>
                <RuleStatusBadge status={rule.lifecycle_status} />
              </div>
              <p className="text-xs text-muted-foreground mt-0.5">
                {rule.kind} · confidence {Math.round(rule.confidence * 100)}% · {rule.evidence_count} evidence
              </p>
              {rule.review_notes && (
                <p className="text-xs text-muted-foreground mt-1 italic">Review: {rule.review_notes}</p>
              )}
            </div>
            <div className="flex gap-1.5 shrink-0">
              {rule.lifecycle_status !== 'promoted' && (
                <Button
                  size="sm"
                  variant="ghost"
                  className="h-7 text-xs"
                  onClick={() => handlePromote(rule.version_id)}
                >
                  <Check className="h-3 w-3" />
                  Promote
                </Button>
              )}
              <Button
                size="sm"
                variant="ghost"
                className="h-7 text-xs text-error hover:text-error"
                onClick={() => handleDeprecate(rule.version_id)}
              >
                <X className="h-3 w-3" />
                Deprecate
              </Button>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
