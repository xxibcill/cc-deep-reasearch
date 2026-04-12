'use client'

import dynamic from 'next/dynamic'
import type { PipelineContext } from '@/types/content-gen'

const QCGatePanel = dynamic(
  () => import('@/components/content-gen/qc-gate-panel').then((mod) => mod.QCGatePanel),
  {
    ssr: false,
    loading: () => <p className="text-sm text-muted-foreground">Loading QC review...</p>,
  },
)

export function HumanQCPanel({ ctx, pipelineId, onApprove }: { ctx: PipelineContext; pipelineId: string; onApprove: (pipelineId: string) => Promise<void> }) {
  if (!ctx.qc_gate) {
    return null
  }

  return <QCGatePanel qcGate={ctx.qc_gate} pipelineId={pipelineId} onApprove={onApprove} />
}
