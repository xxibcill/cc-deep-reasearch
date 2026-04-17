'use client'

import { useState } from 'react'
import { Archive, Check, Edit2, Plus, X } from 'lucide-react'
import type { ContentExample } from '@/types/content-gen'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'

interface ContentExampleCardProps {
  example: ContentExample
  variant: 'winner' | 'loser'
  onUpdate: (updated: ContentExample) => void
  onRemove: () => void
}

function ContentExampleCard({ example, variant, onUpdate, onRemove }: ContentExampleCardProps) {
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState(example)

  const save = () => {
    onUpdate(draft)
    setEditing(false)
  }

  if (editing) {
    return (
      <div className="space-y-3 rounded-xl border border-primary/40 bg-surface/80 p-4">
        <div className="space-y-1.5">
          <label className="text-[10px] font-mono uppercase tracking-[0.22em] text-muted-foreground">
            Title
          </label>
          <Input
            value={draft.title}
            onChange={(e) => setDraft({ ...draft, title: e.target.value })}
            placeholder="What was this content about?"
          />
        </div>
        <div className="space-y-1.5">
          <label className="text-[10px] font-mono uppercase tracking-[0.22em] text-muted-foreground">
            Why it {variant === 'winner' ? 'worked' : 'failed'}
          </label>
          <Textarea
            value={draft.why_it_worked_or_failed}
            onChange={(e) => setDraft({ ...draft, why_it_worked_or_failed: e.target.value })}
            placeholder="What made this a {variant}?"
            rows={2}
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
          <p className="text-sm font-medium text-foreground">{example.title}</p>
          {example.why_it_worked_or_failed && (
            <p className="mt-1 text-xs text-foreground/72 leading-relaxed">{example.why_it_worked_or_failed}</p>
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

interface ContentExampleEditorProps {
  examples: ContentExample[]
  variant: 'winner' | 'loser'
  onChange: (examples: ContentExample[]) => void
}

export function ContentExampleEditor({ examples, variant, onChange }: ContentExampleEditorProps) {
  const [showAdd, setShowAdd] = useState(false)
  const [newExample, setNewExample] = useState<ContentExample>({
    title: '',
    why_it_worked_or_failed: '',
    metrics_snapshot: {},
  })

  const addExample = () => {
    if (!newExample.title.trim()) return
    onChange([...examples, { ...newExample }])
    setNewExample({ title: '', why_it_worked_or_failed: '', metrics_snapshot: {} })
    setShowAdd(false)
  }

  return (
    <div className="space-y-3">
      {examples.length > 0 ? (
        <div className="space-y-2">
          {examples.map((example, i) => (
            <ContentExampleCard
              key={i}
              example={example}
              variant={variant}
              onUpdate={(updated) => onChange(examples.map((e, j) => (j === i ? updated : e)))}
              onRemove={() => onChange(examples.filter((_, j) => j !== i))}
            />
          ))}
        </div>
      ) : (
        <p className="text-sm text-muted-foreground">
          No past {variant}s recorded.
        </p>
      )}

      {showAdd ? (
        <div className="space-y-3 rounded-xl border border-primary/40 bg-surface/80 p-4">
          <div className="space-y-1.5">
            <label className="text-[10px] font-mono uppercase tracking-[0.22em] text-muted-foreground">
              Title
            </label>
            <Input
              value={newExample.title}
              onChange={(e) => setNewExample({ ...newExample, title: e.target.value })}
              placeholder="What was this content about?"
              autoFocus
            />
          </div>
          <div className="space-y-1.5">
            <label className="text-[10px] font-mono uppercase tracking-[0.22em] text-muted-foreground">
              Why it {variant === 'winner' ? 'worked' : 'failed'}
            </label>
            <Textarea
              value={newExample.why_it_worked_or_failed}
              onChange={(e) => setNewExample({ ...newExample, why_it_worked_or_failed: e.target.value })}
              placeholder={`What made this a ${variant}?`}
              rows={2}
            />
          </div>
          <div className="flex gap-2">
            <Button type="button" size="sm" onClick={addExample} className="gap-1.5">
              <Check className="h-3.5 w-3.5" />
              Add {variant === 'winner' ? 'Winner' : 'Loser'}
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
          Add Past {variant === 'winner' ? 'Winner' : 'Loser'}
        </Button>
      )}
    </div>
  )
}
