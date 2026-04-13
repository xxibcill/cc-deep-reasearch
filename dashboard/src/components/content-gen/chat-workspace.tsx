'use client'

import { useEffect } from 'react'
import { Bot, AlertCircle, Loader2, ListChecks, Check, MessageSquare, ChevronRight, Sparkles } from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { cn } from '@/lib/utils'
import useContentGen from '@/hooks/useContentGen'
import { statusBadgeVariant, recommendationBadgeVariant } from '@/components/content-gen/backlog-shared'
import { ChatThread } from '@/components/content-gen/chat-thread'

interface ChatWorkspaceProps {
  className?: string
}

export function ChatWorkspace({ className }: ChatWorkspaceProps) {
  const backlog = useContentGen((s) => s.backlog)
  const backlogLoading = useContentGen((s) => s.backlogLoading)
  const backlogError = useContentGen((s) => s.error)
  const loadBacklog = useContentGen((s) => s.loadBacklog)

  const selectedItem = backlog.find((i) => i.status === 'selected')
  const selectedItemCount = backlog.filter((i) => i.status === 'selected').length
  const selectedIdeaId = selectedItem?.idea_id ?? null

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
              <h1 className="text-lg font-semibold text-foreground">Backlog Assistant</h1>
              <p className="text-xs text-muted-foreground">Propose and apply backlog changes</p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            {backlogLoading ? (
              <Badge variant="secondary" className="gap-1.5">
                <Loader2 className="h-3 w-3 animate-spin" />
                Loading
              </Badge>
            ) : backlogError ? (
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
        {backlogError && (
          <Alert variant="destructive" className="py-2">
            <AlertCircle className="h-4 w-4" />
            <AlertDescription className="text-xs">Failed to load backlog: {backlogError}</AlertDescription>
          </Alert>
        )}
      </div>

      {/* Workspace body: chat + context rail */}
      <div className="flex flex-1 min-h-0 pt-4 gap-4">
        {/* Main chat area */}
        <div className="flex-1 min-w-0">
          <ChatThread
            backlog={backlog}
            selectedIdeaId={selectedIdeaId}
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
                  {backlog.filter((i) => i.status === 'in_production').length}
                </span>
              </div>
              <div className="flex items-center justify-between text-xs">
                <span className="text-muted-foreground">Published</span>
                <span className="font-medium text-foreground">
                  {backlog.filter((i) => i.status === 'published').length}
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
