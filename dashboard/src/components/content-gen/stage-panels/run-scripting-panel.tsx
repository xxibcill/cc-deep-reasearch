'use client'

import { ScriptViewer } from '@/components/content-gen/script-viewer'
import type { PipelineContext } from '@/types/content-gen'

export function RunScriptingPanel({ ctx }: { ctx: PipelineContext }) {
  if (!ctx.scripting) {
    return null
  }

  return (
    <ScriptViewer
      content={
        ctx.scripting.qc?.final_script ||
        ctx.scripting.tightened?.content ||
        ctx.scripting.draft?.content ||
        ''
      }
      label="Final Script"
    />
  )
}
