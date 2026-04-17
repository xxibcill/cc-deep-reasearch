'use client'

import { useState } from 'react'
import { Archive, Check, Edit2, Plus, X } from 'lucide-react'
import type { PlatformRule } from '@/types/content-gen'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { TagInput } from '@/components/ui/tag-input'

interface PlatformRuleCardProps {
  rule: PlatformRule
  onUpdate: (updated: PlatformRule) => void
  onRemove: () => void
}

function PlatformRuleCard({ rule, onUpdate, onRemove }: PlatformRuleCardProps) {
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState(rule)

  const save = () => {
    onUpdate(draft)
    setEditing(false)
  }

  if (editing) {
    return (
      <div className="space-y-3 rounded-xl border border-primary/40 bg-surface/80 p-4">
        <div className="space-y-1.5">
          <label className="text-[10px] font-mono uppercase tracking-[0.22em] text-muted-foreground">
            Platform
          </label>
          <Input
            value={draft.platform}
            onChange={(e) => setDraft({ ...draft, platform: e.target.value })}
            placeholder="e.g. TikTok, Instagram, YouTube"
          />
        </div>
        <div className="space-y-1.5">
          <label className="text-[10px] font-mono uppercase tracking-[0.22em] text-muted-foreground">
            Format preferences
          </label>
          <TagInput
            value={draft.format_preferences}
            onChange={(tags) => setDraft({ ...draft, format_preferences: tags })}
            placeholder="e.g. Vertical video, Stories"
          />
        </div>
        <div className="space-y-1.5">
          <label className="text-[10px] font-mono uppercase tracking-[0.22em] text-muted-foreground">
            Length constraints
          </label>
          <Input
            value={draft.length_constraints}
            onChange={(e) => setDraft({ ...draft, length_constraints: e.target.value })}
            placeholder="e.g. 30-60s, max 3 min"
          />
        </div>
        <div className="space-y-1.5">
          <label className="text-[10px] font-mono uppercase tracking-[0.22em] text-muted-foreground">
            Style constraints
          </label>
          <TagInput
            value={draft.style_constraints}
            onChange={(tags) => setDraft({ ...draft, style_constraints: tags })}
            placeholder="e.g. Fast-paced, Educational"
          />
        </div>
        <div className="space-y-1.5">
          <label className="text-[10px] font-mono uppercase tracking-[0.22em] text-muted-foreground">
            CTA norms
          </label>
          <TagInput
            value={draft.cta_norms}
            onChange={(tags) => setDraft({ ...draft, cta_norms: tags })}
            placeholder="e.g. Link in bio, Swipe up"
          />
        </div>
        <div className="flex gap-2">
          <Button type="button" size="sm" onClick={save} className="gap-1.5">
            <Check className="h-3.5 w-3.5" />
            Save
          </Button>
          <Button type="button" variant="ghost" size="sm" onClick={() => setEditing(false)}>
            <X className="h-3.5 w-3.5" />
            Cancel
          </Button>
        </div>
      </div>
    )
  }

  return (
    <div className="group rounded-xl border border-border/70 bg-background/55 px-4 py-3">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0 flex-1">
          <p className="text-sm font-medium text-foreground">{rule.platform || 'Unnamed platform'}</p>
          {rule.length_constraints && (
            <p className="mt-1 text-xs text-foreground/72">
              Length: {rule.length_constraints}
            </p>
          )}
          {(rule.format_preferences.length > 0 || rule.style_constraints.length > 0) && (
            <div className="mt-2 flex flex-wrap gap-1">
              {rule.format_preferences.slice(0, 2).map((f) => (
                <span key={f} className="rounded-md border border-border/70 bg-surface/55 px-2 py-0.5 text-[10px] text-foreground/75">
                  {f}
                </span>
              ))}
              {rule.style_constraints.slice(0, 2).map((s) => (
                <span key={s} className="rounded-md border border-border/70 bg-secondary/55 px-2 py-0.5 text-[10px] text-secondary-foreground">
                  {s}
                </span>
              ))}
            </div>
          )}
        </div>
        <div className="flex gap-1 opacity-0 transition-opacity group-hover:opacity-100">
          <Button type="button" variant="ghost" size="icon" onClick={() => setEditing(true)}>
            <Edit2 className="h-3.5 w-3.5" />
          </Button>
          <Button type="button" variant="ghost" size="icon" onClick={onRemove}>
            <Archive className="h-3.5 w-3.5" />
          </Button>
        </div>
      </div>
    </div>
  )
}

interface PlatformRuleEditorProps {
  rules: PlatformRule[]
  onChange: (rules: PlatformRule[]) => void
}

export function PlatformRuleEditor({ rules, onChange }: PlatformRuleEditorProps) {
  const [showAdd, setShowAdd] = useState(false)
  const [newRule, setNewRule] = useState<PlatformRule>({
    platform: '',
    format_preferences: [],
    length_constraints: '',
    style_constraints: [],
    cta_norms: [],
  })

  const addRule = () => {
    if (!newRule.platform.trim()) return
    onChange([...rules, { ...newRule }])
    setNewRule({ platform: '', format_preferences: [], length_constraints: '', style_constraints: [], cta_norms: [] })
    setShowAdd(false)
  }

  return (
    <div className="space-y-3">
      {rules.length > 0 ? (
        <div className="space-y-2">
          {rules.map((rule, i) => (
            <PlatformRuleCard
              key={i}
              rule={rule}
              onUpdate={(updated) => onChange(rules.map((r, j) => (j === i ? updated : r)))}
              onRemove={() => onChange(rules.filter((_, j) => j !== i))}
            />
          ))}
        </div>
      ) : (
        <p className="text-sm text-muted-foreground">No platform rules configured.</p>
      )}

      {showAdd ? (
        <div className="space-y-3 rounded-xl border border-primary/40 bg-surface/80 p-4">
          <div className="space-y-1.5">
            <label className="text-[10px] font-mono uppercase tracking-[0.22em] text-muted-foreground">
              Platform
            </label>
            <Input
              value={newRule.platform}
              onChange={(e) => setNewRule({ ...newRule, platform: e.target.value })}
              placeholder="e.g. TikTok"
              autoFocus
            />
          </div>
          <div className="space-y-1.5">
            <label className="text-[10px] font-mono uppercase tracking-[0.22em] text-muted-foreground">
              Format preferences
            </label>
            <TagInput
              value={newRule.format_preferences}
              onChange={(tags) => setNewRule({ ...newRule, format_preferences: tags })}
              placeholder="e.g. Vertical video"
            />
          </div>
          <div className="space-y-1.5">
            <label className="text-[10px] font-mono uppercase tracking-[0.22em] text-muted-foreground">
              Length constraints
            </label>
            <Input
              value={newRule.length_constraints}
              onChange={(e) => setNewRule({ ...newRule, length_constraints: e.target.value })}
              placeholder="e.g. 30-60s, max 3 min"
            />
          </div>
          <div className="space-y-1.5">
            <label className="text-[10px] font-mono uppercase tracking-[0.22em] text-muted-foreground">
              Style constraints
            </label>
            <TagInput
              value={newRule.style_constraints}
              onChange={(tags) => setNewRule({ ...newRule, style_constraints: tags })}
              placeholder="e.g. Fast-paced"
            />
          </div>
          <div className="space-y-1.5">
            <label className="text-[10px] font-mono uppercase tracking-[0.22em] text-muted-foreground">
              CTA norms
            </label>
            <TagInput
              value={newRule.cta_norms}
              onChange={(tags) => setNewRule({ ...newRule, cta_norms: tags })}
              placeholder="e.g. Link in bio"
            />
          </div>
          <div className="flex gap-2">
            <Button type="button" size="sm" onClick={addRule} className="gap-1.5">
              <Check className="h-3.5 w-3.5" />
              Add Rule
            </Button>
            <Button type="button" variant="ghost" size="sm" onClick={() => setShowAdd(false)}>
              <X className="h-3.5 w-3.5" />
              Cancel
            </Button>
          </div>
        </div>
      ) : (
        <Button type="button" variant="outline" onClick={() => setShowAdd(true)} className="gap-1.5 w-full">
          <Plus className="h-4 w-4" />
          Add Platform Rule
        </Button>
      )}
    </div>
  )
}
