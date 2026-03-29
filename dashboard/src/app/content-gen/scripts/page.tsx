'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { ArrowLeft, ChevronDown, ChevronRight } from 'lucide-react'
import useContentGen from '@/hooks/useContentGen'
import { ScriptViewer } from '@/components/content-gen/script-viewer'

export default function ScriptsPage() {
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

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      <div className="flex items-center gap-3">
        <Link
          href="/content-gen"
          className="text-muted-foreground hover:text-foreground transition-colors"
        >
          <ArrowLeft className="h-5 w-5" />
        </Link>
        <div>
          <h1 className="text-xl font-bold">Script History</h1>
          <p className="text-sm text-muted-foreground">
            Browse past scripting runs
          </p>
        </div>
      </div>

      {loading && <p className="text-sm text-muted-foreground">Loading...</p>}

      {!loading && scripts.length === 0 && (
        <div className="text-center py-12 text-muted-foreground text-sm">
          No scripts yet. Run the scripting pipeline to generate your first script.
        </div>
      )}

      <div className="space-y-2">
        {scripts.map((run) => (
          <div key={run.run_id} className="border rounded-md">
            <button
              onClick={() => handleExpand(run.run_id)}
              className="w-full flex items-center justify-between px-4 py-3 text-sm hover:bg-muted/50 transition-colors"
            >
              <div className="flex items-center gap-3 min-w-0">
                {expandedId === run.run_id ? (
                  <ChevronDown className="h-4 w-4 shrink-0" />
                ) : (
                  <ChevronRight className="h-4 w-4 shrink-0" />
                )}
                <span className="truncate">{run.raw_idea || 'Untitled'}</span>
              </div>
              <div className="flex items-center gap-3 shrink-0 text-xs text-muted-foreground">
                <span>{run.word_count} words</span>
                <span>{run.saved_at}</span>
              </div>
            </button>
            {expandedId === run.run_id && (
              <div className="px-4 pb-4 pt-2 border-t">
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
    </div>
  )
}
