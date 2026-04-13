'use client'

import { cloneElement, isValidElement, useState } from 'react'
import type { ComponentPropsWithRef } from 'react'
import { Pencil, Plus } from 'lucide-react'

import { Alert, AlertDescription } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogBody, DialogFooter } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { NativeSelect } from '@/components/ui/native-select'
import { Textarea } from '@/components/ui/textarea'
import type { BacklogItem, BacklogCategory } from '@/types/content-gen'

const CATEGORY_OPTIONS: BacklogCategory[] = [
  'trend-responsive',
  'evergreen',
  'authority-building',
]

interface BacklogItemFormProps {
  item?: BacklogItem
  onSubmitEdit?: (ideaId: string, patch: Record<string, unknown>) => Promise<void>
  onSubmitCreate?: (data: Record<string, unknown>) => Promise<void>
  trigger?: React.ReactNode
  title?: string
}

interface FormState {
  idea: string
  category: string
  audience: string
  problem: string
  source_theme: string
  selection_reasoning: string
}

interface FormErrors {
  idea?: string
  category?: string
}

export function BacklogItemForm({
  item,
  onSubmitEdit,
  onSubmitCreate,
  trigger,
  title,
}: BacklogItemFormProps) {
  const isEditMode = item !== undefined
  const [open, setOpen] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [submitError, setSubmitError] = useState<string | null>(null)
  const [form, setForm] = useState<FormState>({
    idea: item?.idea ?? '',
    category: item?.category ?? '',
    audience: item?.audience ?? '',
    problem: item?.problem ?? '',
    source_theme: item?.source_theme ?? '',
    selection_reasoning: item?.selection_reasoning ?? '',
  })
  const [errors, setErrors] = useState<FormErrors>({})

  const handleOpenChange = (nextOpen: boolean) => {
    if (nextOpen) {
      setForm({
        idea: item?.idea ?? '',
        category: item?.category ?? '',
        audience: item?.audience ?? '',
        problem: item?.problem ?? '',
        source_theme: item?.source_theme ?? '',
        selection_reasoning: item?.selection_reasoning ?? '',
      })
      setErrors({})
      setSubmitError(null)
    }
    setOpen(nextOpen)
  }

  const validate = (): boolean => {
    const newErrors: FormErrors = {}

    if (!form.idea.trim()) {
      newErrors.idea = 'Idea is required.'
    }

    if (form.category && !CATEGORY_OPTIONS.includes(form.category as BacklogCategory)) {
      newErrors.category = 'Invalid category.'
    }

    setErrors(newErrors)
    return Object.keys(newErrors).length === 0
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setSubmitError(null)

    if (!validate()) {
      return
    }

    try {
      setSubmitting(true)

      if (isEditMode && onSubmitEdit) {
        const patch: Record<string, unknown> = {}

        if (form.idea.trim()) patch.idea = form.idea.trim()
        if (form.category) patch.category = form.category
        if (form.audience.trim()) patch.audience = form.audience.trim()
        if (form.problem.trim()) patch.problem = form.problem.trim()
        if (form.source_theme.trim()) patch.source_theme = form.source_theme.trim()
        if (form.selection_reasoning.trim()) patch.selection_reasoning = form.selection_reasoning.trim()

        await onSubmitEdit(item.idea_id, patch)
      } else if (onSubmitCreate) {
        const data: Record<string, unknown> = {
          idea: form.idea.trim(),
        }
        if (form.category) data.category = form.category
        if (form.audience.trim()) data.audience = form.audience.trim()
        if (form.problem.trim()) data.problem = form.problem.trim()
        if (form.source_theme.trim()) data.source_theme = form.source_theme.trim()
        if (form.selection_reasoning.trim()) data.selection_reasoning = form.selection_reasoning.trim()

        await onSubmitCreate(data)
      }
      setOpen(false)
    } catch (err) {
      setSubmitError(err instanceof Error ? err.message : String(err))
    } finally {
      setSubmitting(false)
    }
  }

  const setField = (field: keyof FormState) => (
    e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>
  ) => {
    setForm((prev) => ({ ...prev, [field]: e.target.value }))
    if (errors[field as keyof FormErrors]) {
      setErrors((prev) => ({ ...prev, [field]: undefined }))
    }
  }

  const renderTrigger = () => {
    if (trigger && isValidElement(trigger)) {
      type TriggerProps = ComponentPropsWithRef<typeof trigger.type>
      const originalOnClick = (trigger.props as TriggerProps).onClick

      return cloneElement(trigger, {
        onClick: (event: React.MouseEvent<HTMLElement>) => {
          if (typeof originalOnClick === 'function') {
            ;(originalOnClick as (e: React.MouseEvent<HTMLElement>) => void)(event)
          }
          if (!event.defaultPrevented) {
            handleOpenChange(true)
          }
        },
      })
    }

    return (
      <Button
        type="button"
        variant="ghost"
        size="icon"
        onClick={() => handleOpenChange(true)}
        className="h-8 w-8 text-muted-foreground/60 hover:text-primary"
        title={isEditMode ? 'Edit item' : 'New item'}
      >
        {isEditMode ? <Pencil className="h-3.5 w-3.5" /> : <Plus className="h-3.5 w-3.5" />}
      </Button>
    )
  }

  return (
    <>
      {renderTrigger()}
      <Dialog open={open} onOpenChange={handleOpenChange}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{title ?? (isEditMode ? 'Edit Backlog Item' : 'New Backlog Item')}</DialogTitle>
            <DialogDescription>
              {isEditMode
                ? 'Update the operator-managed fields for this backlog item. All fields are optional except the idea itself.'
                : 'Create a new backlog item. The idea field is required.'}
            </DialogDescription>
          </DialogHeader>
          <DialogBody>
            <form id="backlog-item-form" onSubmit={handleSubmit} className="space-y-5">
              {submitError && (
                <Alert variant="destructive">
                  <AlertDescription>{submitError}</AlertDescription>
                </Alert>
              )}

              <div className="space-y-2">
                <Label htmlFor="idea">
                  Idea <span className="text-error">*</span>
                </Label>
                <Textarea
                  id="idea"
                  value={form.idea}
                  onChange={setField('idea')}
                  placeholder="The core content idea or angle..."
                  rows={3}
                  className={errors.idea ? 'border-error' : ''}
                />
                {errors.idea && (
                  <p className="text-xs text-error">{errors.idea}</p>
                )}
              </div>

              <div className="space-y-2">
                <Label htmlFor="category">Category</Label>
                <NativeSelect
                  id="category"
                  value={form.category}
                  onChange={setField('category')}
                >
                  <option value="">Select a category...</option>
                  {CATEGORY_OPTIONS.map((cat) => (
                    <option key={cat} value={cat}>
                      {cat}
                    </option>
                  ))}
                </NativeSelect>
              </div>

              <div className="space-y-2">
                <Label htmlFor="audience">Audience</Label>
                <Input
                  id="audience"
                  value={form.audience}
                  onChange={setField('audience')}
                  placeholder="Who is this content for?"
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="problem">Problem</Label>
                <Textarea
                  id="problem"
                  value={form.problem}
                  onChange={setField('problem')}
                  placeholder="What problem does this solve for the audience?"
                  rows={2}
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="source_theme">Source Theme</Label>
                <Input
                  id="source_theme"
                  value={form.source_theme}
                  onChange={setField('source_theme')}
                  placeholder="The theme or trend this idea came from..."
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="selection_reasoning">Selection Reasoning</Label>
                <Textarea
                  id="selection_reasoning"
                  value={form.selection_reasoning}
                  onChange={setField('selection_reasoning')}
                  placeholder="Why was this idea selected?"
                  rows={2}
                />
              </div>
            </form>
          </DialogBody>
          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => handleOpenChange(false)}
              disabled={submitting}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              form="backlog-item-form"
              disabled={submitting}
            >
              {submitting ? 'Saving...' : 'Save Changes'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  )
}
