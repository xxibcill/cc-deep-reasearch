'use client'

import { useEffect, useMemo } from 'react'
import { Bot, AlertCircle, Loader2, ListChecks, Check, MessageSquare, ChevronRight, Sparkles, AlertTriangle, Clock, TrendingUp } from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { cn } from '@/lib/utils'
import type { BacklogItem } from '@/types/content-gen'
import {
  formatProductionStatus,
  hasActiveProductionStatus,
  productionStatusBadgeVariant,
  recommendationBadgeVariant,
  statusBadgeVariant,
} from '@/components/content-gen/backlog-shared'
import { ChatThread } from '@/components/content-gen/chat-thread'
import { useBacklog } from '@/hooks/useBacklog'

interface BacklogInsight {
  id: string
  icon: React.ReactNode
  label: string
  description: string
  severity: 'info' | 'warning' | 'critical'
}

function deriveInsights(backlog: BacklogItem[]): BacklogInsight[] {
  const insights: BacklogInsight[] = []

  // No selected item
  const selectedCount = backlog.filter((i) => i.status === 'selected').length
  if (backlog.length > 0 && selectedCount === 0) {
    insights.push({
      id: 'no-selection',
      icon: <Sparkles className="h-3.5 w-3.5" />,
      label: 'No item selected',
      description: 'Select an item to focus the assistant context for editing decisions.',
      severity: 'warning',
    })
  }

  // Duplicate/near-duplicate idea themes
  const ideasByTheme = new Map<string, number>()
  for (const item of backlog) {
    if (item.source_theme) {
      ideasByTheme.set(item.source_theme, (ideasByTheme.get(item.source_theme) ?? 0) + 1)
    }
  }
  for (const [theme, count] of ideasByTheme) {
    if (count >= 3) {
      insights.push({
        id: `theme-concentration-${theme}`,
        icon: <TrendingUp className="h-3.5 w-3.5" />,
        label: `Theme concentration: ${theme}`,
        description: `${count} items share this theme — consider diversifying.`,
        severity: count >= 5 ? 'critical' : 'warning',
      })
    }
  }

  // Items missing evidence
  const missingEvidence = backlog.filter((i) => !i.evidence && i.status !== 'archived')
  if (missingEvidence.length > backlog.length * 0.5 && backlog.length >= 4) {
    insights.push({
      id: 'missing-evidence',
      icon: <AlertTriangle className="h-3.5 w-3.5" />,
      label: 'Weak evidence coverage',
      description: `${missingEvidence.length} items lack supporting evidence — claims may be harder to defend.`,
      severity: missingEvidence.length > backlog.length * 0.7 ? 'critical' : 'info',
    })
  }

  // Category concentration
  const cats = backlog.filter((i) => i.category).map((i) => i.category)
  const catCounts = new Map<string, number>()
  for (const c of cats) catCounts.set(c, (catCounts.get(c) ?? 0) + 1)
  for (const [cat, count] of catCounts) {
    if (count >= backlog.length * 0.6 && backlog.length >= 4) {
      insights.push({
        id: `category-concentration-${cat}`,
        icon: <ListChecks className="h-3.5 w-3.5" />,
        label: `Category imbalance: ${cat}`,
        description: `${count} of ${backlog.length} items share this category — review for variety.`,
        severity: 'info',
      })
      break
    }
  }

  // Stale items (not updated in 30+ days)
  const staleThreshold = Date.now() - 30 * 24 * 60 * 60 * 1000
  const staleItems = backlog.filter((i) => {
    if (!i.updated_at || i.status === 'archived') return false
    return new Date(i.updated_at).getTime() < staleThreshold
  })
  if (staleItems.length >= 3) {
    insights.push({
      id: 'stale-items',
      icon: <Clock className="h-3.5 w-3.5" />,
      label: `${staleItems.length} stale items`,
      description: 'These items have not been updated in over 30 days — review for relevance.',
      severity: 'info',
    })
  }

  return insights
}

interface ChatWorkspaceProps {
  className?: string
}

export function ChatWorkspace({ className }: ChatWorkspaceProps) {
  const backlog = useBacklog((s) => s.backlog)
  const backlogLoading = useBacklog((s) => s.backlogLoading)
  const loadBacklog = useBacklog((s) => s.loadBacklog)
  const error = useBacklog((s) => s.error)

  const selectedItem = backlog.find((i) => i.status === 'selected')
  const selectedItemCount = backlog.filter((i) => i.status === 'selected').length
  const selectedIdeaId = selectedItem?.idea_id ?? null

  const insights = useMemo(() => deriveInsights(backlog), [backlog])

  const starterPrompts = [
    { label: 'Plan next focus', prompt: 'I want to plan what my next backlog focus should be. Help me narrow the goal first.' },
    { label: 'Sort priorities', prompt: 'Help me sort this backlog into what should move now, later, or get reframed.' },
    { label: 'Find audience gaps', prompt: 'Look at this backlog and help me spot audience or problem gaps before we edit anything.' },
    { label: 'Shape rough ideas', prompt: 'I have rough ideas but not clean hooks yet. Help me shape them before we update the backlog.' },
  ]

  useEffect(() => {
    if (backlog.length === 0) {
      void loadBacklog()
    }
  }, [backlog.length, loadBacklog])

  return (
    <div className={cn('flex flex-col h-full', className)}>
      {/* Page header */}
      <div className="flex flex-col gap-4 pb-4 border-b border-border/60">
        <div className="flex items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-[0.9rem] bg-primary/10 border border-primary/20">
              <MessageSquare className="h-5 w-5 text-primary" />
            </div>
            <div>
              <h1 className="text-lg font-semibold text-foreground">Backlog Planning Chat</h1>
              <p className="text-xs text-muted-foreground">Plan conversationally first, then use `/edit` when you want a backlog patch</p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            {backlogLoading ? (
              <Badge variant="secondary" className="gap-1.5">
                <Loader2 className="h-3 w-3 animate-spin" />
                Loading
              </Badge>
            ) : error ? (
              <Badge variant="destructive" className="gap-1">
                <AlertCircle className="h-3 w-3" />
                Error
              </Badge>
            ) : (
              <>
                <Badge variant="outline" className="gap-1.5">
                  <ListChecks className="h-3 w-3" />
                  {backlog.length} item{backlog.length !== 1 ? 's' : ''}
                </Badge>
                {selectedItemCount > 0 && (
                  <Badge variant="success" className="gap-1.5 bg-success/10 text-success border-success/20">
                    <Check className="h-3 w-3" />
                    {selectedItemCount} selected
                  </Badge>
                )}
              </>
            )}
          </div>
        </div>

        {/* Backlog error banner */}
        {error && (
          <Alert variant="destructive" className="py-2">
            <AlertCircle className="h-4 w-4" />
            <AlertDescription className="text-xs">Failed to load backlog: {error}</AlertDescription>
          </Alert>
        )}

        {/* Backlog insights */}
        {insights.length > 0 && !backlogLoading && !error && (
          <div className="flex flex-wrap gap-2">
            {insights.map((insight) => (
              <div
                key={insight.id}
                className={cn(
                  'flex items-center gap-2 rounded-[0.8rem] border px-3 py-1.5 text-xs',
                  insight.severity === 'critical' && 'border-error/40 bg-error/5 text-error',
                  insight.severity === 'warning' && 'border-warning/40 bg-warning/5 text-warning',
                  insight.severity === 'info' && 'border-border/70 bg-card/60 text-muted-foreground',
                )}
              >
                {insight.icon}
                <span className="font-medium">{insight.label}</span>
                <span className="opacity-80">{insight.description}</span>
              </div>
            ))}
          </div>
        )}

        {/* Starter prompts */}
        {!backlogLoading && !error && backlog.length > 0 && (
          <div className="flex flex-wrap gap-2">
            <span className="text-[10px] font-mono uppercase tracking-[0.15em] text-muted-foreground/60 self-center">
              Quick actions:
            </span>
            {starterPrompts.map((sp) => (
              <button
                key={sp.label}
                type="button"
                onClick={() => {
                  // Fill the composer with the prompt text - ChatThread will be the one to handle
                  // We dispatch a custom event that ChatThread listens to
                  window.dispatchEvent(new CustomEvent('chat-fill-composer', { detail: sp.prompt }))
                }}
                className="rounded-[0.8rem] border border-border/70 bg-card/60 px-3 py-1.5 text-xs text-muted-foreground hover:text-foreground hover:border-primary/30 transition-colors"
              >
                {sp.label}
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Workspace body: chat + context rail */}
      <div className="flex flex-1 min-h-0 pt-4 gap-4">
        {/* Main chat area */}
        <div className="flex-1 min-w-0">
          <ChatThread
            backlog={backlog}
            selectedIdeaId={selectedIdeaId}
            variant="planner"
          />
        </div>

        {/* Backlog context rail - hidden on mobile */}
        <aside className="hidden lg:flex w-72 xl:w-80 flex-col gap-4 shrink-0">
          {/* Selected item card */}
          {selectedItem ? (
            <div className="rounded-[1rem] border border-border/75 bg-card/80 p-4 shadow-sm">
              <div className="flex items-center gap-2 mb-3">
                <Sparkles className="h-4 w-4 text-primary" />
                <span className="text-sm font-semibold text-foreground">Selected Item</span>
              </div>
              <div className="space-y-3">
                <div className="flex flex-wrap gap-2">
                  <Badge variant={statusBadgeVariant(selectedItem.status)}>
                    {selectedItem.status}
                  </Badge>
                  {hasActiveProductionStatus(selectedItem.production_status) ? (
                    <Badge variant={productionStatusBadgeVariant(selectedItem.production_status)}>
                      {formatProductionStatus(selectedItem.production_status)}
                    </Badge>
                  ) : null}
                  <Badge variant="outline">{selectedItem.category || 'uncategorized'}</Badge>
                  <Badge variant={recommendationBadgeVariant(selectedItem.latest_recommendation)}>
                    {selectedItem.latest_recommendation || 'unscored'}
                  </Badge>
                </div>
                <div className="space-y-2">
                  <p className="text-sm font-medium text-foreground line-clamp-2">
                    {selectedItem.idea}
                  </p>
                  <div className="flex items-center gap-2 text-xs text-muted-foreground">
                    <span className="font-mono">{selectedItem.idea_id.slice(0, 8)}</span>
                    {selectedItem.latest_score !== undefined && (
                      <span>Score: {selectedItem.latest_score}</span>
                    )}
                  </div>
                </div>
                {selectedItem.selection_reasoning && (
                  <p className="text-xs text-muted-foreground/80 border-t border-border/60 pt-2">
                    {selectedItem.selection_reasoning}
                  </p>
                )}
              </div>
            </div>
          ) : (
            <div className="rounded-[1rem] border border-dashed border-border/75 bg-card/40 p-4">
              <div className="flex flex-col items-center justify-center text-center py-4">
                <div className="flex h-10 w-10 items-center justify-center rounded-full bg-muted/50 mb-3">
                  <ListChecks className="h-5 w-5 text-muted-foreground/60" />
                </div>
                <p className="text-sm font-medium text-foreground mb-1">No item selected</p>
                <p className="text-xs text-muted-foreground">
                  Select an item from the backlog to focus the assistant context.
                </p>
              </div>
            </div>
          )}

          {/* Backlog summary */}
          <div className="rounded-[1rem] border border-border/75 bg-card/80 p-4 shadow-sm">
            <div className="flex items-center justify-between mb-3">
              <span className="text-sm font-semibold text-foreground">Backlog Summary</span>
              <ChevronRight className="h-4 w-4 text-muted-foreground/60" />
            </div>
            <div className="space-y-2">
              <div className="flex items-center justify-between text-xs">
                <span className="text-muted-foreground">Total items</span>
                <span className="font-medium text-foreground">{backlog.length}</span>
              </div>
              <div className="flex items-center justify-between text-xs">
                <span className="text-muted-foreground">In production</span>
                <span className="font-medium text-foreground">
                  {backlog.filter((i) => i.production_status === 'in_production').length}
                </span>
              </div>
              <div className="flex items-center justify-between text-xs">
                <span className="text-muted-foreground">Ready to publish</span>
                <span className="font-medium text-foreground">
                  {backlog.filter((i) => i.production_status === 'ready_to_publish').length}
                </span>
              </div>
              <div className="flex items-center justify-between text-xs">
                <span className="text-muted-foreground">Archived</span>
                <span className="font-medium text-foreground">
                  {backlog.filter((i) => i.status === 'archived').length}
                </span>
              </div>
            </div>
            <div className="mt-3 pt-3 border-t border-border/60">
              <p className="text-[10px] uppercase tracking-[0.15em] text-muted-foreground mb-2">
                Categories
              </p>
              <div className="flex flex-wrap gap-1.5">
                {[...new Set(backlog.map((i) => i.category).filter(Boolean))].map((cat) => (
                  <Badge key={cat} variant="outline" className="text-[10px]">
                    {cat}
                  </Badge>
                ))}
                {backlog.filter((i) => !i.category).length > 0 && (
                  <Badge variant="secondary" className="text-[10px]">
                    uncategorized ({backlog.filter((i) => !i.category).length})
                  </Badge>
                )}
              </div>
            </div>
          </div>
        </aside>
      </div>
    </div>
  )
}
