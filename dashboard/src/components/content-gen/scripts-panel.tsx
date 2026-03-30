'use client'

import { useEffect, useState } from 'react'
import { ChevronDown, ChevronRight } from 'lucide-react'
import useContentGen from '@/hooks/useContentGen'
import { ScriptViewer } from '@/components/content-gen/script-viewer'

export function ScriptsPanel() {
  const scripts = useContentGen((s) => s.scripts)
  const loadScripts = useContentGen((s) => s.loadScripts)
  const loading = useContentGen((s) => s.scriptsLoading)

  const [expandedId, setExpandedId] = useState<string | null>(null)
  const [scriptContent, setScriptContent] = useState<Record<string, string>>({})

  useEffect(() => {
    loadScripts()
  }, [loadScripts])

  const handleExpand = async (runId: string) => {
    if (expandedId === runId) {
      setExpandedId(null)
      return
    }

    setExpandedId(runId)

    if (!scriptContent[runId]) {
      try {
        const { getScript } = await import('@/lib/content-gen-api')
        const data = await getScript(runId)
        setScriptContent((prev) => ({ ...prev, [runId]: data.script || '' }))
      } catch {
        setScriptContent((prev) => ({ ...prev, [runId]: '[Error loading script]' }))
      }
    }
  }

  if (loading) {
    return <div className="text-muted-foreground text-sm py-8 text-center">Loading scripts...</div>
  }

  if (scripts.length === 0) {
    return (
      <div className="py-16 text-center">
        <p className="text-sm text-muted-foreground">No scripts yet.</p>
        <p className="text-xs text-muted-foreground/50 mt-1">
          Run the scripting pipeline to generate your first script.
        </p>
      </div>
    )
  }

  return (
    <div className="divide-y divide-border">
      {scripts.map((run) => (
        <div key={run.run_id} className="bg-surface">
          <button
            onClick={() => handleExpand(run.run_id)}
            className="w-full flex items-center justify-between px-3 py-3 text-sm hover:bg-surface-raised/50 transition-colors"
          >
            <div className="flex items-center gap-2 min-w-0">
              {expandedId === run.run_id ? (
                <ChevronDown className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
              ) : (
                <ChevronRight className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
              )}
              <span className="truncate text-foreground/80">{run.raw_idea || 'Untitled'}</span>
            </div>
            <div className="flex items-center gap-3 shrink-0 text-xs text-muted-foreground font-mono tabular-nums">
              <span>{run.word_count}w</span>
              <span className="hidden sm:inline">{run.saved_at}</span>
            </div>
          </button>
          {expandedId === run.run_id && (
            <div className="px-3 pb-4 pt-1 border-t border-border animate-fade-in">
              {scriptContent[run.run_id] ? (
                <ScriptViewer content={scriptContent[run.run_id]} />
              ) : (
                <p className="text-sm text-muted-foreground">Loading script...</p>
              )}
            </div>
          )}
        </div>
      ))}
    </div>
  )
}
