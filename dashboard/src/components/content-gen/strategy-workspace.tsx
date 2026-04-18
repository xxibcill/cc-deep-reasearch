'use client'

import { useEffect, useState } from 'react'
import {
  AlertCircle,
  AlertTriangle,
  Archive,
  Check,
  ChevronDown,
  ChevronRight,
  Copy,
  Download,
  Eye,
  EyeOff,
  FileText,
  Loader2,
  Plus,
  Save,
  Upload,
  X,
} from 'lucide-react'
import type {
  AudienceSegment,
  ContentExample,
  ContentPillar,
  OperatingFitnessMetrics,
  PlatformRule,
  RuleVersion,
  StrategyMemory,
  StrategyReadinessResult,
} from '@/types/content-gen'
import {
  getOperatingFitness,
  getRulesForReview,
  getStrategy,
  getStrategyReadiness,
  updateRuleLifecycle,
  updateStrategy,
} from '@/lib/content-gen-api'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { Tabs } from '@/components/ui/tabs'
import { TagInput } from '@/components/ui/tag-input'
import { Badge } from '@/components/ui/badge'
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

// ---------------------------------------------------------------------------
// Strategy completeness / health
// ---------------------------------------------------------------------------

interface SectionHealth {
  label: string
  status: 'complete' | 'warning' | 'missing'
  detail: string
}

function computeHealth(s: StrategyMemory | null): SectionHealth[] {
  if (!s) return []
  const h: SectionHealth[] = []

  h.push({
    label: 'Niche',
    status: s.niche?.trim() ? 'complete' : 'missing',
    detail: s.niche?.trim() ? s.niche : 'No niche set',
  })

  h.push({
    label: 'Content pillars',
    status: s.content_pillars.length > 0 ? 'complete' : 'missing',
    detail: `${s.content_pillars.length} pillar${s.content_pillars.length !== 1 ? 's' : ''} configured`,
  })

  h.push({
    label: 'Audience segments',
    status: s.audience_segments.length > 0 ? 'complete' : 'warning',
    detail:
      s.audience_segments.length > 0
        ? `${s.audience_segments.length} segment${s.audience_segments.length !== 1 ? 's' : ''}`
        : 'No audience segments – recommended for targeting',
  })

  h.push({
    label: 'Platforms',
    status: s.platforms.length > 0 || s.platform_rules.length > 0 ? 'complete' : 'warning',
    detail:
      s.platforms.length > 0
        ? s.platforms.join(', ')
        : s.platform_rules.length > 0
          ? `${s.platform_rules.length} platform rule${s.platform_rules.length !== 1 ? 's' : ''}`
          : 'No platforms set',
  })

  h.push({
    label: 'Tone rules',
    status: s.tone_rules.length > 0 ? 'complete' : 'warning',
    detail: s.tone_rules.length > 0 ? s.tone_rules.join(' | ') : 'No tone rules',
  })

  h.push({
    label: 'Proof & claims',
    status:
      s.proof_standards.length > 0 && s.forbidden_claims.length > 0
        ? 'complete'
        : s.proof_standards.length > 0 || s.forbidden_claims.length > 0
          ? 'warning'
          : 'missing',
    detail:
      s.proof_standards.length > 0 && s.forbidden_claims.length > 0
        ? 'Standards and forbidden claims set'
        : s.proof_standards.length > 0
          ? 'Only proof standards set'
          : s.forbidden_claims.length > 0
            ? 'Only forbidden claims set'
            : 'No proof standards or forbidden claims',
  })

  h.push({
    label: 'Past examples',
    status: s.past_winners.length > 0 || s.past_losers.length > 0 ? 'complete' : 'warning',
    detail:
      s.past_winners.length > 0 && s.past_losers.length > 0
        ? `${s.past_winners.length} winner${s.past_winners.length !== 1 ? 's' : ''}, ${s.past_losers.length} loser${s.past_losers.length !== 1 ? 's' : ''}`
        : s.past_winners.length > 0
          ? `${s.past_winners.length} past winner${s.past_winners.length !== 1 ? 's' : ''}`
          : s.past_losers.length > 0
            ? `${s.past_losers.length} past loser${s.past_losers.length !== 1 ? 's' : ''}`
            : 'No past examples',
  })

  return h
}

function HealthIcon({ status }: { status: SectionHealth['status'] }) {
  if (status === 'complete') return <Check className="h-3.5 w-3.5 text-success" />
  if (status === 'warning') return <AlertTriangle className="h-3.5 w-3.5 text-warning" />
  return <AlertCircle className="h-3.5 w-3.5 text-error" />
}

// ---------------------------------------------------------------------------
// Import / Export panel
// ---------------------------------------------------------------------------

function ImportExportPanel({
  strategy,
  onImport,
}: {
  strategy: StrategyMemory
  onImport: (s: StrategyMemory) => void
}) {
  const [importText, setImportText] = useState('')
  const [jsonValid, setJsonValid] = useState<boolean | null>(null)
  const [importError, setImportError] = useState<string | null>(null)
  const [confirmOpen, setConfirmOpen] = useState(false)
  const [copied, setCopied] = useState(false)

  const handleExport = () => {
    const nicheSlug = strategy.niche
      ? strategy.niche.toLowerCase().replace(/[^a-z0-9]+/g, '-').slice(0, 40)
      : 'strategy'
    const blob = new Blob([JSON.stringify(strategy, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${nicheSlug}-${new Date().toISOString().slice(0, 10)}.json`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
  }

  const handleCopy = async () => {
    await navigator.clipboard.writeText(JSON.stringify(strategy, null, 2))
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  const handleImportConfirm = () => {
    try {
      const parsed = JSON.parse(importText) as StrategyMemory
      const hasNiche = typeof parsed.niche === 'string' && parsed.niche.trim().length > 0
      const hasPillars = Array.isArray(parsed.content_pillars) && parsed.content_pillars.length > 0
      if (!hasNiche && !hasPillars) {
        throw new Error('Invalid: must have niche (non-empty string) or content_pillars (non-empty array)')
      }
      onImport(parsed)
      setImportText('')
      setJsonValid(null)
      setConfirmOpen(false)
      setImportError(null)
    } catch (err) {
      setImportError(err instanceof Error ? err.message : 'Import failed')
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-2">
        <Button type="button" variant="outline" onClick={handleExport} className="gap-1.5">
          <Download className="h-4 w-4" />
          Export JSON
        </Button>
        <Button type="button" variant="outline" onClick={handleCopy} className="gap-1.5">
          {copied ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
          {copied ? 'Copied' : 'Copy'}
        </Button>
      </div>

      <div className="space-y-2">
        <p className="text-[10px] font-mono uppercase tracking-[0.22em] text-muted-foreground">
          Paste strategy JSON to import
        </p>
        <Textarea
          value={importText}
          onChange={(e) => {
            const val = e.target.value
            setImportText(val)
            setImportError(null)
            if (!val.trim()) {
              setJsonValid(null)
            } else {
              try {
                JSON.parse(val)
                const parsed = JSON.parse(val) as StrategyMemory
                const hasNiche = typeof parsed.niche === 'string' && parsed.niche.trim().length > 0
                const hasPillars = Array.isArray(parsed.content_pillars) && parsed.content_pillars.length > 0
                setJsonValid(hasNiche || hasPillars)
              } catch {
                setJsonValid(false)
              }
            }
          }}
          placeholder='{"niche": "...", "content_pillars": [...]}'
          rows={8}
          className={`font-mono text-xs ${jsonValid === false ? 'border-error' : jsonValid === true ? 'border-success' : ''}`}
        />
        {importError && (
          <Alert variant="destructive">
            <AlertTitle>Import failed</AlertTitle>
            <AlertDescription>{importError}</AlertDescription>
          </Alert>
        )}
        <Button
          type="button"
          variant="outline"
          onClick={() => setConfirmOpen(true)}
          disabled={jsonValid !== true}
          className="gap-1.5"
        >
          <Upload className="h-4 w-4" />
          Import
        </Button>
      </div>

      <Dialog open={confirmOpen} onOpenChange={setConfirmOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Confirm import</DialogTitle>
            <DialogDescription>
              This will replace your current strategy. All fields will be overwritten with the imported data.
              This cannot be undone.
            </DialogDescription>
          </DialogHeader>
          <DialogBody>
            <div className="flex gap-2">
              <Button type="button" onClick={handleImportConfirm} className="gap-1.5 bg-warning text-background hover:bg-warning/90">
                <Upload className="h-4 w-4" />
                Yes, import
              </Button>
              <Button type="button" variant="ghost" onClick={() => setConfirmOpen(false)}>
                Cancel
              </Button>
            </div>
          </DialogBody>
        </DialogContent>
      </Dialog>
    </div>
  )
}

// ---------------------------------------------------------------------------
// P4-T1: Strategy Readiness Panel
// ---------------------------------------------------------------------------

function ReadinessIcon({ severity }: { severity: string }) {
  if (severity === 'blocking') return <AlertCircle className="h-4 w-4 text-error" />
  if (severity === 'warning') return <AlertTriangle className="h-4 w-4 text-warning" />
  return <Check className="h-4 w-4 text-success" />
}

function ReadinessPanel() {
  const [readiness, setReadiness] = useState<StrategyReadinessResult | null>(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    void loadReadiness()
  }, [])

  const loadReadiness = async () => {
    try {
      setLoading(true)
      const data = await getStrategyReadiness()
      setReadiness(data)
    } catch {
      // readiness is optional, don't block on errors
    } finally {
      setLoading(false)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center gap-2 text-xs text-muted-foreground">
        <Loader2 className="h-3.5 w-3.5 animate-spin" />
        Checking strategy readiness…
      </div>
    )
  }

  if (!readiness) return null

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm font-medium">
            Strategy Readiness:{' '}
            <span
              className={
                readiness.readiness === 'healthy'
                  ? 'text-success'
                  : readiness.readiness === 'incomplete'
                    ? 'text-warning'
                    : 'text-error'
              }
            >
              {readiness.readiness}
            </span>
          </p>
          <p className="text-xs text-muted-foreground">{readiness.summary}</p>
        </div>
        <div className="text-right">
          <p className="text-2xl font-bold">{Math.round(readiness.overall_score * 100)}%</p>
          <p className="text-xs text-muted-foreground">completeness</p>
        </div>
      </div>

      {readiness.issues.length > 0 && (
        <div className="space-y-2">
          {readiness.issues.map((issue) => (
            <div
              key={issue.code}
              className="flex items-start gap-2.5 rounded-lg border border-border/70 bg-background/55 px-3 py-2.5"
            >
              <ReadinessIcon severity={issue.severity} />
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <p className="text-xs font-medium">{issue.label}</p>
                  <Badge variant="outline" className="text-[10px] uppercase tracking-wider">
                    {issue.severity}
                  </Badge>
                </div>
                <p className="text-xs text-muted-foreground mt-0.5">{issue.detail}</p>
                {issue.suggestion && (
                  <p className="text-xs text-muted-foreground mt-1 italic">Tip: {issue.suggestion}</p>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// P4-T2: Rules For Review Panel
// ---------------------------------------------------------------------------

function RuleStatusBadge({ status }: { status: string }) {
  const variants: Record<string, string> = {
    promoted: 'bg-success/10 text-success border-success/30',
    under_review: 'bg-warning/10 text-warning border-warning/30',
    deprecated: 'bg-error/10 text-error border-error/30',
    expired: 'bg-error/10 text-error border-error/30',
  }
  return (
    <Badge className={`text-[10px] uppercase tracking-wider ${variants[status] ?? ''}`}>
      {status}
    </Badge>
  )
}

function RulesForReviewPanel() {
  const [rules, setRules] = useState<RuleVersion[]>([])
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    void loadRules()
  }, [])

  const loadRules = async () => {
    try {
      setLoading(true)
      const data = await getRulesForReview()
      setRules(data)
    } catch {
      // governance is optional, don't block on errors
    } finally {
      setLoading(false)
    }
  }

  const handleDeprecate = async (versionId: string) => {
    try {
      await updateRuleLifecycle(versionId, { status: 'deprecated' })
      await loadRules()
    } catch {
      // best effort
    }
  }

  const handlePromote = async (versionId: string) => {
    try {
      await updateRuleLifecycle(versionId, { status: 'promoted' })
      await loadRules()
    } catch {
      // best effort
    }
  }

  if (loading) {
    return (
      <div className="flex items-center gap-2 text-xs text-muted-foreground">
        <Loader2 className="h-3.5 w-3.5 animate-spin" />
        Loading rules for review…
      </div>
    )
  }

  if (rules.length === 0) return null

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2">
        <AlertTriangle className="h-4 w-4 text-warning" />
        <p className="text-sm font-medium">{rules.length} rule(s) need review</p>
      </div>
      <div className="space-y-2">
        {rules.map((rule) => (
          <div
            key={rule.version_id}
            className="flex items-start justify-between gap-3 rounded-lg border border-border/70 bg-background/55 px-3 py-2.5"
          >
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-2">
                <p className="text-xs font-medium truncate">{rule.change_summary || rule.new_value || rule.kind}</p>
                <RuleStatusBadge status={rule.lifecycle_status} />
              </div>
              <p className="text-xs text-muted-foreground mt-0.5">
                {rule.kind} · confidence {Math.round(rule.confidence * 100)}% · {rule.evidence_count} evidence
              </p>
              {rule.review_notes && (
                <p className="text-xs text-muted-foreground mt-1 italic">Review: {rule.review_notes}</p>
              )}
            </div>
            <div className="flex gap-1.5 shrink-0">
              {rule.lifecycle_status !== 'promoted' && (
                <Button
                  size="sm"
                  variant="ghost"
                  className="h-7 text-xs"
                  onClick={() => handlePromote(rule.version_id)}
                >
                  <Check className="h-3 w-3" />
                  Promote
                </Button>
              )}
              <Button
                size="sm"
                variant="ghost"
                className="h-7 text-xs text-error hover:text-error"
                onClick={() => handleDeprecate(rule.version_id)}
              >
                <X className="h-3 w-3" />
                Deprecate
              </Button>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// P4-T3: Operating Fitness Panel
// ---------------------------------------------------------------------------

function FitnessMetricRow({ label, value, unit }: { label: string; value: string | number; unit?: string }) {
  return (
    <div className="flex items-center justify-between py-1">
      <span className="text-xs text-muted-foreground">{label}</span>
      <span className="text-xs font-medium">
        {value}
        {unit && <span className="text-muted-foreground ml-0.5">{unit}</span>}
      </span>
    </div>
  )
}

function OperatingFitnessPanel() {
  const [fitness, setFitness] = useState<{ metrics: OperatingFitnessMetrics; summary: string } | null>(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    void loadFitness()
  }, [])

  const loadFitness = async () => {
    try {
      setLoading(true)
      const data = await getOperatingFitness()
      setFitness(data)
    } catch {
      // fitness is optional
    } finally {
      setLoading(false)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center gap-2 text-xs text-muted-foreground">
        <Loader2 className="h-3.5 w-3.5 animate-spin" />
        Loading operating fitness…
      </div>
    )
  }

  if (!fitness) return null

  const m = fitness.metrics

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2">
        <AlertTriangle className="h-4 w-4 text-muted-foreground" />
        <p className="text-sm font-medium">Operating Fitness</p>
      </div>

      <div className="rounded-lg border border-border/70 bg-background/55 px-3 py-2 space-y-0">
        <FitnessMetricRow label="Kill rate" value={`${Math.round((m.kill_rate ?? 0) * 100)}%`} />
        <FitnessMetricRow label="Publish rate" value={`${Math.round((m.publish_rate ?? 0) * 100)}%`} />
        <FitnessMetricRow label="Avg cycle" value={Math.round(m.avg_cycle_time_ms / 1000)} unit="s" />
        <FitnessMetricRow label="P95 cycle" value={Math.round(m.p95_cycle_time_ms / 1000)} unit="s" />
        <FitnessMetricRow label="Published/wk" value={m.published_per_week?.toFixed(1) ?? '0'} />
      </div>

      {m.drift_summary && (
        <div className="rounded-lg border border-border/70 bg-background/55 px-3 py-2">
          <p className="text-xs font-medium mb-1">Strategy Drift</p>
          <p className="text-xs text-muted-foreground">{m.drift_summary}</p>
          {m.learning_bias_score > 0.1 && (
            <p className="text-xs text-warning mt-1">Hook overrepresentation: {Math.round(m.learning_bias_score * 100)}%</p>
          )}
          {m.rules_needing_review_count > 0 && (
            <p className="text-xs text-warning mt-0.5">{m.rules_needing_review_count} rules need review</p>
          )}
        </div>
      )}
    </div>
  )
}

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
  const [advancedOpen, setAdvancedOpen] = useState(false)

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

  const health = computeHealth(strategy)
  const completedCount = health.filter((h) => h.status === 'complete').length

  const tabs: { value: StrategyTab; label: string; badge?: string | number }[] = [
    { value: 'health', label: 'Health', badge: `${completedCount}/${health.length}` },
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
          <div className="grid gap-3 sm:grid-cols-2">
            {health.map((h) => (
              <div key={h.label} className="flex items-start gap-3 rounded-xl border border-border/70 bg-background/55 px-4 py-3">
                <HealthIcon status={h.status} />
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-medium text-foreground">{h.label}</p>
                  <p className="text-xs text-muted-foreground truncate">{h.detail}</p>
                </div>
              </div>
            ))}
          </div>
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
