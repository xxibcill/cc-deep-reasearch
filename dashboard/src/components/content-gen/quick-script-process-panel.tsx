'use client'

import { FileJson, Workflow } from 'lucide-react'
import { StageResultPanel } from '@/components/content-gen/stage-result-panel'
import type { ScriptingLLMCallTrace, ScriptingStepTrace } from '@/types/content-gen'

interface QuickScriptProcessPanelProps {
  traces: ScriptingStepTrace[]
  label?: string
}

function formatTraceValue(value: unknown): string {
  if (typeof value === 'string') {
    return value
  }
  if (value == null) {
    return 'No structured output captured.'
  }
  try {
    return JSON.stringify(value, null, 2)
  } catch {
    return String(value)
  }
}

function PromptBlock({
  title,
  content,
}: {
  title: string
  content: string
}) {
  return (
    <div className="rounded-sm border border-border bg-background">
      <div className="border-b border-border px-3 py-2 text-[11px] font-mono uppercase tracking-wider text-muted-foreground">
        {title}
      </div>
      <pre className="max-h-72 overflow-auto whitespace-pre-wrap px-3 py-3 text-xs leading-relaxed text-foreground/80">
        {content || 'Empty'}
      </pre>
    </div>
  )
}

function CallPanel({ call }: { call: ScriptingLLMCallTrace }) {
  return (
    <div className="space-y-3 rounded-sm border border-border bg-surface/60 p-3">
      <div className="flex flex-wrap items-center gap-2">
        <span className="rounded-sm border border-border px-2 py-1 text-[11px] font-mono text-muted-foreground">
          Call {call.call_index}
        </span>
        <span className="rounded-sm border border-border px-2 py-1 text-[11px] font-mono text-muted-foreground">
          {call.provider}
        </span>
        <span className="rounded-sm border border-border px-2 py-1 text-[11px] font-mono text-muted-foreground">
          {call.transport}
        </span>
        <span className="rounded-sm border border-border px-2 py-1 text-[11px] font-mono text-foreground/80">
          {call.model}
        </span>
        <span className="rounded-sm border border-border px-2 py-1 text-[11px] font-mono text-muted-foreground">
          temp {call.temperature}
        </span>
        <span className="rounded-sm border border-border px-2 py-1 text-[11px] font-mono text-muted-foreground">
          {call.latency_ms}ms
        </span>
        <span className="rounded-sm border border-border px-2 py-1 text-[11px] font-mono text-muted-foreground">
          {call.prompt_tokens} in / {call.completion_tokens} out
        </span>
        {call.finish_reason && (
          <span className="rounded-sm border border-border px-2 py-1 text-[11px] font-mono text-muted-foreground">
            {call.finish_reason}
          </span>
        )}
      </div>

      <div className="grid gap-3 xl:grid-cols-2">
        <PromptBlock title="System Prompt" content={call.system_prompt} />
        <PromptBlock title="User Prompt" content={call.user_prompt} />
      </div>

      <PromptBlock title="Raw LLM Response" content={call.raw_response} />
    </div>
  )
}

export function QuickScriptProcessPanel({
  traces,
  label = 'Quick Script Process',
}: QuickScriptProcessPanelProps) {
  if (traces.length === 0) {
    return null
  }

  const iterationOrder = Array.from(new Set(traces.map((trace) => trace.iteration))).sort((a, b) => a - b)
  const showIterations = iterationOrder.length > 1

  return (
    <div className="space-y-4">
      <div className="rounded-sm border border-border bg-background px-4 py-3">
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-xs font-mono uppercase tracking-wider text-muted-foreground">
            {label}
          </span>
          <span className="rounded-sm border border-border px-2 py-1 text-[11px] font-mono text-muted-foreground">
            {traces.length} steps captured
          </span>
          <span className="rounded-sm border border-border px-2 py-1 text-[11px] font-mono text-muted-foreground">
            {traces.reduce((total, trace) => total + trace.llm_calls.length, 0)} LLM calls
          </span>
          {showIterations && (
            <span className="rounded-sm border border-border px-2 py-1 text-[11px] font-mono text-muted-foreground">
              {iterationOrder.length} passes
            </span>
          )}
        </div>
        <p className="mt-2 text-sm text-muted-foreground">
          Review each scripting step, the exact prompts sent, the route selected, and the structured result that came back.
        </p>
      </div>

      {iterationOrder.map((iteration) => {
        const iterationTraces = traces.filter((trace) => trace.iteration === iteration)

        return (
          <div key={iteration} className="space-y-3">
            {showIterations && (
              <div className="flex items-center gap-2 text-xs font-mono uppercase tracking-wider text-muted-foreground">
                <Workflow className="h-3.5 w-3.5" />
                Pass {iteration}
              </div>
            )}

            {iterationTraces.map((trace, index) => (
              <StageResultPanel
                key={`${trace.iteration}-${trace.step_name}-${index}`}
                title={trace.step_label}
                stageIndex={trace.step_index}
                status="completed"
                defaultOpen={iteration === iterationOrder[iterationOrder.length - 1] && index === iterationTraces.length - 1}
              >
                <div className="space-y-3 pt-2">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="rounded-sm border border-border px-2 py-1 text-[11px] font-mono text-muted-foreground">
                      {trace.step_name}
                    </span>
                    <span className="rounded-sm border border-border px-2 py-1 text-[11px] font-mono text-muted-foreground">
                      {trace.llm_calls.length} call{trace.llm_calls.length === 1 ? '' : 's'}
                    </span>
                  </div>

                  <div className="space-y-3">
                    {trace.llm_calls.map((call) => (
                      <CallPanel key={call.call_index} call={call} />
                    ))}
                  </div>

                  <div className="rounded-sm border border-border bg-background">
                    <div className="flex items-center gap-2 border-b border-border px-3 py-2 text-[11px] font-mono uppercase tracking-wider text-muted-foreground">
                      <FileJson className="h-3.5 w-3.5" />
                      Parsed Step Result
                    </div>
                    <pre className="max-h-80 overflow-auto whitespace-pre-wrap px-3 py-3 text-xs leading-relaxed text-foreground/80">
                      {formatTraceValue(trace.parsed_output)}
                    </pre>
                  </div>
                </div>
              </StageResultPanel>
            ))}
          </div>
        )
      })}
    </div>
  )
}
