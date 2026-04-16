'use client'

import { useEffect, useState } from 'react'
import { useParams, useRouter } from 'next/navigation'
import {
  ArrowLeft,
  CheckCircle2,
  Copy,
  GitBranch,
  GitCompare,
  History,
  Loader2,
  Play,
  RotateCcw,
  Save,
  Sparkles,
  Trash2,
} from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogBody, DialogFooter } from '@/components/ui/dialog'
import { NativeSelect } from '@/components/ui/native-select'
import { Textarea } from '@/components/ui/textarea'
import { Input } from '@/components/ui/input'
import {
  lifecycleStateBadgeVariant,
  lifecycleStateLabel,
  provenanceLabel,
  formatBriefTimestamp,
  briefRevisionSummary,
  LIFECYCLE_STATE_OPTIONS,
} from '@/components/content-gen/brief-shared'
import { BriefAssistantPanel } from '@/components/content-gen/brief-assistant-panel'
import { BriefToBacklogPanel } from '@/components/content-gen/brief-to-backlog-panel'
import { LineagePanel } from '@/components/content-gen/lineage-panel'
import { CompareBriefsDialog } from '@/components/content-gen/compare-briefs-dialog'
import useContentGen from '@/hooks/useContentGen'
import type { BriefRevision, ManagedOpportunityBrief } from '@/types/content-gen'

export default function BriefDetailPage() {
  const params = useParams()
  const router = useRouter()
  const briefId = params.id as string

  const loadBrief = useContentGen((s) => s.loadBrief)
  const loadBriefRevisions = useContentGen((s) => s.loadBriefRevisions)
  const approveBrief = useContentGen((s) => s.approveBrief)
  const archiveBrief = useContentGen((s) => s.archiveBrief)
  const supersedeBrief = useContentGen((s) => s.supersedeBrief)
  const revertBriefToDraft = useContentGen((s) => s.revertBriefToDraft)
  const cloneBrief = useContentGen((s) => s.cloneBrief)
  const branchBrief = useContentGen((s) => s.branchBrief)
  const loadSiblingBriefs = useContentGen((s) => s.loadSiblingBriefs)
  const saveBriefRevision = useContentGen((s) => s.saveBriefRevision)
  const applyRevision = useContentGen((s) => s.applyRevision)
  const briefs = useContentGen((s) => s.briefs)
  const activeBriefRevisions = useContentGen((s) => s.activeBriefRevisions)
  const siblingBriefs = useContentGen((s) => s.siblingBriefs)
  const error = useContentGen((s) => s.error)

  const [brief, setBrief] = useState<(ManagedOpportunityBrief & { current_revision?: BriefRevision }) | null>(null)
  const [loading, setLoading] = useState(true)
  const [actionError, setActionError] = useState<string | null>(null)
  const [busyKey, setBusyKey] = useState<string | null>(null)
  const [selectedRevisionId, setSelectedRevisionId] = useState<string | null>(null)
  const [revisionNotes, setRevisionNotes] = useState('')
  const [compareOpen, setCompareOpen] = useState(false)
  const [compareRevisions, setCompareRevisions] = useState<[string, string] | null>(null)
  const [activeTab, setActiveTab] = useState<'content' | 'revisions' | 'assistant' | 'backlog' | 'lineage'>('content')
  const [editingField, setEditingField] = useState<string | null>(null)
  const [editedContent, setEditedContent] = useState<Record<string, unknown> | null>(null)
  const [branchOpen, setBranchOpen] = useState(false)
  const [branchTitle, setBranchTitle] = useState('')
  const [branchReason, setBranchReason] = useState('')
  const [compareBriefOpen, setCompareBriefOpen] = useState(false)
  const [compareWithBriefId, setCompareWithBriefId] = useState<string | null>(null)

  function isManagedBrief(b: unknown): b is ManagedOpportunityBrief & { current_revision?: BriefRevision } {
    return typeof b === 'object' && b !== null && 'brief_id' in b
  }

  useEffect(() => {
    if (!briefId) return
    setLoading(true)
    Promise.all([loadBrief(briefId), loadBriefRevisions(briefId)]).then((results) => {
      const b = results[0]
      setBrief(isManagedBrief(b) ? b : null)
      setLoading(false)
    })
  }, [briefId, loadBrief, loadBriefRevisions])

  const currentBrief = briefs.find((b) => b.brief_id === briefId) || brief

  const runAction = async (key: string, action: () => Promise<void>) => {
    try {
      setBusyKey(key)
      setActionError(null)
      await action()
    } catch (err) {
      setActionError(err instanceof Error ? err.message : String(err))
    } finally {
      setBusyKey(null)
    }
  }

  const handleApprove = () => {
    if (!currentBrief) return
    void runAction('approve', async () => {
      await approveBrief(currentBrief.brief_id, currentBrief.updated_at)
      const updated = await loadBrief(currentBrief.brief_id)
      if (updated) setBrief(updated as ManagedOpportunityBrief & { current_revision?: BriefRevision })
    })
  }

  const handleArchive = () => {
    if (!currentBrief) return
    void runAction('archive', async () => {
      await archiveBrief(currentBrief.brief_id, currentBrief.updated_at)
      const updated = await loadBrief(currentBrief.brief_id)
      if (updated) setBrief(updated as ManagedOpportunityBrief & { current_revision?: BriefRevision })
    })
  }

  const handleSupersede = () => {
    if (!currentBrief) return
    void runAction('supersede', async () => {
      await supersedeBrief(currentBrief.brief_id, currentBrief.updated_at)
      const updated = await loadBrief(currentBrief.brief_id)
      if (updated) setBrief(updated as ManagedOpportunityBrief & { current_revision?: BriefRevision })
    })
  }

  const handleRevertToDraft = () => {
    if (!currentBrief) return
    void runAction('revert', async () => {
      await revertBriefToDraft(currentBrief.brief_id, currentBrief.updated_at)
      const updated = await loadBrief(currentBrief.brief_id)
      if (updated) setBrief(updated as ManagedOpportunityBrief & { current_revision?: BriefRevision })
    })
  }

  const handleClone = () => {
    if (!currentBrief) return
    void runAction('clone', async () => {
      const newId = await cloneBrief(currentBrief.brief_id)
      if (newId) {
        router.push(`/content-gen/briefs/${newId}`)
      }
    })
  }

  const handleBranch = () => {
    if (!currentBrief) return
    void runAction('branch', async () => {
      const newId = await branchBrief(
        currentBrief.brief_id,
        branchTitle || undefined,
        branchReason || undefined,
      )
      if (newId) {
        setBranchOpen(false)
        setBranchTitle('')
        setBranchReason('')
        router.push(`/content-gen/briefs/${newId}`)
      }
    })
  }

  const handleApplyRevision = (revisionId: string) => {
    if (!currentBrief) return
    void runAction(`apply-${revisionId}`, async () => {
      await applyRevision(currentBrief.brief_id, revisionId, currentBrief.updated_at)
      const updated = await loadBrief(currentBrief.brief_id)
      if (updated) setBrief(updated as ManagedOpportunityBrief & { current_revision?: BriefRevision })
      await loadBriefRevisions(currentBrief.brief_id)
    })
  }

  const handleSaveRevision = () => {
    if (!currentBrief || !editedContent) return
    void runAction('save-revision', async () => {
      await saveBriefRevision(
        currentBrief.brief_id,
        editedContent as Record<string, unknown>,
        revisionNotes,
      )
      setEditingField(null)
      setEditedContent(null)
      setRevisionNotes('')
      const updated = await loadBrief(currentBrief.brief_id)
      setBrief(updated as (ManagedOpportunityBrief & { current_revision?: BriefRevision }) | null)
    })
  }

  const startEditing = (revision: BriefRevision) => {
    setEditedContent({
      theme: revision.theme,
      goal: revision.goal,
      primary_audience_segment: revision.primary_audience_segment,
      secondary_audience_segments: revision.secondary_audience_segments,
      problem_statements: revision.problem_statements,
      content_objective: revision.content_objective,
      proof_requirements: revision.proof_requirements,
      platform_constraints: revision.platform_constraints,
      risk_constraints: revision.risk_constraints,
      freshness_rationale: revision.freshness_rationale,
      sub_angles: revision.sub_angles,
      research_hypotheses: revision.research_hypotheses,
      success_criteria: revision.success_criteria,
      expert_take: revision.expert_take,
      non_obvious_claims_to_test: revision.non_obvious_claims_to_test,
      genericity_risks: revision.genericity_risks,
    })
    setEditingField(revision.revision_id)
  }

  if (loading) {
    return <div className="py-8 text-center text-sm text-muted-foreground">Loading brief...</div>
  }

  if (!currentBrief) {
    return (
      <div className="space-y-4">
        <Button type="button" variant="ghost" onClick={() => router.back()} className="gap-2">
          <ArrowLeft className="h-4 w-4" />
          Back
        </Button>
        <Alert variant="destructive">
          <AlertDescription>Brief not found.</AlertDescription>
        </Alert>
      </div>
    )
  }

  const currentRevision = currentBrief.current_revision
  const isHeadRevision = (rev: BriefRevision) => rev.revision_id === currentBrief.current_revision_id

  return (
    <div className="space-y-6">
      {actionError && (
        <Alert variant="destructive">
          <AlertDescription>{actionError}</AlertDescription>
        </Alert>
      )}

      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Button type="button" variant="ghost" onClick={() => router.push('/content-gen/briefs')} className="gap-2">
            <ArrowLeft className="h-4 w-4" />
            Back
          </Button>
          <div>
            <h1 className="text-lg font-display font-semibold tracking-tight">{currentBrief.title}</h1>
            <p className="mt-0.5 text-xs font-mono text-muted-foreground">{currentBrief.brief_id}</p>
          </div>
          <Badge variant={lifecycleStateBadgeVariant(currentBrief.lifecycle_state)}>
            {lifecycleStateLabel(currentBrief.lifecycle_state)}
          </Badge>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-[11px] font-mono text-muted-foreground tabular-nums">
            {currentBrief.revision_count} revision{currentBrief.revision_count === 1 ? '' : 's'}
          </span>
          {currentBrief.lifecycle_state === 'draft' && (
            <Button
              type="button"
              variant="default"
              size="sm"
              onClick={handleApprove}
              disabled={!!busyKey}
              className="gap-2 bg-success text-background hover:bg-success/90"
            >
              <CheckCircle2 className="h-3.5 w-3.5" />
              Approve
            </Button>
          )}
          {currentBrief.lifecycle_state === 'approved' && (
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={handleSupersede}
              disabled={!!busyKey}
              className="gap-2"
            >
              <RotateCcw className="h-3.5 w-3.5" />
              Supersede
            </Button>
          )}
          <Button type="button" variant="outline" size="sm" onClick={handleClone} disabled={!!busyKey} className="gap-2">
            <Copy className="h-3.5 w-3.5" />
            Clone
          </Button>
          <Button type="button" variant="outline" size="sm" onClick={() => setBranchOpen(true)} disabled={!!busyKey} className="gap-2">
            <GitBranch className="h-3.5 w-3.5" />
            Branch
          </Button>
          {currentBrief.lifecycle_state !== 'archived' && (
            <Button type="button" variant="outline" size="sm" onClick={handleArchive} disabled={!!busyKey} className="gap-2">
              <Trash2 className="h-3.5 w-3.5" />
              Archive
            </Button>
          )}
        </div>
      </div>

      <div className="flex gap-1 border-b border-border">
        {(['content', 'revisions', 'assistant', 'backlog', 'lineage'] as const).map((tab) => (
          <button
            key={tab}
            type="button"
            onClick={() => setActiveTab(tab)}
            className={`px-4 py-2 text-sm capitalize transition-colors ${
              activeTab === tab
                ? 'border-b-2 border-primary text-foreground'
                : 'text-muted-foreground hover:text-foreground'
            }`}
          >
            {tab === 'assistant' ? (
              <span className="flex items-center gap-1.5">
                <Sparkles className="h-3.5 w-3.5" />
                Assistant
              </span>
            ) : tab === 'backlog' ? (
              <span className="flex items-center gap-1.5">
                <GitBranch className="h-3.5 w-3.5" />
                Backlog
              </span>
            ) : (
              tab
            )}
          </button>
        ))}
      </div>

      {activeTab === 'content' && (
        <div className="space-y-6">
          {currentRevision ? (
            <div className="space-y-6">
              <div className="grid gap-4 lg:grid-cols-2">
                <Card className="rounded-[1rem]">
                  <CardHeader>
                    <CardTitle className="text-base">Theme & Goal</CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <div>
                      <p className="text-[10px] font-mono uppercase tracking-[0.18em] text-muted-foreground">Theme</p>
                      <p className="mt-1 text-sm text-foreground/88">{currentRevision.theme || '—'}</p>
                    </div>
                    <div>
                      <p className="text-[10px] font-mono uppercase tracking-[0.18em] text-muted-foreground">Goal</p>
                      <p className="mt-1 text-sm text-foreground/88">{currentRevision.goal || '—'}</p>
                    </div>
                    <div>
                      <p className="text-[10px] font-mono uppercase tracking-[0.18em] text-muted-foreground">Content Objective</p>
                      <p className="mt-1 text-sm text-foreground/88">{currentRevision.content_objective || '—'}</p>
                    </div>
                  </CardContent>
                </Card>

                <Card className="rounded-[1rem]">
                  <CardHeader>
                    <CardTitle className="text-base">Audience</CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <div>
                      <p className="text-[10px] font-mono uppercase tracking-[0.18em] text-muted-foreground">Primary</p>
                      <p className="mt-1 text-sm text-foreground/88">{currentRevision.primary_audience_segment || '—'}</p>
                    </div>
                    {currentRevision.secondary_audience_segments?.length > 0 && (
                      <div>
                        <p className="text-[10px] font-mono uppercase tracking-[0.18em] text-muted-foreground">Secondary</p>
                        <div className="mt-1 flex flex-wrap gap-1">
                          {currentRevision.secondary_audience_segments.map((seg, i) => (
                            <Badge key={i} variant="outline">{seg}</Badge>
                          ))}
                        </div>
                      </div>
                    )}
                    <div>
                      <p className="text-[10px] font-mono uppercase tracking-[0.18em] text-muted-foreground">Problem Statements</p>
                      <ul className="mt-1 space-y-1">
                        {(currentRevision.problem_statements || []).map((ps, i) => (
                          <li key={i} className="text-sm text-foreground/88">• {ps}</li>
                        ))}
                      </ul>
                    </div>
                  </CardContent>
                </Card>

                <Card className="rounded-[1rem]">
                  <CardHeader>
                    <CardTitle className="text-base">Research & Proof</CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <div>
                      <p className="text-[10px] font-mono uppercase tracking-[0.18em] text-muted-foreground">Research Hypotheses</p>
                      <ul className="mt-1 space-y-1">
                        {(currentRevision.research_hypotheses || []).map((rh, i) => (
                          <li key={i} className="text-sm text-foreground/88">• {rh}</li>
                        ))}
                      </ul>
                    </div>
                    <div>
                      <p className="text-[10px] font-mono uppercase tracking-[0.18em] text-muted-foreground">Proof Requirements</p>
                      <ul className="mt-1 space-y-1">
                        {(currentRevision.proof_requirements || []).map((pr, i) => (
                          <li key={i} className="text-sm text-foreground/88">• {pr}</li>
                        ))}
                      </ul>
                    </div>
                  </CardContent>
                </Card>

                <Card className="rounded-[1rem]">
                  <CardHeader>
                    <CardTitle className="text-base">Constraints & Quality</CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <div>
                      <p className="text-[10px] font-mono uppercase tracking-[0.18em] text-muted-foreground">Platform Constraints</p>
                      <ul className="mt-1 space-y-1">
                        {(currentRevision.platform_constraints || []).map((pc, i) => (
                          <li key={i} className="text-sm text-foreground/88">• {pc}</li>
                        ))}
                      </ul>
                    </div>
                    <div>
                      <p className="text-[10px] font-mono uppercase tracking-[0.18em] text-muted-foreground">Risk Constraints</p>
                      <ul className="mt-1 space-y-1">
                        {(currentRevision.risk_constraints || []).map((rc, i) => (
                          <li key={i} className="text-sm text-foreground/88">• {rc}</li>
                        ))}
                      </ul>
                    </div>
                    <div>
                      <p className="text-[10px] font-mono uppercase tracking-[0.18em] text-muted-foreground">Non-Obvious Claims</p>
                      <ul className="mt-1 space-y-1">
                        {(currentRevision.non_obvious_claims_to_test || []).map((noc, i) => (
                          <li key={i} className="text-sm text-foreground/88">• {noc}</li>
                        ))}
                      </ul>
                    </div>
                  </CardContent>
                </Card>
              </div>

              {currentBrief.lifecycle_state === 'draft' && (
                <Card className="rounded-[1rem]">
                  <CardHeader>
                    <div className="flex items-center justify-between">
                      <CardTitle className="text-base">Save Revision</CardTitle>
                      <Button
                        type="button"
                        variant="default"
                        size="sm"
                        onClick={() => startEditing(currentRevision)}
                        className="gap-2"
                      >
                        <Save className="h-3.5 w-3.5" />
                        Edit & Save Revision
                      </Button>
                    </div>
                  </CardHeader>
                </Card>
              )}
            </div>
          ) : (
            <div className="rounded-xl border border-dashed border-border bg-card/70 py-16 text-center">
              <p className="text-sm text-muted-foreground">No current revision available.</p>
            </div>
          )}
        </div>
      )}

      {activeTab === 'revisions' && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <p className="text-sm font-medium text-foreground">
              {activeBriefRevisions.length} revision{activeBriefRevisions.length === 1 ? '' : 's'}
            </p>
            {activeBriefRevisions.length >= 2 && (
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => {
                  const sorted = [...activeBriefRevisions].sort((a, b) => a.version - b.version)
                  setCompareRevisions([sorted[0].revision_id, sorted[1].revision_id])
                  setCompareOpen(true)
                }}
                className="gap-2"
              >
                <GitCompare className="h-3.5 w-3.5" />
                Compare
              </Button>
            )}
          </div>

          {activeBriefRevisions.length === 0 ? (
            <div className="rounded-xl border border-dashed border-border bg-card/70 py-16 text-center">
              <p className="text-sm text-muted-foreground">No revisions saved yet.</p>
            </div>
          ) : (
            <div className="space-y-3">
              {activeBriefRevisions.map((rev) => {
                const isHead = isHeadRevision(rev)
                return (
                  <Card key={rev.revision_id} className={`rounded-[1rem] ${isHead ? 'border-primary/40' : ''}`}>
                    <CardContent className="p-4">
                      <div className="flex items-start justify-between gap-4">
                        <div className="space-y-2 flex-1 min-w-0">
                          <div className="flex items-center gap-2 flex-wrap">
                            <Badge variant={isHead ? 'success' : 'outline'}>
                              v{rev.version} {isHead ? '(head)' : ''}
                            </Badge>
                            <span className="text-xs font-mono text-muted-foreground">{rev.revision_id.slice(0, 12)}</span>
                            <span className="text-xs text-muted-foreground">{formatBriefTimestamp(rev.created_at)}</span>
                          </div>
                          <p className="text-sm text-foreground/88 truncate">{rev.theme || 'No theme'}</p>
                          {rev.revision_notes && (
                            <p className="text-xs text-muted-foreground/80">{rev.revision_notes}</p>
                          )}
                        </div>
                        <div className="flex items-center gap-1 shrink-0">
                          {!isHead && (
                            <Button
                              type="button"
                              variant="ghost"
                              size="sm"
                              onClick={() => handleApplyRevision(rev.revision_id)}
                              disabled={!!busyKey}
                              className="h-8 gap-1 text-xs"
                              title="Apply as head"
                            >
                              <Play className="h-3 w-3" />
                              Apply
                            </Button>
                          )}
                          <Button
                            type="button"
                            variant="ghost"
                            size="sm"
                            onClick={() => {
                              setSelectedRevisionId(rev.revision_id)
                            }}
                            className="h-8 gap-1 text-xs"
                            title="View revision"
                          >
                            <History className="h-3 w-3" />
                            View
                          </Button>
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                )
              })}
            </div>
          )}
        </div>
      )}

      {activeTab === 'assistant' && currentBrief && currentRevision && (
        <BriefAssistantPanel
          briefId={currentBrief.brief_id}
          briefName={currentBrief.title}
          revisionId={currentRevision.revision_id}
          onRevisionSaved={async () => {
            const updated = await loadBrief(currentBrief.brief_id)
            if (updated) setBrief(updated as ManagedOpportunityBrief & { current_revision?: BriefRevision })
            await loadBriefRevisions(currentBrief.brief_id)
          }}
        />
      )}

      {activeTab === 'backlog' && currentBrief && currentRevision && (
        <BriefToBacklogPanel
          briefId={currentBrief.brief_id}
          briefName={currentBrief.title}
          onItemsApplied={() => {
            void router.push('/content-gen/backlog')
          }}
        />
      )}

      {activeTab === 'lineage' && currentBrief && (
        <div className="space-y-6">
          <LineagePanel
            brief={currentBrief}
            siblingBriefs={siblingBriefs}
            onLoadSiblings={() => loadSiblingBriefs(currentBrief.brief_id)}
            onCompareWith={(otherBriefId) => {
              setCompareWithBriefId(otherBriefId)
              setCompareBriefOpen(true)
            }}
            onNavigateToBrief={(id) => router.push(`/content-gen/briefs/${id}`)}
          />
        </div>
      )}

      {editingField && editedContent && (
        <Dialog open={true} onOpenChange={(open) => !open && setEditingField(null)}>
          <DialogContent className="max-w-2xl max-h-[85vh] overflow-y-auto">
            <DialogHeader>
              <DialogTitle>Edit & Save Revision</DialogTitle>
              <DialogDescription>
                Make changes to the brief content and save as a new revision.
                The current head will not be changed.
              </DialogDescription>
            </DialogHeader>
            <DialogBody className="space-y-4">
              <div className="space-y-3">
                {(['theme', 'goal', 'primary_audience_segment', 'content_objective'] as const).map((field) => (
                  <div key={field} className="space-y-1">
                    <label className="text-xs font-mono uppercase tracking-[0.18em] text-muted-foreground capitalize">
                      {field.replace(/_/g, ' ')}
                    </label>
                    <Textarea
                      value={String(editedContent[field] || '')}
                      onChange={(e) => setEditedContent({ ...editedContent, [field]: e.target.value })}
                      className="min-h-[60px]"
                    />
                  </div>
                ))}
              </div>
              <div className="space-y-1">
                <label className="text-xs font-mono uppercase tracking-[0.18em] text-muted-foreground">
                  Revision Notes
                </label>
                <Textarea
                  value={revisionNotes}
                  onChange={(e) => setRevisionNotes(e.target.value)}
                  placeholder="Describe what changed in this revision..."
                  className="min-h-[60px]"
                />
              </div>
            </DialogBody>
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => setEditingField(null)}>
                Cancel
              </Button>
              <Button
                type="button"
                variant="default"
                onClick={handleSaveRevision}
                disabled={!!busyKey || !revisionNotes.trim()}
              >
                {busyKey === 'save-revision' ? 'Saving...' : 'Save Revision'}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      )}

      {compareOpen && compareRevisions && (
        <Dialog open={true} onOpenChange={(open) => !open && setCompareOpen(false)}>
          <DialogContent className="max-w-3xl max-h-[85vh] overflow-y-auto">
            <DialogHeader>
              <DialogTitle>Compare Revisions</DialogTitle>
            </DialogHeader>
            <DialogBody>
              <p className="text-sm text-muted-foreground mb-4">
                Comparing {compareRevisions[0]} and {compareRevisions[1]}
              </p>
              <div className="space-y-6">
                {(['theme', 'goal', 'primary_audience_segment', 'content_objective'] as const).map((field) => {
                  const rev0 = activeBriefRevisions.find((r) => r.revision_id === compareRevisions[0])
                  const rev1 = activeBriefRevisions.find((r) => r.revision_id === compareRevisions[1])
                  const val0 = rev0 ? String(rev0[field] || '') : ''
                  const val1 = rev1 ? String(rev1[field] || '') : ''
                  const changed = val0 !== val1
                  return (
                    <div key={field} className="space-y-2">
                      <p className="text-xs font-mono uppercase tracking-[0.18em] text-muted-foreground capitalize">
                        {field.replace(/_/g, ' ')} {changed && <span className="text-warning">(changed)</span>}
                      </p>
                      <div className="grid grid-cols-2 gap-4">
                        <div className={`rounded-lg border p-3 ${changed ? 'border-warning/50 bg-warning/5' : 'border-border'}`}>
                          <p className="text-[10px] font-mono text-muted-foreground mb-1">
                            v{rev0?.version} ({formatBriefTimestamp(rev0?.created_at)})
                          </p>
                          <p className="text-sm whitespace-pre-wrap">{val0 || '—'}</p>
                        </div>
                        <div className={`rounded-lg border p-3 ${changed ? 'border-primary/50 bg-primary/5' : 'border-border'}`}>
                          <p className="text-[10px] font-mono text-muted-foreground mb-1">
                            v{rev1?.version} ({formatBriefTimestamp(rev1?.created_at)})
                          </p>
                          <p className="text-sm whitespace-pre-wrap">{val1 || '—'}</p>
                        </div>
                      </div>
                    </div>
                  )
                })}
              </div>
            </DialogBody>
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => setCompareOpen(false)}>
                Close
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      )}

      {branchOpen && (
        <Dialog open={true} onOpenChange={(open) => !open && setBranchOpen(false)}>
          <DialogContent className="max-w-lg">
            <DialogHeader>
              <DialogTitle>Branch Brief</DialogTitle>
              <DialogDescription>
                Create a derivative brief for a different theme, channel, or experiment.
                The branched brief tracks its lineage back to this source.
              </DialogDescription>
            </DialogHeader>
            <DialogBody className="space-y-4">
              <div className="space-y-2">
                <label className="text-xs font-mono uppercase tracking-[0.18em] text-muted-foreground">
                  New Brief Title (optional)
                </label>
                <input
                  type="text"
                  value={branchTitle}
                  onChange={(e) => setBranchTitle(e.target.value)}
                  placeholder={`${currentBrief?.title || 'Brief'} (branch)`}
                  className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm"
                />
              </div>
              <div className="space-y-2">
                <label className="text-xs font-mono uppercase tracking-[0.18em] text-muted-foreground">
                  Branch Reason
                </label>
                <Textarea
                  value={branchReason}
                  onChange={(e) => setBranchReason(e.target.value)}
                  placeholder="Why are you branching this brief? (e.g., 'different channel - TikTok', 'experiment for Q2 campaign')"
                  className="min-h-[80px]"
                />
              </div>
            </DialogBody>
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => setBranchOpen(false)}>
                Cancel
              </Button>
              <Button
                type="button"
                variant="default"
                onClick={() => void handleBranch()}
                disabled={!!busyKey}
                className="gap-1.5"
              >
                {busyKey === 'branch' ? (
                  <>
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                    Branching...
                  </>
                ) : (
                  <>
                    <GitBranch className="h-3.5 w-3.5" />
                    Create Branch
                  </>
                )}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      )}

      {compareBriefOpen && compareWithBriefId && (
        <CompareBriefsDialog
          briefId={currentBrief?.brief_id || ''}
          otherBriefId={compareWithBriefId}
          onClose={() => {
            setCompareBriefOpen(false)
            setCompareWithBriefId(null)
          }}
        />
      )}
    </div>
  )
}