'use client'

import { AlertTriangle, Clock3, GitBranchPlus, Layers, CheckCircle2 } from 'lucide-react'

import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { getStatusBadgeVariant } from '@/lib/utils'
import type { PipelineStageTrace, StageTraceMetadata } from '@/types/content-gen'

function formatDuration(durationMs: number): string | null {
  if (!durationMs) {
    return null
  }
  if (durationMs < 1000) {
    return `${durationMs}ms`
  }
  if (durationMs < 60_000) {
    return `${(durationMs / 1000).toFixed(durationMs < 10_000 ? 1 : 0)}s`
  }
  return `${(durationMs / 60_000).toFixed(1)}m`
}

function MetadataPill({ label, value }: { label: string; value: string | number | boolean }) {
  if (value === '' || value === 0 || value === false) {
    return null
  }
  const displayValue = typeof value === 'boolean' ? (value ? 'Yes' : 'No') : String(value)
  return (
    <span className="rounded-full border border-border/60 bg-muted/40 px-2 py-0.5 text-[11px] text-muted-foreground">
      {label}: {displayValue}
    </span>
  )
}

function MetadataGrid({ metadata }: { metadata: StageTraceMetadata }) {
  const pills = [
    { label: 'Ideas', value: metadata.shortlist_count ? metadata.shortlist_count : null },
    { label: 'Angles', value: metadata.option_count ? metadata.option_count : null },
    { label: 'Facts', value: metadata.fact_count ? metadata.fact_count : null },
    { label: 'Steps', value: metadata.step_count ? metadata.step_count : null },
    { label: 'LLM', value: metadata.llm_call_count ? metadata.llm_call_count : null },
    { label: 'Words', value: metadata.final_word_count ? metadata.final_word_count : null },
    { label: 'Beats', value: metadata.beats_count ? metadata.beats_count : null },
    { label: 'Platforms', value: metadata.platforms_count ? metadata.platforms_count : null },
    { label: 'Iter', value: metadata.current_iteration ? metadata.current_iteration : null },
    { label: 'Score', value: metadata.latest_quality_score ? metadata.latest_quality_score.toFixed(2) : null },
  ].filter(p => p.value !== null) as Array<{ label: string; value: string | number }>

  if (pills.length === 0) {
    return null
  }

  return (
    <div className="flex flex-wrap gap-1.5">
      {pills.map(p => (
        <MetadataPill key={p.label} label={p.label} value={p.value} />
      ))}
    </div>
  )
}

function SummaryBlock({
  label,
  value,
}: {
  label: string
  value: string
}) {
  return (
    <div className="rounded-xl border border-border/70 bg-background/55 px-3 py-3">
      <p className="text-[11px] font-mono uppercase tracking-[0.22em] text-muted-foreground">
        {label}
      </p>
      <p className="mt-2 text-sm leading-relaxed text-foreground/80">{value}</p>
    </div>
  )
}

export function StageTraceSummary({ trace }: { trace: PipelineStageTrace | null | undefined }) {
  if (!trace) {
    return null
  }

  const duration = formatDuration(trace.duration_ms)
  const decisionVariant =
    trace.status === 'failed'
      ? 'destructive'
      : trace.status === 'skipped' || trace.warnings.length > 0
        ? 'warning'
        : 'info'

  return (
    <div className="space-y-3 rounded-[1rem] border border-border/80 bg-muted/10 p-4">
      <div className="flex flex-wrap items-center gap-2">
        <Badge variant={getStatusBadgeVariant(trace.status)}>{trace.status}</Badge>
        {duration ? (
          <Badge variant="outline" className="gap-1.5 normal-case tracking-[0.12em]">
            <Clock3 className="h-3.5 w-3.5" />
            {duration}
          </Badge>
        ) : null}
        {trace.warnings.length > 0 ? (
          <Badge variant="warning">{trace.warnings.length} warning{trace.warnings.length > 1 ? 's' : ''}</Badge>
        ) : null}
        {trace.metadata.is_degraded ? (
          <Badge variant="destructive">Degraded</Badge>
        ) : null}
        {trace.metadata.approved ? (
          <Badge variant="success" className="gap-1">
            <CheckCircle2 className="h-3 w-3" />
            Approved
          </Badge>
        ) : null}
      </div>

      {trace.metadata.selected_idea_id || trace.metadata.selected_angle_id ? (
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <Layers className="h-3.5 w-3.5" />
          <span>
            {trace.metadata.selected_idea_id && `Idea: ${trace.metadata.selected_idea_id}`}
            {trace.metadata.selected_idea_id && trace.metadata.selected_angle_id && ' / '}
            {trace.metadata.selected_angle_id && `Angle: ${trace.metadata.selected_angle_id}`}
          </span>
        </div>
      ) : null}

      <MetadataGrid metadata={trace.metadata} />

      {trace.decision_summary ? (
        <Alert variant={decisionVariant}>
          <AlertTitle className="flex items-center gap-2">
            <GitBranchPlus className="h-4 w-4" />
            Decision summary
          </AlertTitle>
          <AlertDescription>{trace.decision_summary}</AlertDescription>
        </Alert>
      ) : null}

      <div className="grid gap-3 lg:grid-cols-2">
        {trace.input_summary ? (
          <SummaryBlock label="Input" value={trace.input_summary} />
        ) : null}
        {trace.output_summary ? (
          <SummaryBlock label="Output" value={trace.output_summary} />
        ) : null}
      </div>

      {trace.warnings.length > 0 ? (
        <div className="space-y-2">
          <div className="flex items-center gap-2 text-[11px] font-mono uppercase tracking-[0.22em] text-warning">
            <AlertTriangle className="h-3.5 w-3.5" />
            Warnings
          </div>
          <ul className="space-y-2">
            {trace.warnings.map((warning, index) => (
              <li
                key={`${trace.stage_index}-warning-${index}`}
                className="rounded-xl border border-warning/25 bg-warning-muted/20 px-3 py-2 text-sm text-foreground/78"
              >
                {warning}
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {trace.metadata.degradation_reason ? (
        <Alert variant="warning">
          <AlertTitle className="flex items-center gap-2">
            <AlertTriangle className="h-4 w-4" />
            Degradation reason
          </AlertTitle>
          <AlertDescription>{trace.metadata.degradation_reason}</AlertDescription>
        </Alert>
      ) : null}
    </div>
  )
}
