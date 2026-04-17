'use client'

import { useState } from 'react'
import { Archive, Check, Edit2, Plus, X } from 'lucide-react'
import type { AudienceSegment } from '@/types/content-gen'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { TagInput } from '@/components/ui/tag-input'

interface AudienceSegmentCardProps {
  segment: AudienceSegment
  onUpdate: (updated: AudienceSegment) => void
  onArchive: () => void
}

function AudienceSegmentCard({ segment, onUpdate, onArchive }: AudienceSegmentCardProps) {
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState(segment)

  const save = () => {
    onUpdate(draft)
    setEditing(false)
  }

  if (editing) {
    return (
      <div className="space-y-3 rounded-xl border border-primary/40 bg-surface/80 p-4">
        <div className="space-y-1.5">
          <label className="text-[10px] font-mono uppercase tracking-[0.22em] text-muted-foreground">
            Segment name
          </label>
          <Input
            value={draft.name}
            onChange={(e) => setDraft({ ...draft, name: e.target.value })}
            placeholder="e.g. Early-career professionals"
          />
        </div>
        <div className="space-y-1.5">
          <label className="text-[10px] font-mono uppercase tracking-[0.22em] text-muted-foreground">
            Description
          </label>
          <Textarea
            value={draft.description}
            onChange={(e) => setDraft({ ...draft, description: e.target.value })}
            placeholder="Who is this segment and what are they dealing with?"
            rows={2}
          />
        </div>
        <div className="space-y-1.5">
          <label className="text-[10px] font-mono uppercase tracking-[0.22em] text-muted-foreground">
            Pain points
          </label>
          <TagInput
            value={draft.pain_points}
            onChange={(tags) => setDraft({ ...draft, pain_points: tags })}
            placeholder="Add pain point, press Enter"
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
          <p className="text-sm font-medium text-foreground">{segment.name}</p>
          {segment.description && (
            <p className="mt-1 text-xs text-foreground/72 leading-relaxed">{segment.description}</p>
          )}
          {segment.pain_points.length > 0 && (
            <div className="mt-2 flex flex-wrap gap-1">
              {segment.pain_points.slice(0, 3).map((point, i) => (
                <span
                  key={i}
                  className="rounded-md border border-border/70 bg-surface/55 px-2 py-0.5 text-[10px] text-foreground/75"
                >
                  {point}
                </span>
              ))}
              {segment.pain_points.length > 3 && (
                <span className="rounded-md bg-secondary/70 px-2 py-0.5 text-[10px] text-secondary-foreground">
                  +{segment.pain_points.length - 3}
                </span>
              )}
            </div>
          )}
        </div>
        <div className="flex gap-1 opacity-0 transition-opacity group-hover:opacity-100">
          <Button type="button" variant="ghost" size="icon" onClick={() => setEditing(true)}>
            <Edit2 className="h-3.5 w-3.5" />
          </Button>
          <Button type="button" variant="ghost" size="icon" onClick={onArchive} title="Remove segment">
            <Archive className="h-3.5 w-3.5" />
          </Button>
        </div>
      </div>
    </div>
  )
}

interface AudienceSegmentEditorProps {
  segments: AudienceSegment[]
  onChange: (segments: AudienceSegment[]) => void
}

export function AudienceSegmentEditor({ segments, onChange }: AudienceSegmentEditorProps) {
  const [showAdd, setShowAdd] = useState(false)
  const [newSegment, setNewSegment] = useState<AudienceSegment>({
    name: '',
    description: '',
    pain_points: [],
  })

  const addSegment = () => {
    if (!newSegment.name.trim()) return
    onChange([...segments, { ...newSegment }])
    setNewSegment({ name: '', description: '', pain_points: [] })
    setShowAdd(false)
  }

  return (
    <div className="space-y-3">
      {segments.length > 0 ? (
        <div className="space-y-2">
          {segments.map((segment, i) => (
            <AudienceSegmentCard
              key={i}
              segment={segment}
              onUpdate={(updated) => onChange(segments.map((s, j) => (j === i ? updated : s)))}
              onArchive={() => onChange(segments.filter((_, j) => j !== i))}
            />
          ))}
        </div>
      ) : (
        <p className="text-sm text-muted-foreground">No audience segments yet.</p>
      )}

      {showAdd ? (
        <div className="space-y-3 rounded-xl border border-primary/40 bg-surface/80 p-4">
          <div className="space-y-1.5">
            <label className="text-[10px] font-mono uppercase tracking-[0.22em] text-muted-foreground">
              Segment name
            </label>
            <Input
              value={newSegment.name}
              onChange={(e) => setNewSegment({ ...newSegment, name: e.target.value })}
              placeholder="e.g. Early-career professionals"
              autoFocus
            />
          </div>
          <div className="space-y-1.5">
            <label className="text-[10px] font-mono uppercase tracking-[0.22em] text-muted-foreground">
              Description
            </label>
            <Textarea
              value={newSegment.description}
              onChange={(e) => setNewSegment({ ...newSegment, description: e.target.value })}
              placeholder="Who is this segment and what are they dealing with?"
              rows={2}
            />
          </div>
          <div className="space-y-1.5">
            <label className="text-[10px] font-mono uppercase tracking-[0.22em] text-muted-foreground">
              Pain points
            </label>
            <TagInput
              value={newSegment.pain_points}
              onChange={(tags) => setNewSegment({ ...newSegment, pain_points: tags })}
              placeholder="Add pain point, press Enter"
            />
          </div>
          <div className="flex gap-2">
            <Button type="button" size="sm" onClick={addSegment} className="gap-1.5">
              <Check className="h-3.5 w-3.5" />
              Add Segment
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
          Add Audience Segment
        </Button>
      )}
    </div>
  )
}
