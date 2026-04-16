'use client'

import { useState, useRef, useEffect } from 'react'
import { AlertCircle, Loader2, Send, Sparkles, CheckCircle2 } from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Textarea } from '@/components/ui/textarea'
import { cn } from '@/lib/utils'
import {
  briefAssistantRespond,
  briefAssistantApply,
} from '@/lib/content-gen-api'
import type {
  BriefAssistantMessage,
  BriefAssistantRespondResponse,
  BriefAssistantProposal,
} from '@/types/content-gen'
import { briefTitle } from '@/components/content-gen/brief-shared'

interface BriefAssistantPanelProps {
  briefId: string
  briefName: string
  revisionId: string
  onRevisionSaved?: () => void
}

export function BriefAssistantPanel({
  briefId,
  briefName,
  revisionId,
  onRevisionSaved,
}: BriefAssistantPanelProps) {
  const [messages, setMessages] = useState<BriefAssistantMessage[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [response, setResponse] = useState<BriefAssistantRespondResponse | null>(null)
  const [applying, setApplying] = useState(false)
  const [applyError, setApplyError] = useState<string | null>(null)
  const [mode, setMode] = useState<'conversation' | 'edit'>('edit')
  const messagesEndRef = useRef<HTMLDivElement>(null)

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages, response])

  const handleSend = async () => {
    if (!input.trim() || loading) return

    const userMessage: BriefAssistantMessage = { role: 'user', content: input.trim() }
    const newMessages = [...messages, userMessage]
    setMessages(newMessages)
    setInput('')
    setLoading(true)
    setError(null)
    setResponse(null)

    try {
      const result = await briefAssistantRespond(briefId, {
        messages: newMessages,
        revision_id: revisionId,
        mode,
      })
      setResponse(result)

      if (result.reply_markdown) {
        const assistantMessage: BriefAssistantMessage = {
          role: 'assistant',
          content: result.reply_markdown,
        }
        setMessages((prev) => [...prev, assistantMessage])
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to get response')
    } finally {
      setLoading(false)
    }
  }

  const handleApply = async () => {
    if (!response?.proposals?.length || applying) return

    setApplying(true)
    setApplyError(null)

    try {
      const result = await briefAssistantApply(briefId, {
        proposals: response.proposals.map((p) => ({
          reason: p.reason,
          fields: p.fields,
        })),
        revision_notes: `AI-assisted: ${response.proposals.length} proposal(s) applied`,
      })

      if (result.errors?.length > 0) {
        setApplyError(result.errors.join(', '))
      } else {
        setResponse(null)
        setMessages([])
        onRevisionSaved?.()
      }
    } catch (err) {
      setApplyError(err instanceof Error ? err.message : 'Failed to apply proposals')
    } finally {
      setApplying(false)
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      void handleSend()
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Sparkles className="h-4 w-4 text-primary" />
          <span className="text-sm font-medium text-foreground">Brief Assistant</span>
        </div>
        <div className="flex items-center gap-2">
          <Badge variant="outline" className="text-xs">
            {mode === 'conversation' ? 'Chat mode' : 'Edit mode'}
          </Badge>
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={() => setMode((m) => (m === 'conversation' ? 'edit' : 'conversation'))}
            className="h-7 text-xs"
          >
            Switch to {mode === 'conversation' ? 'edit' : 'chat'}
          </Button>
        </div>
      </div>

      {error && (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      <Card className="rounded-[1rem]">
        <CardContent className="p-4">
          <div className="space-y-4">
            {messages.length === 0 && !response && (
              <div className="text-center py-8 space-y-2">
                <Sparkles className="h-8 w-8 mx-auto text-muted-foreground/50" />
                <p className="text-sm text-muted-foreground">
                  Ask the assistant to refine &ldquo;{briefName}&rdquo;
                </p>
                <p className="text-xs text-muted-foreground/60">
                  {mode === 'edit'
                    ? 'Responses may include revision proposals you can apply.'
                    : 'Chat mode for discussion without proposals.'}
                </p>
              </div>
            )}

            {messages.map((msg, i) => (
              <div
                key={i}
                className={cn(
                  'flex gap-3',
                  msg.role === 'user' ? 'justify-end' : 'justify-start'
                )}
              >
                <div
                  className={cn(
                    'max-w-[85%] rounded-[0.8rem] px-4 py-3 text-sm',
                    msg.role === 'user'
                      ? 'bg-primary text-primary-foreground'
                      : 'bg-surface-raised border border-border/70'
                  )}
                >
                  <p className="whitespace-pre-wrap leading-relaxed">{msg.content}</p>
                </div>
              </div>
            ))}

            {loading && (
              <div className="flex items-center gap-2 text-muted-foreground">
                <Loader2 className="h-4 w-4 animate-spin" />
                <span className="text-sm">Assistant is thinking...</span>
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>

          {response && response.apply_ready && response.proposals.length > 0 && (
            <div className="mt-4 pt-4 border-t border-border/60 space-y-3">
              <div className="flex items-center gap-2">
                <CheckCircle2 className="h-4 w-4 text-success" />
                <span className="text-sm font-medium text-foreground">
                  {response.proposals.length} revision proposal{response.proposals.length === 1 ? '' : 's'} ready
                </span>
              </div>

              {response.warnings.length > 0 && (
                <Alert variant="warning" className="rounded-[0.8rem]">
                  <AlertDescription className="text-xs">
                    {response.warnings.join(' ')}
                  </AlertDescription>
                </Alert>
              )}

              <div className="space-y-2">
                {response.proposals.map((proposal, i) => (
                  <div
                    key={i}
                    className="rounded-[0.8rem] border border-border/70 bg-card/50 p-3 space-y-2"
                  >
                    <p className="text-xs font-medium text-foreground/80">
                      Proposal {i + 1}: {proposal.reason || 'Field changes'}
                    </p>
                    <div className="space-y-1">
                      {Object.entries(proposal.fields).map(([key, value]) => (
                        <div key={key} className="text-xs">
                          <span className="font-mono text-muted-foreground">{key}: </span>
                          <span className="text-foreground/80">
                            {Array.isArray(value) ? value.join(', ') : String(value)}
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                ))}
              </div>

              {applyError && (
                <Alert variant="destructive">
                  <AlertDescription>{applyError}</AlertDescription>
                </Alert>
              )}

              <div className="flex gap-2">
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => setResponse(null)}
                  disabled={applying}
                  className="gap-1.5"
                >
                  Dismiss
                </Button>
                <Button
                  type="button"
                  variant="default"
                  size="sm"
                  onClick={() => void handleApply()}
                  disabled={applying}
                  className="gap-1.5 bg-success hover:bg-success/90"
                >
                  {applying ? (
                    <>
                      <Loader2 className="h-3.5 w-3.5 animate-spin" />
                      Applying...
                    </>
                  ) : (
                    <>
                      <CheckCircle2 className="h-3.5 w-3.5" />
                      Apply {response.proposals.length} proposal{response.proposals.length === 1 ? '' : 's'}
                    </>
                  )}
                </Button>
              </div>
            </div>
          )}

          <div className="mt-4 flex gap-2">
            <Textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={
                mode === 'conversation'
                  ? 'Ask about the brief...'
                  : 'Suggest changes to the brief...'
              }
              className="min-h-[60px] resize-none rounded-[0.8rem]"
              disabled={loading}
            />
            <Button
              type="button"
              variant="default"
              size="icon"
              onClick={() => void handleSend()}
              disabled={loading || !input.trim()}
              className="h-[60px] w-[60px] shrink-0 rounded-[0.8rem]"
            >
              {loading ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Send className="h-4 w-4" />
              )}
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
