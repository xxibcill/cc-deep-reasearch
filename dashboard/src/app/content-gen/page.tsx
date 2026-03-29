'use client'

import { useEffect } from 'react'
import Link from 'next/link'
import { Play, FileText, Settings, ListVideo, BookOpen } from 'lucide-react'
import useContentGen from '@/hooks/useContentGen'

const NAV_ITEMS = [
  { href: '/content-gen/pipeline/new', label: 'New Pipeline', icon: Play },
  { href: '/content-gen/scripting', label: 'Scripting', icon: FileText },
  { href: '/content-gen/strategy', label: 'Strategy', icon: Settings },
  { href: '/content-gen/scripts', label: 'Past Scripts', icon: BookOpen },
  { href: '/content-gen/publish', label: 'Publish Queue', icon: ListVideo },
]

export default function ContentGenPage() {
  const pipelines = useContentGen((s) => s.pipelines)
  const loadPipelines = useContentGen((s) => s.loadPipelines)
  const scripts = useContentGen((s) => s.scripts)
  const loadScripts = useContentGen((s) => s.loadScripts)

  useEffect(() => {
    loadPipelines()
    loadScripts()
  }, [loadPipelines, loadScripts])

  const activePipelines = pipelines.filter(
    (p) => p.status === 'running' || p.status === 'queued'
  )
  const recentScripts = scripts.slice(0, 5)

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Content Generation</h1>
        <p className="text-muted-foreground text-sm mt-1">
          Create short-form video content with AI
        </p>
      </div>

      {/* Navigation cards */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
        {NAV_ITEMS.map(({ href, label, icon: Icon }) => (
          <Link
            key={href}
            href={href}
            className="flex flex-col items-center gap-2 p-4 border rounded-md hover:bg-muted/50 transition-colors"
          >
            <Icon className="h-6 w-6 text-muted-foreground" />
            <span className="text-sm font-medium">{label}</span>
          </Link>
        ))}
      </div>

      {/* Active pipelines */}
      {activePipelines.length > 0 && (
        <div>
          <h2 className="text-lg font-semibold mb-3">Active Pipelines</h2>
          <div className="space-y-2">
            {activePipelines.map((p) => (
              <Link
                key={p.pipeline_id}
                href={`/content-gen/pipeline/${p.pipeline_id}`}
                className="block p-3 border rounded-md hover:bg-muted/50 transition-colors"
              >
                <div className="flex items-center justify-between">
                  <span className="font-medium text-sm">{p.theme}</span>
                  <span className="text-xs text-blue-600 bg-blue-50 px-2 py-0.5 rounded-full">
                    Stage {p.current_stage + 1}/12
                  </span>
                </div>
                <span className="text-xs text-muted-foreground font-mono">
                  {p.pipeline_id}
                </span>
              </Link>
            ))}
          </div>
        </div>
      )}

      {/* Recent scripts */}
      {recentScripts.length > 0 && (
        <div>
          <h2 className="text-lg font-semibold mb-3">Recent Scripts</h2>
          <div className="space-y-1">
            {recentScripts.map((s) => (
              <div
                key={s.run_id}
                className="flex items-center justify-between p-2 text-sm"
              >
                <span className="truncate max-w-[60%]">{s.raw_idea}</span>
                <span className="text-xs text-muted-foreground">
                  {s.word_count} words
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
