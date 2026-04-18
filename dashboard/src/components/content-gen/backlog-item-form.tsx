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
  title: string
  one_line_summary: string
  raw_idea: string
  constraints: string
  category: string
  audience: string
  persona_detail: string
  problem: string
  emotional_driver: string
  urgency_level: string
  why_now: string
  hook: string
  content_type: string
  format_duration: string
  key_message: string
  call_to_action: string
  evidence: string
  proof_gap_note: string
  expertise_reason: string
  genericity_risk: string
  risk_level: string
  source_theme: string
  selection_reasoning: string
}

interface FormErrors {
  title?: string
  raw_idea?: string
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
    title: item?.title ?? item?.idea ?? '',
    one_line_summary: item?.one_line_summary ?? item?.idea ?? '',
    raw_idea: item?.raw_idea ?? '',
    constraints: item?.constraints ?? '',
    category: item?.category ?? '',
    audience: item?.audience ?? '',
    persona_detail: item?.persona_detail ?? '',
    problem: item?.problem ?? '',
    emotional_driver: item?.emotional_driver ?? '',
    urgency_level: item?.urgency_level ?? '',
    why_now: item?.why_now ?? '',
    hook: item?.hook ?? item?.potential_hook ?? '',
    content_type: item?.content_type ?? '',
    format_duration: item?.format_duration ?? '',
    key_message: item?.key_message ?? '',
    call_to_action: item?.call_to_action ?? '',
    evidence: item?.evidence ?? '',
    proof_gap_note: item?.proof_gap_note ?? '',
    expertise_reason: item?.expertise_reason ?? '',
    genericity_risk: item?.genericity_risk ?? '',
    risk_level: item?.risk_level ?? 'medium',
    source_theme: item?.source_theme ?? '',
    selection_reasoning: item?.selection_reasoning ?? '',
  })
  const [errors, setErrors] = useState<FormErrors>({})

  const handleOpenChange = (nextOpen: boolean) => {
    if (nextOpen) {
      setForm({
        title: item?.title ?? item?.idea ?? '',
        one_line_summary: item?.one_line_summary ?? item?.idea ?? '',
        raw_idea: item?.raw_idea ?? '',
        constraints: item?.constraints ?? '',
        category: item?.category ?? '',
        audience: item?.audience ?? '',
        persona_detail: item?.persona_detail ?? '',
        problem: item?.problem ?? '',
        emotional_driver: item?.emotional_driver ?? '',
        urgency_level: item?.urgency_level ?? '',
        why_now: item?.why_now ?? '',
        hook: item?.hook ?? item?.potential_hook ?? '',
        content_type: item?.content_type ?? '',
        format_duration: item?.format_duration ?? '',
        key_message: item?.key_message ?? '',
        call_to_action: item?.call_to_action ?? '',
        evidence: item?.evidence ?? '',
        proof_gap_note: item?.proof_gap_note ?? '',
        expertise_reason: item?.expertise_reason ?? '',
        genericity_risk: item?.genericity_risk ?? '',
        risk_level: item?.risk_level ?? 'medium',
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

    if (!form.title.trim() && !form.raw_idea.trim()) {
      newErrors.title = 'Title or raw idea is required.'
      newErrors.raw_idea = 'Title or raw idea is required.'
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

        if (form.title.trim()) {
          patch.title = form.title.trim()
        }
        if (form.one_line_summary.trim()) patch.one_line_summary = form.one_line_summary.trim()
        if (form.raw_idea.trim()) patch.raw_idea = form.raw_idea.trim()
        if (form.constraints.trim()) patch.constraints = form.constraints.trim()
        if (form.category) patch.category = form.category
        if (form.audience.trim()) patch.audience = form.audience.trim()
        if (form.persona_detail.trim()) patch.persona_detail = form.persona_detail.trim()
        if (form.problem.trim()) patch.problem = form.problem.trim()
        if (form.emotional_driver.trim()) patch.emotional_driver = form.emotional_driver.trim()
        if (form.urgency_level) patch.urgency_level = form.urgency_level
        if (form.why_now.trim()) patch.why_now = form.why_now.trim()
        if (form.hook.trim()) {
          patch.hook = form.hook.trim()
        }
        if (form.content_type.trim()) patch.content_type = form.content_type.trim()
        if (form.format_duration.trim()) patch.format_duration = form.format_duration.trim()
        if (form.key_message.trim()) patch.key_message = form.key_message.trim()
        if (form.call_to_action.trim()) patch.call_to_action = form.call_to_action.trim()
        if (form.evidence.trim()) patch.evidence = form.evidence.trim()
        if (form.proof_gap_note.trim()) patch.proof_gap_note = form.proof_gap_note.trim()
        if (form.expertise_reason.trim()) patch.expertise_reason = form.expertise_reason.trim()
        if (form.genericity_risk.trim()) patch.genericity_risk = form.genericity_risk.trim()
        if (form.risk_level) patch.risk_level = form.risk_level
        if (form.source_theme.trim()) patch.source_theme = form.source_theme.trim()
        if (form.selection_reasoning.trim()) patch.selection_reasoning = form.selection_reasoning.trim()

        await onSubmitEdit(item.idea_id, patch)
      } else if (onSubmitCreate) {
        const data: Record<string, unknown> = {
          title: form.title.trim(),
        }
        if (form.one_line_summary.trim()) data.one_line_summary = form.one_line_summary.trim()
        if (form.raw_idea.trim()) data.raw_idea = form.raw_idea.trim()
        if (form.constraints.trim()) data.constraints = form.constraints.trim()
        if (form.category) data.category = form.category
        if (form.audience.trim()) data.audience = form.audience.trim()
        if (form.persona_detail.trim()) data.persona_detail = form.persona_detail.trim()
        if (form.problem.trim()) data.problem = form.problem.trim()
        if (form.emotional_driver.trim()) data.emotional_driver = form.emotional_driver.trim()
        if (form.urgency_level) data.urgency_level = form.urgency_level
        if (form.why_now.trim()) data.why_now = form.why_now.trim()
        if (form.hook.trim()) {
          data.hook = form.hook.trim()
        }
        if (form.content_type.trim()) data.content_type = form.content_type.trim()
        if (form.format_duration.trim()) data.format_duration = form.format_duration.trim()
        if (form.key_message.trim()) data.key_message = form.key_message.trim()
        if (form.call_to_action.trim()) data.call_to_action = form.call_to_action.trim()
        if (form.evidence.trim()) data.evidence = form.evidence.trim()
        if (form.proof_gap_note.trim()) data.proof_gap_note = form.proof_gap_note.trim()
        if (form.expertise_reason.trim()) data.expertise_reason = form.expertise_reason.trim()
        if (form.genericity_risk.trim()) data.genericity_risk = form.genericity_risk.trim()
        if (form.risk_level) data.risk_level = form.risk_level
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
    if (trigger && isValidElement(trigger) && typeof trigger.type !== 'string') {
      type TriggerProps = ComponentPropsWithRef<typeof trigger.type>
      const originalOnClick = (trigger.props as TriggerProps).onClick

      return cloneElement(trigger, {
        onClick: (event: React.MouseEvent<HTMLElement>) => {
          event.stopPropagation()
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
                ? 'Update the operator-managed fields for this backlog item. Keep at least a title or a raw idea memo.'
                : 'Create a new backlog item. Provide either a title or a raw idea memo.'}
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
                <Label htmlFor="title">
                  Title <span className="text-error">*</span>
                </Label>
                <Textarea
                  id="title"
                  value={form.title}
                  onChange={setField('title')}
                  placeholder="Specific editorial title..."
                  rows={2}
                  className={errors.title ? 'border-error' : ''}
                />
                {errors.title && (
                  <p className="text-xs text-error">{errors.title}</p>
                )}
              </div>

              <div className="space-y-2">
                <Label htmlFor="raw_idea">Raw Idea</Label>
                <Textarea
                  id="raw_idea"
                  value={form.raw_idea}
                  onChange={setField('raw_idea')}
                  placeholder="Messy thought dump, unstructured angle, or partial concept..."
                  rows={3}
                  className={errors.raw_idea ? 'border-error' : ''}
                />
                {errors.raw_idea && (
                  <p className="text-xs text-error">{errors.raw_idea}</p>
                )}
              </div>

              <div className="space-y-2">
                <Label htmlFor="one_line_summary">One-line Summary</Label>
                <Textarea
                  id="one_line_summary"
                  value={form.one_line_summary}
                  onChange={setField('one_line_summary')}
                  placeholder="One sentence describing the idea clearly..."
                  rows={2}
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="constraints">Constraints</Label>
                <Textarea
                  id="constraints"
                  value={form.constraints}
                  onChange={setField('constraints')}
                  placeholder="Brand, compliance, production, or must-avoid constraints..."
                  rows={2}
                />
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
                <Label htmlFor="persona_detail">Persona Detail</Label>
                <Input
                  id="persona_detail"
                  value={form.persona_detail}
                  onChange={setField('persona_detail')}
                  placeholder="More specific persona context..."
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

              <div className="grid gap-5 md:grid-cols-2">
                <div className="space-y-2">
                  <Label htmlFor="emotional_driver">Emotional Driver</Label>
                  <Input
                    id="emotional_driver"
                    value={form.emotional_driver}
                    onChange={setField('emotional_driver')}
                    placeholder="What emotional tension makes this matter?"
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="urgency_level">Urgency Level</Label>
                  <NativeSelect id="urgency_level" value={form.urgency_level} onChange={setField('urgency_level')}>
                    <option value="">Select urgency...</option>
                    <option value="low">low</option>
                    <option value="medium">medium</option>
                    <option value="high">high</option>
                  </NativeSelect>
                </div>
              </div>

              <div className="space-y-2">
                <Label htmlFor="why_now">Why Now</Label>
                <Textarea
                  id="why_now"
                  value={form.why_now}
                  onChange={setField('why_now')}
                  placeholder="Why this idea matters right now..."
                  rows={2}
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="hook">Hook</Label>
                <Textarea
                  id="hook"
                  value={form.hook}
                  onChange={setField('hook')}
                  placeholder="Opening line or first-frame idea..."
                  rows={2}
                />
              </div>

              <div className="grid gap-5 md:grid-cols-2">
                <div className="space-y-2">
                  <Label htmlFor="content_type">Content Type</Label>
                  <Input
                    id="content_type"
                    value={form.content_type}
                    onChange={setField('content_type')}
                    placeholder="short_video, carousel, etc."
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="format_duration">Format Duration</Label>
                  <Input
                    id="format_duration"
                    value={form.format_duration}
                    onChange={setField('format_duration')}
                    placeholder="60_seconds"
                  />
                </div>
              </div>

              <div className="space-y-2">
                <Label htmlFor="key_message">Key Message</Label>
                <Textarea
                  id="key_message"
                  value={form.key_message}
                  onChange={setField('key_message')}
                  placeholder="Main takeaway the audience should leave with..."
                  rows={2}
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="call_to_action">Call to Action</Label>
                <Input
                  id="call_to_action"
                  value={form.call_to_action}
                  onChange={setField('call_to_action')}
                  placeholder="What should the viewer do next?"
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="evidence">Evidence</Label>
                <Textarea
                  id="evidence"
                  value={form.evidence}
                  onChange={setField('evidence')}
                  placeholder="What supports this idea?"
                  rows={2}
                />
              </div>

              <div className="grid gap-5 md:grid-cols-2">
                <div className="space-y-2">
                  <Label htmlFor="proof_gap_note">Proof Gap Note</Label>
                  <Textarea
                    id="proof_gap_note"
                    value={form.proof_gap_note}
                    onChange={setField('proof_gap_note')}
                    placeholder="What still needs stronger proof?"
                    rows={2}
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="expertise_reason">Expertise Reason</Label>
                  <Textarea
                    id="expertise_reason"
                    value={form.expertise_reason}
                    onChange={setField('expertise_reason')}
                    placeholder="Why does this fit the creator's authority?"
                    rows={2}
                  />
                </div>
              </div>

              <div className="grid gap-5 md:grid-cols-2">
                <div className="space-y-2">
                  <Label htmlFor="genericity_risk">Genericity Risk</Label>
                  <Input
                    id="genericity_risk"
                    value={form.genericity_risk}
                    onChange={setField('genericity_risk')}
                    placeholder="low, medium, high, or a note..."
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="risk_level">Risk Level</Label>
                  <NativeSelect id="risk_level" value={form.risk_level} onChange={setField('risk_level')}>
                    <option value="low">low</option>
                    <option value="medium">medium</option>
                    <option value="high">high</option>
                  </NativeSelect>
                </div>
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
