'use client'

import { useState } from 'react'
import { ShieldCheck, AlertTriangle, XCircle, Shield, ShieldAlert, ShieldX } from 'lucide-react'
import type { HumanQCGate } from '@/types/content-gen'

interface QCGatePanelProps {
  qcGate: HumanQCGate
  pipelineId: string
  onApprove?: (pipelineId: string) => Promise<void>
}

const STRENGTH_CONFIG = {
  strong: {
    icon: Shield,
    color: 'text-success',
    bg: 'bg-success-muted/40',
    border: 'border-success/20',
    label: 'Strong',
  },
  adequate: {
    icon: ShieldAlert,
    color: 'text-warning',
    bg: 'bg-warning-muted/40',
    border: 'border-warning/20',
    label: 'Adequate',
  },
  weak: {
    icon: ShieldX,
    color: 'text-error',
    bg: 'bg-error-muted/40',
    border: 'border-error/20',
    label: 'Weak',
  },
} as const

export function QCGatePanel({ qcGate, pipelineId, onApprove }: QCGatePanelProps) {
  const [approving, setApproving] = useState(false)
  const [approved, setApproved] = useState(qcGate.approved_for_publish)

  const strengthInfo =
    STRENGTH_CONFIG[qcGate.hook_strength as keyof typeof STRENGTH_CONFIG] ??
    STRENGTH_CONFIG.adequate
  const StrengthIcon = strengthInfo.icon

  const handleApprove = async () => {
    if (!onApprove) return
    try {
      setApproving(true)
      await onApprove(pipelineId)
      setApproved(true)
    } finally {
      setApproving(false)
    }
  }

  const issueSection = (title: string, issues: string[]) => {
    if (!issues.length) return null
    return (
      <div>
        <h4 className="text-xs font-mono uppercase tracking-wider text-muted-foreground mb-1.5">
          {title}
        </h4>
        <ul className="space-y-1">
          {issues.map((issue, i) => (
            <li key={i} className="text-sm text-foreground/70 pl-3 border-l border-border">
              {issue}
            </li>
          ))}
        </ul>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-display font-semibold uppercase tracking-wide">
          QC Review
        </h3>
        <div
          className={`flex items-center gap-1.5 px-2.5 py-1 rounded-sm text-xs font-mono font-medium border ${strengthInfo.bg} ${strengthInfo.border} ${strengthInfo.color}`}
        >
          <StrengthIcon className="h-3.5 w-3.5" />
          {strengthInfo.label}
        </div>
      </div>

      {/* Must-fix items */}
      {qcGate.must_fix_items.length > 0 && (
        <div className="border border-error/20 bg-error-muted/20 rounded-sm p-3 space-y-1.5">
          <h4 className="text-xs font-mono uppercase tracking-wider text-error">
            Must Fix
          </h4>
          <ul className="space-y-1">
            {qcGate.must_fix_items.map((item, i) => (
              <li key={i} className="text-sm text-error/80 pl-3 border-l border-error/30">
                {item}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Issue categories */}
      <div className="space-y-3">
        {issueSection('Clarity', qcGate.clarity_issues)}
        {issueSection('Factual', qcGate.factual_issues)}
        {issueSection('Visual', qcGate.visual_issues)}
        {issueSection('Caption', qcGate.caption_issues)}
      </div>

      {/* Approval */}
      <div className="pt-3 border-t border-border">
        {approved ? (
          <div className="flex items-center gap-2 text-success text-sm font-medium">
            <ShieldCheck className="h-4 w-4" />
            Approved for publish
          </div>
        ) : (
          <button
            onClick={handleApprove}
            disabled={approving || qcGate.must_fix_items.length > 0}
            className="px-4 py-2 bg-success/15 border border-success/30 text-success rounded-sm text-sm font-medium
              hover:bg-success/25 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
            title={
              qcGate.must_fix_items.length > 0
                ? 'Fix all must-fix items before approving'
                : 'Approve for publish (human only)'
            }
          >
            {approving ? 'Approving...' : 'Approve for Publish'}
          </button>
        )}
        {qcGate.must_fix_items.length > 0 && !approved && (
          <p className="text-[11px] text-muted-foreground mt-1.5 font-mono">
            Resolve must-fix items before approval
          </p>
        )}
      </div>
    </div>
  )
}
