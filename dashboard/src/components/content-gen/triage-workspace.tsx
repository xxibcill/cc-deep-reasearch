'use client'

import { useState, useCallback, useMemo } from 'react'
import {
  AlertCircle,
  Check,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  Clock,
  GitMerge,
  Loader2,
  LogOut,
  RefreshCw,
  Sparkles,
  Trash2,
  X,
} from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { backlogTitle } from '@/components/content-gen/backlog-shared'
import { cn } from '@/lib/utils'
import { backlogTriageRespond, backlogTriageApply } from '@/lib/content-gen-api'
import useContentGen from '@/hooks/useContentGen'
import type { TriageOperation, TriageProposalKind, BacklogItem } from '@/types/content-gen'

const PROPOSAL_LABELS: Record<TriageProposalKind, { label: string; icon: typeof Sparkles; color: string }> = {
  batch_enrich: { label: 'Enrich', icon: Sparkles, color: 'text-primary' },
  batch_reframe: { label: 'Reframe', icon: RefreshCw, color: 'text-blue-500' },
  dedupe_recommendation: { label: 'Dedupe', icon: GitMerge, color: 'text-purple-500' },
  archive_recommendation: { label: 'Archive', icon: Trash2, color: 'text-warning' },
  priority_recommendation: { label: 'Priority', icon: Clock, color: 'text-green-500' },
}

type IndexedProposal = {
  index: number
  proposal: TriageOperation
}

type ProposalGroup = {
  kind: TriageProposalKind
  label: string
  icon: typeof Sparkles
  color: string
  items: IndexedProposal[]
}

interface TriageWorkspaceProps {
  onClose: () => void
}

export function TriageWorkspace({ onClose }: TriageWorkspaceProps) {
  const backlog = useContentGen((s) => s.backlog)
  const mergeBacklogItems = useContentGen((s) => s.mergeBacklogItems)

  const [allProposals, setAllProposals] = useState<TriageOperation[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [replyMarkdown, setReplyMarkdown] = useState<string>('')
  const [dismissedSet, setDismissedSet] = useState<Set<number>>(new Set())
  const [appliedSet, setAppliedSet] = useState<Set<number>>(new Set())
  const [selectedSet, setSelectedSet] = useState<Set<number>>(new Set())
  const [applyBusy, setApplyBusy] = useState(false)
  const [applyErrors, setApplyErrors] = useState<string[]>([])
  const [bulkResult, setBulkResult] = useState<{ applied: number; errors: string[] } | null>(null)

  const runTriage = useCallback(async () => {
    setLoading(true)
    setError(null)
    setAllProposals([])
    setDismissedSet(new Set())
    setAppliedSet(new Set())
    setSelectedSet(new Set())
    setReplyMarkdown('')
    setApplyErrors([])
    setBulkResult(null)

    try {
      const response = await backlogTriageRespond({ backlog_items: backlog })
      setAllProposals(response.proposals)
      setReplyMarkdown(response.reply_markdown)
      if (response.warnings.length > 0) {
        setError(response.warnings.join('; '))
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Triage analysis failed.')
    } finally {
      setLoading(false)
    }
  }, [backlog])

  const indexedProposals = useMemo((): IndexedProposal[] => {
    return allProposals
      .map((proposal, index) => ({ index, proposal }))
      .filter(({ index }) => !dismissedSet.has(index) && !appliedSet.has(index))
  }, [allProposals, dismissedSet, appliedSet])

  const groupedProposals = useMemo((): ProposalGroup[] => {
    const groups: Record<TriageProposalKind, IndexedProposal[]> = {
      batch_enrich: [],
      batch_reframe: [],
      dedupe_recommendation: [],
      archive_recommendation: [],
      priority_recommendation: [],
    }
    indexedProposals.forEach((item) => {
      groups[item.proposal.kind].push(item)
    })
    return Object.entries(groups)
      .filter(([, items]) => items.length > 0)
      .map(([kind, items]) => {
        const info = PROPOSAL_LABELS[kind as TriageProposalKind]
        return {
          kind: kind as TriageProposalKind,
          label: info.label,
          icon: info.icon,
          color: info.color,
          items,
        }
      })
  }, [indexedProposals])

  const dismissProposal = useCallback((index: number) => {
    setDismissedSet((prev) => new Set([...prev, index]))
    setSelectedSet((prev) => {
      const next = new Set(prev)
      next.delete(index)
      return next
    })
  }, [])

  const toggleSelectProposal = useCallback((index: number) => {
    setSelectedSet((prev) => {
      const next = new Set(prev)
      if (next.has(index)) {
        next.delete(index)
      } else {
        next.add(index)
      }
      return next
    })
  }, [])

  const selectAllInGroup = useCallback((group: ProposalGroup) => {
    setSelectedSet((prev) => {
      const next = new Set(prev)
      group.items.forEach((item) => next.add(item.index))
      return next
    })
  }, [])

  const deselectAllInGroup = useCallback((group: ProposalGroup) => {
    setSelectedSet((prev) => {
      const next = new Set(prev)
      group.items.forEach((item) => next.delete(item.index))
      return next
    })
  }, [])

  const applyProposal = useCallback(
    async (index: number, proposal: TriageOperation) => {
      setApplyBusy(true)
      setApplyErrors([])
      setBulkResult(null)

      try {
        const result = await backlogTriageApply({ operations: [proposal] })

        if (result.errors.length > 0) {
          setApplyErrors(result.errors)
          return
        }

        if (result.applied > 0) {
          setAppliedSet((prev) => new Set([...prev, index]))
          setSelectedSet((prev) => {
            const next = new Set(prev)
            next.delete(index)
            return next
          })
          mergeBacklogItems(result.items)
          setBulkResult({ applied: result.applied, errors: [] })
        }
      } catch (err) {
        setApplyErrors([err instanceof Error ? err.message : 'Apply failed.'])
      } finally {
        setApplyBusy(false)
      }
    },
    [mergeBacklogItems],
  )

  const applyAllVisible = useCallback(async () => {
    const visible = indexedProposals.map((i) => i.proposal)
    if (!visible.length || applyBusy) return

    setApplyBusy(true)
    setApplyErrors([])
    setBulkResult(null)

    try {
      const result = await backlogTriageApply({ operations: visible })

      if (result.errors.length > 0) {
        setApplyErrors(result.errors)
        setBulkResult({ applied: result.applied, errors: result.errors })
      }

      if (result.applied > 0) {
        setAppliedSet(new Set(indexedProposals.map((i) => i.index)))
        setSelectedSet(new Set())
        mergeBacklogItems(result.items)
        setBulkResult({ applied: result.applied, errors: result.errors })
      }
    } catch (err) {
      setApplyErrors([err instanceof Error ? err.message : 'Apply failed.'])
    } finally {
      setApplyBusy(false)
    }
  }, [indexedProposals, applyBusy, mergeBacklogItems])

  const applySelected = useCallback(async () => {
    const selected = indexedProposals
      .filter((p) => selectedSet.has(p.index))
      .map((i) => i.proposal)
    if (!selected.length || applyBusy) return

    setApplyBusy(true)
    setApplyErrors([])
    setBulkResult(null)

    try {
      const result = await backlogTriageApply({ operations: selected })

      const allErrors = [...result.errors]
      if (result.applied > 0) {
        const appliedIndices = indexedProposals
          .filter((p) => selectedSet.has(p.index))
          .map((i) => i.index)
        setAppliedSet((prev) => new Set([...prev, ...appliedIndices]))
        setSelectedSet(new Set())
        mergeBacklogItems(result.items)
      }
      setBulkResult({ applied: result.applied, errors: allErrors })
    } catch (err) {
      setApplyErrors([err instanceof Error ? err.message : 'Apply failed.'])
    } finally {
      setApplyBusy(false)
    }
  }, [indexedProposals, selectedSet, applyBusy, mergeBacklogItems])

  const rejectSelected = useCallback(() => {
    const toDismiss = indexedProposals
      .filter((p) => selectedSet.has(p.index))
      .map((i) => i.index)
    setDismissedSet((prev) => {
      const next = new Set(prev)
      toDismiss.forEach((idx) => next.add(idx))
      return next
    })
    setSelectedSet(new Set())
  }, [indexedProposals, selectedSet])

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between pb-3 border-b border-border/60">
        <div className="flex items-center gap-2">
          <Sparkles className="h-4 w-4 text-primary" />
          <span className="text-sm font-semibold text-foreground">AI Triage Workspace</span>
          <Badge variant="outline" className="bg-primary/8 text-primary border-primary/20">
            {indexedProposals.length} proposal{indexedProposals.length !== 1 ? 's' : ''}
          </Badge>
          {selectedSet.size > 0 && (
            <Badge variant="outline" className="bg-primary/12 text-primary border-primary/30">
              {selectedSet.size} selected
            </Badge>
          )}
        </div>
        <div className="flex items-center gap-2">
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={() => void runTriage()}
            disabled={loading}
            className="gap-1.5 h-8"
          >
            {loading ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
            ) : (
              <RefreshCw className="h-3.5 w-3.5" />
            )}
            Run triage
          </Button>
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={onClose}
            className="gap-1.5 h-8"
          >
            <LogOut className="h-3.5 w-3.5" />
            Close
          </Button>
        </div>
      </div>

      {/* Error banner */}
      {error && (
        <Alert variant="destructive" className="mt-3">
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {/* Apply errors / bulk result */}
      {applyErrors.length > 0 && (
        <Alert variant="destructive" className="mt-3">
          <AlertDescription className="text-xs">{applyErrors.join('; ')}</AlertDescription>
        </Alert>
      )}

      {bulkResult && (
        <Alert variant={bulkResult.errors.length > 0 ? 'destructive' : 'default'} className="mt-3">
          <AlertDescription className="text-xs">
            {bulkResult.applied > 0 ? `Applied ${bulkResult.applied} operation${bulkResult.applied !== 1 ? 's' : ''}.` : 'No operations applied.'}
            {bulkResult.errors.length > 0 && ` Errors: ${bulkResult.errors.join('; ')}`}
          </AlertDescription>
        </Alert>
      )}

      {/* Empty state / prompt */}
      {allProposals.length === 0 && !loading && (
        <div className="flex flex-col items-center justify-center flex-1 text-center py-12">
          <Sparkles className="h-10 w-10 text-muted-foreground/30 mb-3" />
          <p className="text-sm text-muted-foreground max-w-[20rem]">
            Run triage to analyze your backlog for duplicates, weak items, missing evidence, and
            reframe opportunities.
          </p>
          <Button
            type="button"
            variant="default"
            onClick={() => void runTriage()}
            disabled={loading}
            className="mt-4 gap-2"
          >
            {loading ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Sparkles className="h-4 w-4" />
            )}
            Run triage analysis
          </Button>
        </div>
      )}

      {/* AI summary */}
      {replyMarkdown && allProposals.length > 0 && (
        <div className="mt-3 rounded-[0.8rem] border border-border/70 bg-card/60 p-3">
          <p className="text-xs text-muted-foreground leading-relaxed">{replyMarkdown}</p>
        </div>
      )}

      {/* Proposal groups */}
      <div className="flex-1 overflow-y-auto space-y-4 mt-4 min-h-0">
        {groupedProposals.map((group) => (
          <ProposalGroupCard
            key={group.kind}
            group={group}
            backlog={backlog}
            selectedSet={selectedSet}
            onDismiss={dismissProposal}
            onToggleSelect={toggleSelectProposal}
            onSelectAll={() => selectAllInGroup(group)}
            onDeselectAll={() => deselectAllInGroup(group)}
            onApply={applyProposal}
            applyBusy={applyBusy}
          />
        ))}
      </div>

      {/* Footer actions */}
      {indexedProposals.length > 0 && (
        <div className="mt-4 pt-3 border-t border-border/60">
          {/* Bulk action bar - shows when items are selected */}
          {selectedSet.size > 0 && (
            <div className="flex items-center gap-3 mb-3 p-3 rounded-[0.8rem] border border-primary/25 bg-primary/5">
              <span className="text-xs text-muted-foreground">
                {selectedSet.size} selected
              </span>
              <div className="flex items-center gap-2 ml-auto">
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => void rejectSelected()}
                  disabled={applyBusy}
                  className="h-8 gap-1.5 text-warning border-warning/30 hover:bg-warning/10"
                >
                  <X className="h-3.5 w-3.5" />
                  Reject selected
                </Button>
                <Button
                  type="button"
                  variant="default"
                  size="sm"
                  onClick={() => void applySelected()}
                  disabled={applyBusy}
                  className="h-8 gap-1.5"
                >
                  {applyBusy ? (
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  ) : (
                    <CheckCircle2 className="h-3.5 w-3.5" />
                  )}
                  Apply selected
                </Button>
              </div>
            </div>
          )}

          <div className="flex items-center justify-between">
            <p className="text-xs text-muted-foreground">
              {indexedProposals.length} proposal{indexedProposals.length !== 1 ? 's' : ''} pending
              {selectedSet.size > 0 && ` · ${selectedSet.size} selected`}
            </p>
            <Button
              type="button"
              variant="default"
              size="sm"
              onClick={() => void applyAllVisible()}
              disabled={applyBusy || indexedProposals.length === 0}
              className="gap-1.5"
            >
              {applyBusy ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
              ) : (
                <CheckCircle2 className="h-3.5 w-3.5" />
              )}
              Apply all visible
            </Button>
          </div>
        </div>
      )}
    </div>
  )
}

interface ProposalGroupCardProps {
  group: ProposalGroup
  backlog: BacklogItem[]
  selectedSet: Set<number>
  onDismiss: (index: number) => void
  onToggleSelect: (index: number) => void
  onSelectAll: () => void
  onDeselectAll: () => void
  onApply: (index: number, proposal: TriageOperation) => Promise<void>
  applyBusy: boolean
}

function ProposalGroupCard({
  group,
  backlog,
  selectedSet,
  onDismiss,
  onToggleSelect,
  onSelectAll,
  onDeselectAll,
  onApply,
  applyBusy,
}: ProposalGroupCardProps) {
  const [expanded, setExpanded] = useState(true)
  const Icon = group.icon

  const allSelected = group.items.length > 0 && group.items.every((item) => selectedSet.has(item.index))
  const someSelected = group.items.some((item) => selectedSet.has(item.index))

  return (
    <div className="rounded-[0.95rem] border border-border/75 bg-card/80 shadow-sm overflow-hidden">
      {/* Group header */}
      <div className="flex items-center justify-between px-4 py-3">
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => (allSelected ? onDeselectAll() : onSelectAll())}
            className={cn(
              'flex items-center justify-center h-5 w-5 rounded border transition-colors',
              allSelected
                ? 'bg-primary border-primary text-primary-foreground'
                : someSelected
                  ? 'bg-primary/30 border-primary/50 text-primary'
                  : 'border-border/60 hover:border-primary/40'
            )}
            title={allSelected ? 'Deselect all' : 'Select all'}
          >
            {allSelected && <Check className="h-3 w-3" />}
            {someSelected && !allSelected && <div className="h-1.5 w-1.5 rounded-full bg-primary" />}
          </button>
          <Icon className={cn('h-4 w-4', group.color)} />
          <span className="text-sm font-semibold text-foreground">{group.label}</span>
          <Badge variant="outline" className="bg-background/50 text-muted-foreground border-border/60">
            {group.items.length}
          </Badge>
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => setExpanded((v) => !v)}
            className="p-1 text-muted-foreground/50 hover:text-foreground transition-colors rounded"
            title={expanded ? 'Collapse' : 'Expand'}
          >
            {expanded ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
          </button>
        </div>
      </div>

      {/* Proposal list */}
      {expanded && (
        <div className="border-t border-border/60 px-4 py-3 space-y-3">
          {group.items.map(({ index, proposal }) => (
            <TriageProposalCard
              key={index}
              proposal={proposal}
              backlog={backlog}
              selected={selectedSet.has(index)}
              onSelect={() => onToggleSelect(index)}
              onDismiss={() => onDismiss(index)}
              onApply={() => void onApply(index, proposal)}
              applyBusy={applyBusy}
            />
          ))}
        </div>
      )}
    </div>
  )
}

interface TriageProposalCardProps {
  proposal: TriageOperation
  backlog: BacklogItem[]
  selected: boolean
  onSelect: () => void
  onDismiss: () => void
  onApply: () => void
  applyBusy: boolean
}

function TriageProposalCard({
  proposal,
  backlog,
  selected,
  onSelect,
  onDismiss,
  onApply,
  applyBusy,
}: TriageProposalCardProps) {
  const [expanded, setExpanded] = useState(false)

  const affectedItems = proposal.idea_ids
    .map((id) => backlog.find((b) => b.idea_id === id))
    .filter(Boolean) as BacklogItem[]

  const changedFields = Object.keys(proposal.fields)

  return (
    <div className={cn(
      'rounded-[0.72rem] border bg-background/50 p-3 transition-colors',
      selected ? 'border-primary/40 bg-primary/5' : 'border-border/70'
    )}>
      {/* Header row */}
      <div className="flex items-start gap-2">
        <button
          type="button"
          onClick={onSelect}
          className={cn(
            'flex items-center justify-center h-5 w-5 rounded border shrink-0 mt-0.5 transition-colors',
            selected
              ? 'bg-primary border-primary text-primary-foreground'
              : 'border-border/60 hover:border-primary/40'
          )}
          title={selected ? 'Deselect' : 'Select'}
        >
          {selected && <Check className="h-3 w-3" />}
        </button>

        <div className="flex-1 min-w-0">
          <p className="text-xs text-muted-foreground leading-relaxed mb-2">{proposal.reason}</p>

          {/* Affected items */}
          <div className="flex flex-wrap gap-1.5 mb-2">
            {affectedItems.map((item) => (
              <Badge
                key={item.idea_id}
                variant="outline"
                className="bg-background/70 text-foreground/80 border-border/60 font-mono text-[10px]"
              >
                {backlogTitle(item).slice(0, 30)}
                {backlogTitle(item).length > 30 ? '…' : ''}
              </Badge>
            ))}
          </div>

          {/* Compact field list */}
          {!expanded && changedFields.length > 0 && (
            <p className="text-[10px] text-muted-foreground/60 font-mono">
              {changedFields.join(', ')}
            </p>
          )}

          {/* Preferred survivor for dedupe */}
          {proposal.kind === 'dedupe_recommendation' && proposal.preferred_idea_id && (
            <p className="text-[10px] text-muted-foreground/70 mt-1">
              Keep:{' '}
              <span className="font-mono text-primary/80">
                {(() => {
                  const survivor = backlog.find((b) => b.idea_id === proposal.preferred_idea_id)
                  return survivor ? backlogTitle(survivor).slice(0, 40) : proposal.preferred_idea_id
                })()}
              </span>
            </p>
          )}
        </div>

        {/* Actions */}
        <div className="flex items-center gap-1 shrink-0">
          <button
            onClick={onDismiss}
            className="p-1 text-muted-foreground/50 hover:text-foreground transition-colors rounded"
            title="Dismiss this proposal"
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

      {/* Expanded diff */}
      {expanded && changedFields.length > 0 && (
        <div className="mt-3 space-y-2">
          {changedFields.map((field) => {
            const targetItem =
              proposal.kind === 'dedupe_recommendation' && proposal.preferred_idea_id
                ? affectedItems.find((i) => i.idea_id === proposal.preferred_idea_id)
                : affectedItems[0]
            const current = targetItem ? String(targetItem[field as keyof BacklogItem] ?? '') : ''
            const proposed = String(proposal.fields[field] ?? '')
            const hasChange = current !== proposed

            return (
              <div key={field} className="grid grid-cols-[7rem_1fr] gap-x-3 gap-y-0.5 text-xs">
                <p className="font-mono uppercase tracking-[0.1em] text-muted-foreground/70">
                  {field}
                </p>
                <div className="text-muted-foreground/60">
                  {hasChange ? (
                    <div className="flex items-start gap-1.5">
                      <span className="line-through opacity-50">
                        {current || <em className="italic">empty</em>}
                      </span>
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
        </div>
      )}

      {/* Apply button */}
      <div className="mt-3 flex items-center justify-end">
        <Button
          type="button"
          variant="default"
          size="sm"
          onClick={onApply}
          disabled={applyBusy}
          className="gap-1.5 h-8"
        >
          {applyBusy ? (
            <Loader2 className="h-3 w-3 animate-spin" />
          ) : (
            <CheckCircle2 className="h-3 w-3" />
          )}
          Apply
        </Button>
      </div>
    </div>
  )
}
