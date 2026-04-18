'use client'

import { useState } from 'react'
import { Archive, Check, Edit2, Plus, X } from 'lucide-react'
import type { ContentPillar } from '@/types/content-gen'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { Badge } from '@/components/ui/badge'
import { TagInput } from '@/components/ui/tag-input'
import { DraggableList } from '@/components/ui/draggable-list'

interface ContentPillarCardProps {
  pillar: ContentPillar
  onUpdate: (updated: ContentPillar) => void
  onArchive: () => void
}

function ContentPillarCard({ pillar, onUpdate, onArchive }: ContentPillarCardProps) {
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState(pillar)

  const save = () => {
    onUpdate(draft)
    setEditing(false)
  }

  const cancel = () => {
    setDraft(pillar)
    setEditing(false)
  }

  if (editing) {
    return (
      <div className="space-y-3 rounded-xl border border-primary/40 bg-surface/80 p-4">
        <div className="space-y-1.5">
          <label className="text-[10px] font-mono uppercase tracking-[0.22em] text-muted-foreground">
            Pillar name
          </label>
          <Input
            value={draft.name}
            onChange={(e) => setDraft({ ...draft, name: e.target.value })}
            placeholder="e.g. Money Mindset"
          />
        </div>
        <div className="space-y-1.5">
          <label className="text-[10px] font-mono uppercase tracking-[0.22em] text-muted-foreground">
            Description
          </label>
          <Textarea
            value={draft.description}
            onChange={(e) => setDraft({ ...draft, description: e.target.value })}
            placeholder="What content lives under this pillar?"
            rows={2}
          />
        </div>
        <div className="space-y-1.5">
          <label className="text-[10px] font-mono uppercase tracking-[0.22em] text-muted-foreground">
            Content types
          </label>
          <TagInput
            value={draft.content_types}
            onChange={(tags) => setDraft({ ...draft, content_types: tags })}
            placeholder="e.g. Short-form video, Carousel"
          />
        </div>
        <div className="flex gap-2">
          <Button type="button" size="sm" onClick={save} className="gap-1.5">
            <Check className="h-3.5 w-3.5" />
            Save
          </Button>
          <Button type="button" variant="ghost" size="sm" onClick={cancel}>
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
          <p className="text-sm font-medium text-foreground">{pillar.name}</p>
          {pillar.description && (
            <p className="mt-1 text-xs text-foreground/72 leading-relaxed">{pillar.description}</p>
          )}
          {pillar.content_types.length > 0 && (
            <div className="mt-2 flex flex-wrap gap-1">
              {pillar.content_types.slice(0, 4).map((ct) => (
                <Badge key={ct} variant="outline" className="text-[10px] px-1.5 py-0">
                  {ct}
                </Badge>
              ))}
              {pillar.content_types.length > 4 && (
                <Badge variant="secondary" className="text-[10px] px-1.5 py-0">
                  +{pillar.content_types.length - 4}
                </Badge>
              )}
            </div>
          )}
        </div>
        <div className="flex gap-1 opacity-0 transition-opacity group-hover:opacity-100">
          <Button type="button" variant="ghost" size="icon" onClick={() => setEditing(true)}>
            <Edit2 className="h-3.5 w-3.5" />
          </Button>
          <Button type="button" variant="ghost" size="icon" onClick={onArchive} title="Archive pillar">
            <Archive className="h-3.5 w-3.5" />
          </Button>
        </div>
      </div>
    </div>
  )
}

interface ContentPillarEditorProps {
  pillars: ContentPillar[]
  onChange: (pillars: ContentPillar[]) => void
}

export function ContentPillarEditor({ pillars, onChange }: ContentPillarEditorProps) {
  const [showAdd, setShowAdd] = useState(false)
  const [newPillar, setNewPillar] = useState<ContentPillar>({
    name: '',
    description: '',
    content_types: [],
  })

  const addPillar = () => {
    if (!newPillar.name.trim()) return
    onChange([...pillars, { ...newPillar }])
    setNewPillar({ name: '', description: '', content_types: [] })
    setShowAdd(false)
  }

  const updatePillar = (index: number, updated: ContentPillar) => {
    onChange(pillars.map((p, i) => (i === index ? updated : p)))
  }

  const archivePillar = (index: number) => {
    onChange(pillars.filter((_, i) => i !== index))
  }

  const handleReorder = (reordered: { id: string; data: ContentPillar }[]) => {
    onChange(reordered.map((r) => r.data))
  }

  const draggableItems = pillars.map((p, i) => ({ id: `pillar-${i}`, data: p }))

  return (
    <div className="space-y-3">
      {pillars.length > 0 ? (
        <DraggableList
          items={draggableItems}
          onReorder={handleReorder}
          renderItem={(item, index) => (
            <ContentPillarCard
              pillar={item.data}
              onUpdate={(updated) => updatePillar(index, updated)}
              onArchive={() => archivePillar(index)}
            />
          )}
        />
      ) : (
        <p className="text-sm text-muted-foreground">No content pillars yet. Add your first one below.</p>
      )}

      {showAdd ? (
        <div className="space-y-3 rounded-xl border border-primary/40 bg-surface/80 p-4">
          <div className="space-y-1.5">
            <label className="text-[10px] font-mono uppercase tracking-[0.22em] text-muted-foreground">
              Pillar name
            </label>
            <Input
              value={newPillar.name}
              onChange={(e) => setNewPillar({ ...newPillar, name: e.target.value })}
              placeholder="e.g. Money Mindset"
              autoFocus
            />
          </div>
          <div className="space-y-1.5">
            <label className="text-[10px] font-mono uppercase tracking-[0.22em] text-muted-foreground">
              Description
            </label>
            <Textarea
              value={newPillar.description}
              onChange={(e) => setNewPillar({ ...newPillar, description: e.target.value })}
              placeholder="What content lives under this pillar?"
              rows={2}
            />
          </div>
          <div className="space-y-1.5">
            <label className="text-[10px] font-mono uppercase tracking-[0.22em] text-muted-foreground">
              Content types
            </label>
            <TagInput
              value={newPillar.content_types}
              onChange={(tags) => setNewPillar({ ...newPillar, content_types: tags })}
              placeholder="e.g. Short-form video, Carousel"
            />
          </div>
          <div className="flex gap-2">
            <Button type="button" size="sm" onClick={addPillar} className="gap-1.5">
              <Check className="h-3.5 w-3.5" />
              Add Pillar
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
          Add Content Pillar
        </Button>
      )}
    </div>
  )
}