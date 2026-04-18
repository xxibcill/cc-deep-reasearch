'use client'

import { useEffect, useState } from 'react'
import { Check, Save, X } from 'lucide-react'
import type {
  AudienceSegment,
  ContentExample,
  ContentPillar,
  PlatformRule,
  StrategyMemory,
} from '@/types/content-gen'
import {
  getStrategy,
  updateStrategy,
} from '@/lib/content-gen-api'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { Tabs } from '@/components/ui/tabs'
import { TagInput } from '@/components/ui/tag-input'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import {
  Dialog,
  DialogBody,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import {
  ContentPillarEditor,
  AudienceSegmentEditor,
  PlatformRuleEditor,
  CTAStrategyEditor,
  ContentExampleEditor,
} from './editors'
import {
  HealthPanel,
  ReadinessPanel,
  RulesForReviewPanel,
  OperatingFitnessPanel,
  ImportExportPanel,
} from './strategy-panels'

// ---------------------------------------------------------------------------
// StrategyWorkspace
// ---------------------------------------------------------------------------

type StrategyTab = 'health' | 'niche' | 'pillars' | 'audience' | 'platforms' | 'claims' | 'examples' | 'advanced'

export function StrategyWorkspace() {
  const [strategy, setStrategy] = useState<StrategyMemory | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [saved, setSaved] = useState(false)
  const [hasChanges, setHasChanges] = useState(false)
  const [activeTab, setActiveTab] = useState<StrategyTab>('health')
  const [discardOpen, setDiscardOpen] = useState(false)

  // Track original strategy for change detection
  const [originalStrategy, setOriginalStrategy] = useState<StrategyMemory | null>(null)

  useEffect(() => {
    void loadStrategy()
  }, [])

  const loadStrategy = async () => {
    try {
      setLoading(true)
      const data = await getStrategy()
      setStrategy(data)
      setOriginalStrategy(data)
      setHasChanges(false)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load strategy')
    } finally {
      setLoading(false)
    }
  }

  const handleSave = async () => {
    if (!strategy) return

    try {
      setSaving(true)
      setError(null)

      const patch: Record<string, unknown> = {}
      if (strategy.niche !== originalStrategy?.niche) patch.niche = strategy.niche
      if (JSON.stringify(strategy.content_pillars) !== JSON.stringify(originalStrategy?.content_pillars))
        patch.content_pillars = strategy.content_pillars
      if (JSON.stringify(strategy.tone_rules) !== JSON.stringify(originalStrategy?.tone_rules))
        patch.tone_rules = strategy.tone_rules
      if (JSON.stringify(strategy.platforms) !== JSON.stringify(originalStrategy?.platforms))
        patch.platforms = strategy.platforms
      if (JSON.stringify(strategy.forbidden_claims) !== JSON.stringify(originalStrategy?.forbidden_claims))
        patch.forbidden_claims = strategy.forbidden_claims
      if (JSON.stringify(strategy.proof_standards) !== JSON.stringify(originalStrategy?.proof_standards))
        patch.proof_standards = strategy.proof_standards
      if (JSON.stringify(strategy.offer_cta_rules) !== JSON.stringify(originalStrategy?.offer_cta_rules))
        patch.offer_cta_rules = strategy.offer_cta_rules
      if (JSON.stringify(strategy.forbidden_topics) !== JSON.stringify(originalStrategy?.forbidden_topics))
        patch.forbidden_topics = strategy.forbidden_topics
      if (JSON.stringify(strategy.audience_segments) !== JSON.stringify(originalStrategy?.audience_segments))
        patch.audience_segments = strategy.audience_segments
      if (JSON.stringify(strategy.platform_rules) !== JSON.stringify(originalStrategy?.platform_rules))
        patch.platform_rules = strategy.platform_rules
      if (JSON.stringify(strategy.cta_strategy) !== JSON.stringify(originalStrategy?.cta_strategy))
        patch.cta_strategy = strategy.cta_strategy
      if (JSON.stringify(strategy.past_winners) !== JSON.stringify(originalStrategy?.past_winners))
        patch.past_winners = strategy.past_winners
      if (JSON.stringify(strategy.past_losers) !== JSON.stringify(originalStrategy?.past_losers))
        patch.past_losers = strategy.past_losers

      if (Object.keys(patch).length === 0) {
        setSaved(true)
        setTimeout(() => setSaved(false), 2000)
        return
      }

      const updated = await updateStrategy(patch)
      setStrategy(updated)
      setOriginalStrategy(updated)
      setHasChanges(false)
      setSaved(true)
      setTimeout(() => setSaved(false), 2000)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save strategy')
    } finally {
      setSaving(false)
    }
  }

  const update = <K extends keyof StrategyMemory>(key: K, value: StrategyMemory[K]) => {
    setStrategy((prev) => (prev ? { ...prev, [key]: value } : prev))
    setHasChanges(true)
  }

  if (loading) return <div className="text-sm text-muted-foreground">Loading strategy…</div>
  if (!strategy) return <div className="text-sm text-muted-foreground">No strategy found.</div>

  const completedCount = 0

  const tabs: { value: StrategyTab; label: string; badge?: string | number }[] = [
    { value: 'health', label: 'Health' },
    { value: 'niche', label: 'Niche' },
    { value: 'pillars', label: 'Pillars', badge: strategy.content_pillars.length },
    { value: 'audience', label: 'Audience', badge: strategy.audience_segments.length },
    { value: 'platforms', label: 'Platforms' },
    { value: 'claims', label: 'Claims' },
    { value: 'examples', label: 'Examples' },
    { value: 'advanced', label: 'Advanced' },
  ]

  return (
    <div className="space-y-5">
      <Tabs value={activeTab} onValueChange={(v) => setActiveTab(v as StrategyTab)} tabs={tabs} variant="prominent" className="w-full" />

      {/* Health tab */}
      {activeTab === 'health' && (
        <div className="space-y-4">
          <HealthPanel strategy={strategy} />
          {hasChanges && (
            <Alert variant="default" className="border-warning/40 bg-warning-muted/40">
              <AlertTitle>Unsaved changes</AlertTitle>
              <AlertDescription>You have unsaved changes. Save before leaving this page.</AlertDescription>
            </Alert>
          )}
          <ReadinessPanel />
          <RulesForReviewPanel />
          <OperatingFitnessPanel />
        </div>
      )}

      {/* Niche tab */}
      {activeTab === 'niche' && (
        <div className="space-y-4">
          <div className="space-y-1.5">
            <label className="text-[10px] font-mono uppercase tracking-[0.22em] text-muted-foreground">
              Niche
            </label>
            <Textarea
              value={strategy.niche}
              onChange={(e) => update('niche', e.target.value)}
              placeholder="e.g. Personal finance for millennials"
              rows={3}
            />
            <p className="text-xs text-muted-foreground">
              The core niche or market this content studio should optimize for.
            </p>
          </div>
          <div className="space-y-1.5">
            <label className="text-[10px] font-mono uppercase tracking-[0.22em] text-muted-foreground">
              Tone rules
            </label>
            <TagInput
              value={strategy.tone_rules}
              onChange={(tags) => update('tone_rules', tags)}
              placeholder="Add tone rule, press Enter"
            />
            <p className="text-xs text-muted-foreground">
              Guidelines for voice, style, and register across all content.
            </p>
          </div>
        </div>
      )}

      {/* Pillars tab */}
      {activeTab === 'pillars' && (
        <ContentPillarEditor
          pillars={strategy.content_pillars}
          onChange={(pillars) => update('content_pillars', pillars)}
        />
      )}

      {/* Audience tab */}
      {activeTab === 'audience' && (
        <div className="space-y-5">
          <AudienceSegmentEditor
            segments={strategy.audience_segments}
            onChange={(segments) => update('audience_segments', segments)}
          />
          <div className="space-y-1.5">
            <label className="text-[10px] font-mono uppercase tracking-[0.22em] text-muted-foreground">
              Allowed audience universe
            </label>
            <TagInput
              value={strategy.allowed_audience_universe}
              onChange={(tags) => update('allowed_audience_universe', tags)}
              placeholder="Add allowed audience, press Enter"
            />
          </div>
          <div className="space-y-1.5">
            <label className="text-[10px] font-mono uppercase tracking-[0.22em] text-muted-foreground">
              Positioning statement
            </label>
            <Textarea
              value={strategy.positioning}
              onChange={(e) => update('positioning', e.target.value)}
              placeholder="How is this brand or message positioned in the market?"
              rows={3}
            />
          </div>
          <div className="space-y-1.5">
            <label className="text-[10px] font-mono uppercase tracking-[0.22em] text-muted-foreground">
              Business objective
            </label>
            <Textarea
              value={strategy.business_objective}
              onChange={(e) => update('business_objective', e.target.value)}
              placeholder="What is the primary business goal this content supports?"
              rows={2}
            />
          </div>
        </div>
      )}

      {/* Platforms tab */}
      {activeTab === 'platforms' && (
        <div className="space-y-5">
          <div className="space-y-3">
            <label className="text-[10px] font-mono uppercase tracking-[0.22em] text-muted-foreground">
              Platforms
            </label>
            <TagInput
              value={strategy.platforms}
              onChange={(tags) => update('platforms', tags)}
              placeholder="Add platform, press Enter"
            />
          </div>
          <div className="space-y-3">
            <label className="text-[10px] font-mono uppercase tracking-[0.22em] text-muted-foreground">
              Platform rules
            </label>
            <PlatformRuleEditor
              rules={strategy.platform_rules}
              onChange={(rules) => update('platform_rules', rules)}
            />
          </div>
        </div>
      )}

      {/* Claims tab */}
      {activeTab === 'claims' && (
        <div className="space-y-5">
          <div className="space-y-3">
            <label className="text-[10px] font-mono uppercase tracking-[0.22em] text-muted-foreground">
              Proof standards
            </label>
            <p className="text-xs text-muted-foreground -mt-1">
              Claims must meet these standards before they can be used in content.
            </p>
            <TagInput
              value={strategy.proof_standards}
              onChange={(tags) => update('proof_standards', tags)}
              placeholder="Add proof standard, press Enter"
            />
          </div>
          <div className="space-y-3">
            <label className="text-[10px] font-mono uppercase tracking-[0.22em] text-muted-foreground">
              Forbidden claims
            </label>
            <p className="text-xs text-muted-foreground -mt-1">
              Claims that cannot be made under any circumstances.
            </p>
            <TagInput
              value={strategy.forbidden_claims}
              onChange={(tags) => update('forbidden_claims', tags)}
              placeholder="Add forbidden claim, press Enter"
            />
          </div>
          <div className="space-y-3">
            <label className="text-[10px] font-mono uppercase tracking-[0.22em] text-muted-foreground">
              Forbidden topics
            </label>
            <TagInput
              value={strategy.forbidden_topics}
              onChange={(tags) => update('forbidden_topics', tags)}
              placeholder="Add forbidden topic, press Enter"
            />
          </div>
          <div className="space-y-3">
            <label className="text-[10px] font-mono uppercase tracking-[0.22em] text-muted-foreground">
              CTA rules
            </label>
            <TagInput
              value={strategy.offer_cta_rules}
              onChange={(tags) => update('offer_cta_rules', tags)}
              placeholder="Add CTA rule, press Enter"
            />
          </div>
          <div className="space-y-3">
            <label className="text-[10px] font-mono uppercase tracking-[0.22em] text-muted-foreground">
              CTA strategy
            </label>
            <CTAStrategyEditor
              strategy={strategy.cta_strategy}
              onChange={(cta) => update('cta_strategy', cta)}
            />
          </div>
        </div>
      )}

      {/* Examples tab */}
      {activeTab === 'examples' && (
        <div className="space-y-6">
          <div className="space-y-3">
            <p className="text-[11px] font-mono uppercase tracking-[0.22em] text-muted-foreground">
              Past winners ({strategy.past_winners.length})
            </p>
            <ContentExampleEditor
              examples={strategy.past_winners}
              variant="winner"
              onChange={(examples) => update('past_winners', examples)}
            />
          </div>
          <div className="space-y-3">
            <p className="text-[11px] font-mono uppercase tracking-[0.22em] text-muted-foreground">
              Past losers ({strategy.past_losers.length})
            </p>
            <ContentExampleEditor
              examples={strategy.past_losers}
              variant="loser"
              onChange={(examples) => update('past_losers', examples)}
            />
          </div>
        </div>
      )}

      {/* Advanced tab */}
      {activeTab === 'advanced' && (
        <ImportExportPanel strategy={strategy} onImport={(s) => { setStrategy(s); setHasChanges(true) }} />
      )}

      {/* Error */}
      {error && (
        <Alert variant="destructive">
          <AlertTitle>Strategy save failed</AlertTitle>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {/* Save bar */}
      <div className="flex items-center gap-3 border-t border-border/70 pt-4">
        <Button
          type="button"
          onClick={handleSave}
          disabled={saving || (!hasChanges && activeTab !== 'advanced')}
          className="gap-1.5 bg-warning text-background hover:bg-warning/90"
        >
          {saved ? (
            <>
              <Check className="h-4 w-4" />
              Saved
            </>
          ) : (
            <>
              <Save className="h-4 w-4" />
              {saving ? 'Saving…' : 'Save Strategy'}
            </>
          )}
        </Button>
        {hasChanges && (
          <Button type="button" variant="ghost" size="sm" onClick={() => setDiscardOpen(true)}>
            Discard changes
          </Button>
        )}
      </div>

      {/* Discard dialog */}
      <Dialog open={discardOpen} onOpenChange={setDiscardOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Discard changes?</DialogTitle>
            <DialogDescription>
              You have unsaved changes. Loading a new strategy or refreshing the page will discard them.
            </DialogDescription>
          </DialogHeader>
          <DialogBody>
            <div className="flex gap-2">
              <Button type="button" variant="destructive" onClick={() => { setDiscardOpen(false); setHasChanges(false) }}>
                Discard changes
              </Button>
              <Button type="button" variant="ghost" onClick={() => setDiscardOpen(false)}>
                Keep editing
              </Button>
            </div>
          </DialogBody>
        </DialogContent>
      </Dialog>
    </div>
  )
}