'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'

import { Badge } from '@/components/ui/badge'
import { ItemsView, ItemsViewHeader, ItemsViewLoading, ItemsViewEmpty, ItemsViewToggle, type ItemsViewMode } from '@/components/content-gen/items-view'
import { DataTable, type DataTableColumn } from '@/components/content-gen/data-table'
import { useScripts } from '@/hooks/useScripts'
import type { SavedScriptRun } from '@/types/content-gen'

interface ScriptsPanelProps {
  onReuseInputs?: (rawIdea: string) => void
}

type ScriptsViewMode = ItemsViewMode

export function ScriptsPanel({ onReuseInputs }: ScriptsPanelProps) {
  const scripts = useScripts((s) => s.scripts)
  const loadScripts = useScripts((s) => s.loadScripts)
  const loading = useScripts((s) => s.scriptsLoading)

  const [viewMode, setViewMode] = useState<ScriptsViewMode>('grid')
  const router = useRouter()

  useEffect(() => {
    if (scripts.length === 0) {
      void loadScripts()
    }
  }, [scripts.length, loadScripts])

  const navigateToDetail = (runId: string, e: React.MouseEvent) => {
    e.stopPropagation()
    router.push(`/content-gen/scripts/${runId}`)
  }

  const columns: DataTableColumn<SavedScriptRun>[] = [
  {
    id: 'script',
    header: 'Script',
    render: (run) => (
      <div className="space-y-1">
        <p className="text-sm font-medium text-foreground truncate max-w-md">
          {run.raw_idea || 'Untitled script'}
        </p>
        <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
          <span className="font-mono">{run.run_id.slice(0, 8)}</span>
        </div>
      </div>
    ),
    className: 'min-w-[22rem]',
  },
  {
    id: 'execution',
    header: 'Execution',
    render: (run) => (
      <Badge variant="outline">
        {run.execution_mode === 'iterative' ? 'Iterative' : 'Single pass'}
      </Badge>
    ),
  },
  {
    id: 'iterations',
    header: 'Iterations',
    render: (run) =>
      run.iterations ? (
        <span className="font-mono text-xs tabular-nums">
          {run.iterations.count}/{run.iterations.max_iterations}
        </span>
      ) : (
        <span className="text-xs text-muted-foreground">1</span>
      ),
  },
  {
    id: 'words',
    header: 'Words',
    render: (run) => (
      <span className="font-mono text-xs tabular-nums text-muted-foreground">
        {run.word_count.toLocaleString()}
      </span>
    ),
  },
  {
    id: 'saved',
    header: 'Saved',
    render: (run) => <span className="text-xs text-muted-foreground">{run.saved_at}</span>,
  },
]

  if (loading) {
    return <ItemsViewLoading label="scripts" />
  }

  if (scripts.length === 0) {
    return (
      <ItemsViewEmpty
        label="scripts"
        message="No scripts yet."
        secondaryMessage="Run the scripting pipeline to generate your first script."
      />
    )
  }

  return (
    <div className="space-y-4">
      <ItemsViewHeader
        title="Scripts"
        totalCount={scripts.length}
        controls={<ItemsViewToggle value={viewMode} onChange={setViewMode} label="Scripts" />}
      />

      <ItemsView mode={viewMode}>
        {viewMode === 'grid' ? (
          <>
            {scripts.map((run) => (
              <article
                key={run.run_id}
                role="button"
                tabIndex={0}
                onClick={(e) => navigateToDetail(run.run_id, e)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault()
                    router.push(`/content-gen/scripts/${run.run_id}`)
                  }
                }}
                className="group relative cursor-pointer overflow-hidden rounded-[0.95rem] border border-border/75 bg-card/95 p-4 shadow-[0_18px_48px_rgba(0,0,0,0.18)] transition-all duration-200 hover:-translate-y-1 hover:border-primary/35 hover:shadow-[0_22px_60px_rgba(12,18,30,0.28)] motion-reduce:transform-none motion-reduce:transition-none"
              >
                <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-primary/45 to-transparent opacity-60" />
                <div className="flex items-start justify-between gap-3">
                  <div className="space-y-3 flex-1 min-w-0">
                    <div className="flex flex-wrap gap-2">
                      <Badge variant="outline">
                        {run.execution_mode === 'iterative' ? 'Iterative' : 'Single pass'}
                      </Badge>
                      {run.iterations && (
                        <Badge variant="secondary">
                          {run.iterations.count}/{run.iterations.max_iterations} iter
                        </Badge>
                      )}
                    </div>
                    <div className="space-y-2">
                      <h3 className="text-base font-semibold leading-tight text-foreground truncate">
                        {run.raw_idea || 'Untitled script'}
                      </h3>
                      <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] uppercase tracking-[0.16em] text-muted-foreground">
                        <span className="font-mono">{run.run_id.slice(0, 8)}</span>
                        <span>{run.saved_at}</span>
                      </div>
                    </div>
                  </div>
                  <div className="min-w-[5.75rem] rounded-[0.95rem] border border-border/70 bg-background/45 px-3 py-2 text-right shadow-[inset_0_1px_0_rgba(255,255,255,0.04)]">
                    <p className="text-[10px] font-mono uppercase tracking-[0.18em] text-muted-foreground">
                      Words
                    </p>
                    <p className="mt-1 font-mono text-lg tabular-nums text-foreground">
                      {run.word_count.toLocaleString()}
                    </p>
                  </div>
                </div>

                {onReuseInputs && (
                  <div className="mt-4 flex justify-end">
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation()
                        onReuseInputs(run.raw_idea)
                      }}
                      className="text-xs text-primary/70 hover:text-primary transition-colors"
                    >
                      Reuse Inputs
                    </button>
                  </div>
                )}
              </article>
            ))}
          </>
        ) : (
          <DataTable
            columns={columns}
            data={scripts}
            keyField="run_id"
            onRowClick={(run, e) => navigateToDetail(run.run_id, e)}
          />
        )}
      </ItemsView>
    </div>
  )
}
