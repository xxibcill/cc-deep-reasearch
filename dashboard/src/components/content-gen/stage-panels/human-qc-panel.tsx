'use client'

import { QCGatePanel } from '@/components/content-gen/qc-gate-panel'
import type { PipelineContext } from '@/types/content-gen'

export function HumanQCPanel({ ctx, pipelineId, onApprove }: { ctx: PipelineContext; pipelineId: string; onApprove: (pipelineId: string) => Promise<void> }) {
  if (!ctx.qc_gate) {
    return null
  }

  return <QCGatePanel qcGate={ctx.qc_gate} pipelineId={pipelineId} onApprove={onApprove} />
}
