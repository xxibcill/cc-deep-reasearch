'use client'

import { useState, useRef, useEffect, useCallback } from 'react'
import { Send, Bot, AlertCircle, Loader2, Plus, Pencil, X, CheckCircle2, ChevronDown, ChevronUp, Trash2 } from 'lucide-react'
import ReactMarkdown from 'react-markdown'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { cn } from '@/lib/utils'
import { backlogChatRespond, backlogChatApply } from '@/lib/content-gen-api'
import useContentGen from '@/hooks/useContentGen'
import type { BacklogChatMessage, BacklogChatOperation, BacklogItem } from '@/types/content-gen'

const STORAGE_KEY = 'content-gen-chat-session'

interface TranscriptEntry {
  id: string
  role: 'user' | 'assistant'
  content: string
}

interface ChatThreadProps {
  backlog: BacklogItem[]
  selectedIdeaId: string | null
  onPendingOpsChange?: (ops: BacklogChatOperation[]) => void
  onApplyErrorsChange?: (errors: string[]) => void
}

interface PersistedSession {
  transcript: TranscriptEntry[]
  draftInput: string
  pendingOps: BacklogChatOperation[]
}

export function ChatThread({ backlog, selectedIdeaId, onPendingOpsChange, onApplyErrorsChange }: ChatThreadProps) {
  const loadBacklog = useContentGen((s) => s.loadBacklog)

  const [transcript, setTranscript] = useState<TranscriptEntry[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [pendingOps, setPendingOps] = useState<BacklogChatOperation[]>([])
  const [applyBusy, setApplyBusy] = useState(false)
  const [applyErrors, setApplyErrors] = useState<string[]>([])
  const transcriptEndRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)

  useEffect(() => {
    transcriptEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [transcript, pendingOps])

  // Persist session to localStorage whenever it changes
  useEffect(() => {
    try {
      const session: PersistedSession = {
        transcript,
        draftInput: input,
        pendingOps,
      }
      localStorage.setItem(STORAGE_KEY, JSON.stringify(session))
    } catch {
      // localStorage unavailable - ignore
    }
  }, [transcript, input, pendingOps])

  // Restore session from localStorage on mount
  useEffect(() => {
    try {
      const stored = localStorage.getItem(STORAGE_KEY)
      if (stored) {
        const session: PersistedSession = JSON.parse(stored)
        if (session.transcript?.length) setTranscript(session.transcript)
        if (session.draftInput) setInput(session.draftInput)
        if (session.pendingOps?.length) setPendingOps(session.pendingOps)
      }
    } catch {
      // Corrupt storage - ignore
    }
  }, [])

  // Listen for fill-composer events from parent (e.g. starter prompts)
  useEffect(() => {
    const handler = (e: Event) => {
      const ce = e as CustomEvent<string>
      setInput(ce.detail)
      inputRef.current?.focus()
    }
    window.addEventListener('chat-fill-composer', handler)
    return () => window.removeEventListener('chat-fill-composer', handler)
  }, [])

  const clearSession = useCallback(() => {
    setTranscript([])
    setInput('')
    setPendingOps([])
    setApplyErrors([])
    setError(null)
    onPendingOpsChange?.([])
    onApplyErrorsChange?.([])
    try {
      localStorage.removeItem(STORAGE_KEY)
    } catch {
      // ignore
    }
  }, [onPendingOpsChange, onApplyErrorsChange])

  const dismissOp = useCallback((index: number) => {
    setPendingOps((prev) => {
      const updated = prev.filter((_, i) => i !== index)
      onPendingOpsChange?.(updated)
      return updated
    })
  }, [onPendingOpsChange])

  const sendMessage = async () => {
    const trimmed = input.trim()
    if (!trimmed || loading) return

    const userEntry: TranscriptEntry = {
      id: `user-${Date.now()}`,
      role: 'user',
      content: trimmed,
    }

    setTranscript((prev) => [...prev, userEntry])
    setInput('')
    setError(null)
    setPendingOps([])
    setApplyErrors([])

    const messagesForApi: BacklogChatMessage[] = [
      ...transcript.map((e) => ({ role: e.role, content: e.content })),
      { role: 'user', content: trimmed },
    ]

    setLoading(true)

    try {
      const response = await backlogChatRespond({
        messages: messagesForApi,
        backlog_items: backlog,
        selected_idea_id: selectedIdeaId,
      })

      const assistantEntry: TranscriptEntry = {
        id: `asst-${Date.now()}`,
        role: 'assistant',
        content: response.reply_markdown,
      }

      setTranscript((prev) => [...prev, assistantEntry])

      if (response.operations.length > 0) {
        setPendingOps(response.operations)
        onPendingOpsChange?.(response.operations)
      }

      if (response.warnings.length > 0) {
        setError(response.warnings.join('; '))
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to get response.')
    } finally {
      setLoading(false)
    }
  }

  const applyChanges = async () => {
    if (!pendingOps.length || applyBusy) return

    setApplyBusy(true)
    setApplyErrors([])

    try {
      const result = await backlogChatApply({ operations: pendingOps })

      if (result.errors.length > 0) {
        setApplyErrors(result.errors)
        onApplyErrorsChange?.(result.errors)
      }

      if (result.applied > 0) {
        setPendingOps([])
        onPendingOpsChange?.([])
        setApplyErrors([])
        onApplyErrorsChange?.([])
        setTranscript((prev) => [
          ...prev,
          {
            id: `system-${Date.now()}`,
            role: 'assistant',
            content: `Applied ${result.applied} change${result.applied === 1 ? '' : 's'}. ${
              result.errors.length > 0 ? `(${result.errors.length} operation(s) failed.)` : ''
            }`,
          },
        ])
        void loadBacklog()
      }
    } catch (err) {
      const errMsg = err instanceof Error ? err.message : 'Apply failed.'
      setApplyErrors([errMsg])
      onApplyErrorsChange?.([errMsg])
    } finally {
      setApplyBusy(false)
    }
  }

  const clearProposal = () => {
    setPendingOps([])
    onPendingOpsChange?.([])
    setApplyErrors([])
    onApplyErrorsChange?.([])
  }

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      void sendMessage().catch((err) => {
        console.error('sendMessage failed:', err)
      })
    }
  }

  return (
    <div className="flex flex-col h-full">
      {/* Chat error banner */}
      {error && (
        <Alert variant="destructive" className="mb-3">
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {/* Transcript area */}
      <div className="flex-1 overflow-y-auto space-y-3 min-h-0">
        {transcript.length === 0 && (
          <div className="flex flex-col items-center justify-center h-full text-center py-8">
            <Bot className="h-8 w-8 text-muted-foreground/50 mb-3" />
            <p className="text-sm text-muted-foreground max-w-[18rem]">
              Ask about gaps, priorities, or reframes in your backlog.
              Changes require explicit apply.
            </p>
          </div>
        )}

        {transcript.map((entry) => (
          <div
            key={entry.id}
            className={cn(
              'flex gap-2 rounded-[0.8rem] p-3 text-sm',
              entry.role === 'user'
                ? 'bg-primary/5 border border-primary/10'
                : 'bg-card border border-border/60',
            )}
          >
            <div className="flex-1 text-foreground/88">
              <span className="font-mono text-[10px] uppercase tracking-[0.15em] text-muted-foreground/70 block mb-1">
                {entry.role === 'user' ? 'You' : 'Assistant'}
              </span>
              <div className="prose prose-sm prose-invert max-w-none text-foreground/88">
                <ReactMarkdown>{entry.content}</ReactMarkdown>
              </div>
            </div>
          </div>
        ))}

        {loading && (
          <div className="flex items-center gap-2 rounded-[0.8rem] p-3 bg-card border border-border/60">
            <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
            <span className="text-sm text-muted-foreground">Thinking...</span>
          </div>
        )}

        {/* Proposal card */}
        {pendingOps.length > 0 && !loading && (
          <div className="rounded-[0.95rem] border border-primary/25 bg-primary/[0.04] p-4 shadow-sm">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <CheckCircle2 className="h-4 w-4 text-primary" />
                <span className="text-sm font-semibold text-foreground">Proposed changes</span>
              </div>
              <div className="flex items-center gap-2">
                <button
                  onClick={clearSession}
                  className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground transition-colors"
                >
                  <Trash2 className="h-3 w-3" />
                  clear all
                </button>
                <button
                  onClick={clearProposal}
                  className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground transition-colors"
                >
                  <X className="h-3 w-3" />
                  dismiss
                </button>
              </div>
            </div>

            <div className="space-y-3 mb-4">
              {pendingOps.map((op, i) => {
                const targetItem = op.idea_id ? backlog.find((b) => b.idea_id === op.idea_id) ?? null : null
                return (
                  <OperationCard
                    key={i}
                    op={op}
                    targetItem={targetItem}
                    onDismiss={() => dismissOp(i)}
                  />
                )
              })}
            </div>

            {applyErrors.length > 0 && (
              <Alert variant="destructive" className="mb-3">
                <AlertDescription className="text-xs">
                  {applyErrors.join('; ')}
                </AlertDescription>
              </Alert>
            )}

            <Button
              onClick={() => void applyChanges()}
              disabled={applyBusy}
              className="w-full gap-2"
            >
              {applyBusy ? (
                <><Loader2 className="h-4 w-4 animate-spin" /> Applying...</>
              ) : (
                <><CheckCircle2 className="h-4 w-4" /> Apply changes</>
              )}
            </Button>
          </div>
        )}
        <div ref={transcriptEndRef} />
      </div>

      {/* Composer */}
      <div className="mt-3 pt-3 border-t border-border/60">
        <div className="flex gap-2">
          <textarea
            ref={inputRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask about your backlog..."
            disabled={loading}
            rows={2}
            className="flex-1 resize-none rounded-[0.8rem] border border-border/70 bg-background/60 px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground/50 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-primary/40 disabled:opacity-50"
          />
          <Button
            onClick={() => void sendMessage()}
            disabled={!input.trim() || loading}
            className="shrink-0 h-auto self-end gap-1.5 px-4"
          >
            <Send className="h-4 w-4" />
            Send
          </Button>
        </div>
        <p className="text-[10px] text-muted-foreground/60 mt-1.5 text-right">
          Enter to send &middot; Shift+Enter for newline
        </p>
      </div>
    </div>
  )
}

function OperationCard({
  op,
  targetItem,
  onDismiss,
}: {
  op: BacklogChatOperation
  targetItem: BacklogItem | null
  onDismiss: () => void
}) {
  const [expanded, setExpanded] = useState(false)
  const changedFields = Object.keys(op.fields)
  const isRisky =
    op.kind === 'update_item' &&
    (op.fields.status != null || op.fields.selection_reasoning != null)

  return (
    <div className={cn(
      'rounded-[0.72rem] bg-background/60 border p-3',
      isRisky ? 'border-warning/40 bg-warning/[0.03]' : 'border-border/50'
    )}>
      <div className="flex items-start gap-2">
        <Badge
          variant="outline"
          className={cn(
            'shrink-0 mt-0.5 bg-primary/8 text-primary border-primary/20',
            isRisky && 'border-warning/40 text-warning bg-warning/8'
          )}
        >
          {op.kind === 'create_item' ? (
            <><Plus className="h-3 w-3 mr-1" />create</>
          ) : (
            <><Pencil className="h-3 w-3 mr-1" />update</>
          )}
        </Badge>
        <div className="flex-1 min-w-0">
          <p className="text-xs text-muted-foreground mb-1 line-clamp-2">{op.reason}</p>
          {op.kind === 'update_item' && op.idea_id && (
            <div className="flex items-center gap-2">
              <p className="text-xs font-mono text-muted-foreground/70 truncate">
                {op.idea_id.slice(0, 8)}
              </p>
              {targetItem && (
                <span className="text-xs text-muted-foreground/50 truncate">
                  {targetItem.idea.slice(0, 40)}
                </span>
              )}
            </div>
          )}
        </div>
        <div className="flex items-center gap-1 shrink-0">
          <button
            onClick={onDismiss}
            className="p-1 text-muted-foreground/50 hover:text-foreground transition-colors rounded"
            title="Dismiss this operation"
          >
            <X className="h-3 w-3" />
          </button>
          <button
            onClick={() => setExpanded((v) => !v)}
            className="p-1 text-muted-foreground/50 hover:text-foreground transition-colors rounded"
            title={expanded ? 'Collapse' : 'Expand'}
          >
            {expanded ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
          </button>
        </div>
      </div>

      {/* Compact field list */}
      {!expanded && changedFields.length > 0 && (
        <p className="text-xs text-muted-foreground/60 mt-1.5 pl-1">
          {changedFields.join(', ')}
        </p>
      )}

      {/* Expanded before/after diff */}
      {expanded && changedFields.length > 0 && (
        <div className="mt-3 space-y-2 pl-1">
          {changedFields.map((field) => {
            const current = targetItem ? String(targetItem[field as keyof BacklogItem] ?? '') : ''
            const proposed = String(op.fields[field] ?? '')
            const hasChange = current !== proposed
            return (
              <div key={field} className="grid grid-cols-[7rem_1fr] gap-x-3 gap-y-0.5 text-xs">
                <p className="font-mono uppercase tracking-[0.1em] text-muted-foreground/70">
                  {field}
                </p>
                <div className="text-muted-foreground/60">
                  {hasChange ? (
                    <div className="flex items-start gap-1.5">
                      <span className="line-through opacity-50">{current || <em className="italic">empty</em>}</span>
                      <span className="text-muted-foreground/30">→</span>
                      <span className="text-foreground font-medium">{proposed}</span>
                    </div>
                  ) : (
                    <span>{current || <em className="italic">empty</em>}</span>
                  )}
                </div>
              </div>
            )
          })}
          {op.kind === 'create_item' && (
            <div className="mt-1">
              <p className="text-[10px] font-mono uppercase tracking-[0.1em] text-muted-foreground/50 mb-1">
                New item preview
              </p>
              {changedFields.map((field) => (
                <div key={field} className="grid grid-cols-[7rem_1fr] gap-x-3 gap-y-0.5 text-xs">
                  <p className="font-mono uppercase tracking-[0.1em] text-muted-foreground/70">
                    {field}
                  </p>
                  <p className="text-foreground/80">{String(op.fields[field] ?? '')}</p>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
