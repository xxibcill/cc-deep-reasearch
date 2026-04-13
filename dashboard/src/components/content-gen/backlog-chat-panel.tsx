'use client'

import { useState, useRef, useEffect } from 'react'
import { Send, Bot, AlertCircle, CheckCircle2, Loader2, Plus, Pencil, X } from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { cn } from '@/lib/utils'
import { backlogChatRespond, backlogChatApply } from '@/lib/content-gen-api'
import type { BacklogChatMessage, BacklogChatOperation, BacklogItem } from '@/types/content-gen'

interface BacklogChatPanelProps {
  items: BacklogItem[]
  selectedIdeaId?: string | null
  onItemsChanged?: () => void
}

interface TranscriptEntry {
  id: string
  role: 'user' | 'assistant'
  content: string
}

export function BacklogChatPanel({ items, selectedIdeaId, onItemsChanged }: BacklogChatPanelProps) {
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
        backlog_items: items,
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
      }

      if (result.applied > 0) {
        setPendingOps([])
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
        onItemsChanged?.()
      }
    } catch (err) {
      setApplyErrors([err instanceof Error ? err.message : 'Apply failed.'])
    } finally {
      setApplyBusy(false)
    }
  }

  const clearProposal = () => {
    setPendingOps([])
    setApplyErrors([])
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
      {/* Header */}
      <div className="flex items-center gap-3 pb-3 border-b border-border/60">
        <div className="flex h-9 w-9 items-center justify-center rounded-[0.8rem] bg-primary/10 border border-primary/20">
          <Bot className="h-4 w-4 text-primary" />
        </div>
        <div>
          <p className="text-sm font-semibold text-foreground">Backlog Assistant</p>
          <p className="text-xs text-muted-foreground">Propose backlog changes</p>
        </div>
      </div>

      {/* Error banner */}
      {error && (
        <Alert variant="destructive" className="mt-3">
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {/* Transcript area */}
      <div className="flex-1 overflow-y-auto mt-3 space-y-3 min-h-0">
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
              <span className="whitespace-pre-wrap">{entry.content}</span>
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
              <button
                onClick={clearProposal}
                className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground transition-colors"
              >
                <X className="h-3 w-3" />
                dismiss
              </button>
            </div>

            <div className="space-y-2 mb-4">
              {pendingOps.map((op, i) => (
                <div key={i} className="flex items-start gap-2 rounded-[0.72rem] bg-background/60 p-3 border border-border/50">
                  <Badge variant="outline" className="shrink-0 mt-0.5 bg-primary/8 text-primary border-primary/20">
                    {op.kind === 'create_item' ? (
                      <><Plus className="h-3 w-3 mr-1" />create</>
                    ) : (
                      <><Pencil className="h-3 w-3 mr-1" />update</>
                    )}
                  </Badge>
                  <div className="flex-1 min-w-0">
                    <p className="text-xs text-muted-foreground mb-1 line-clamp-2">{op.reason}</p>
                    {op.kind === 'update_item' && op.idea_id && (
                      <p className="text-xs font-mono text-muted-foreground/70 truncate">
                        target: {op.idea_id.slice(0, 8)}
                      </p>
                    )}
                    {Object.keys(op.fields).length > 0 && (
                      <p className="text-xs text-muted-foreground/70 mt-1">
                        fields: {Object.keys(op.fields).join(', ')}
                      </p>
                    )}
                  </div>
                </div>
              ))}
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