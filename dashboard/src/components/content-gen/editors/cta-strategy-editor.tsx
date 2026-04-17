'use client'

import { useState } from 'react'
import { Check, Edit2, X } from 'lucide-react'
import type { CTAStrategy } from '@/types/content-gen'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { TagInput } from '@/components/ui/tag-input'

interface CTAStrategyEditorProps {
  strategy: CTAStrategy
  onChange: (strategy: CTAStrategy) => void
}

export function CTAStrategyEditor({ strategy, onChange }: CTAStrategyEditorProps) {
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState(strategy)

  const save = () => {
    onChange(draft)
    setEditing(false)
  }

  if (editing) {
    return (
      <div className="space-y-4 rounded-xl border border-primary/40 bg-surface/80 p-4">
        <div className="space-y-1.5">
          <label className="text-[10px] font-mono uppercase tracking-[0.22em] text-muted-foreground">
            Allowed CTA types
          </label>
          <TagInput
            value={draft.allowed_cta_types}
            onChange={(tags) => setDraft({ ...draft, allowed_cta_types: tags })}
            placeholder="e.g. Subscribe, Learn more, Download"
          />
        </div>
        <div className="space-y-3">
          <label className="text-[10px] font-mono uppercase tracking-[0.22em] text-muted-foreground">
            Default by content goal
          </label>
          {Object.entries(draft.default_by_content_goal).map(([goal, cta], i) => (
            <div key={goal} className="flex items-center gap-2">
              <Input
                value={goal}
                onChange={(e) => {
                  const next = { ...draft.default_by_content_goal }
                  delete next[goal]
                  next[e.target.value] = cta
                  setDraft({ ...draft, default_by_content_goal: next })
                }}
                placeholder="Content goal"
                className="flex-1"
              />
              <span className="text-muted-foreground">→</span>
              <Input
                value={cta}
                onChange={(e) => {
                  setDraft({
                    ...draft,
                    default_by_content_goal: { ...draft.default_by_content_goal, [goal]: e.target.value },
                  })
                }}
                placeholder="CTA text"
                className="flex-1"
              />
              <Button
                type="button"
                variant="ghost"
                size="icon"
                onClick={() => {
                  const next = { ...draft.default_by_content_goal }
                  delete next[goal]
                  setDraft({ ...draft, default_by_content_goal: next })
                }}
              >
                <X className="h-3.5 w-3.5" />
              </Button>
            </div>
          ))}
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={() => {
              setDraft({
                ...draft,
                default_by_content_goal: { ...draft.default_by_content_goal, '': '' },
              })
            }}
          >
            + Add goal mapping
          </Button>
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
        <div className="min-w-0 flex-1 space-y-2">
          <div className="space-y-1">
            <p className="text-[10px] font-mono uppercase tracking-[0.22em] text-muted-foreground">
              Allowed CTA types
            </p>
            <div className="flex flex-wrap gap-1">
              {strategy.allowed_cta_types.length > 0 ? (
                strategy.allowed_cta_types.map((cta) => (
                  <span
                    key={cta}
                    className="rounded-md border border-border/70 bg-surface/55 px-2 py-0.5 text-[10px] text-foreground/75"
                  >
                    {cta}
                  </span>
                ))
              ) : (
                <span className="text-xs text-muted-foreground">None configured</span>
              )}
            </div>
          </div>
          <div className="space-y-1">
            <p className="text-[10px] font-mono uppercase tracking-[0.22em] text-muted-foreground">
              Defaults by goal
            </p>
            {Object.keys(strategy.default_by_content_goal).length > 0 ? (
              <div className="space-y-1">
                {Object.entries(strategy.default_by_content_goal).map(([goal, cta]) => (
                  <div key={goal} className="flex items-center gap-1.5 text-xs text-foreground/75">
                    <span className="font-medium text-foreground">{goal}:</span>
                    <span>{cta}</span>
                  </div>
                ))}
              </div>
            ) : (
              <span className="text-xs text-muted-foreground">No mappings set</span>
            )}
          </div>
        </div>
        <Button type="button" variant="ghost" size="icon" onClick={() => setEditing(true)}>
          <Edit2 className="h-3.5 w-3.5" />
        </Button>
      </div>
    </div>
  )
}
