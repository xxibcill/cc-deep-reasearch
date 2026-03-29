'use client'

import { useState } from 'react'
import { ShieldCheck, AlertTriangle, XCircle } from 'lucide-react'
import type { HumanQCGate } from '@/types/content-gen'

interface QCGatePanelProps {
  qcGate: HumanQCGate
  pipelineId: string
  onApprove?: (pipelineId: string) => Promise<void>
}

const STRENGTH_CONFIG = {
  strong: { icon: ShieldCheck, color: 'text-green-600', bg: 'bg-green-50' },
  adequate: { icon: AlertTriangle, color: 'text-yellow-600', bg: 'bg-yellow-50' },
  weak: { icon: XCircle, color: 'text-red-600', bg: 'bg-red-50' },
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
        <h4 className="text-sm font-medium mb-1">{title}</h4>
        <ul className="list-disc list-inside text-sm text-muted-foreground space-y-0.5">
          {issues.map((issue, i) => (
            <li key={i}>{issue}</li>
          ))}
        </ul>
      </div>
    )
  }

  return (
    <div className="space-y-4 border rounded-md p-4">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold">QC Review</h3>
        <div
          className={`flex items-center gap-1.5 px-3 py-1 rounded-full text-sm font-medium ${strengthInfo.bg} ${strengthInfo.color}`}
        >
          <StrengthIcon className="h-4 w-4" />
          Hook: {qcGate.hook_strength}
        </div>
      </div>

      {qcGate.must_fix_items.length > 0 && (
        <div className="border border-red-200 rounded-md p-3 bg-red-50/50">
          <h4 className="text-sm font-medium text-red-700 mb-1">Must Fix</h4>
          <ul className="list-disc list-inside text-sm text-red-600 space-y-0.5">
            {qcGate.must_fix_items.map((item, i) => (
              <li key={i}>{item}</li>
            ))}
          </ul>
        </div>
      )}

      {issueSection('Clarity Issues', qcGate.clarity_issues)}
      {issueSection('Factual Issues', qcGate.factual_issues)}
      {issueSection('Visual Issues', qcGate.visual_issues)}
      {issueSection('Caption Issues', qcGate.caption_issues)}

      <div className="pt-2 border-t">
        {approved ? (
          <div className="flex items-center gap-2 text-green-600 text-sm font-medium">
            <ShieldCheck className="h-4 w-4" />
            Approved for publish
          </div>
        ) : (
          <button
            onClick={handleApprove}
            disabled={approving || qcGate.must_fix_items.length > 0}
            className="px-4 py-2 bg-green-600 text-white rounded-md hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors text-sm"
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
          <p className="text-xs text-muted-foreground mt-1">
            Fix all must-fix items before approving
          </p>
        )}
      </div>
    </div>
  )
}
