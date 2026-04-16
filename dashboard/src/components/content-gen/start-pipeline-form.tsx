'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'

import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { FormDescription, FormField, FormLabel, FormMessage } from '@/components/ui/form-field'
import { Input } from '@/components/ui/input'
import { NativeSelect } from '@/components/ui/native-select'
import { startPipeline } from '@/lib/content-gen-api'
import {
  PIPELINE_STAGE_ORDER,
  PIPELINE_STAGE_SHORT_LABELS,
  TOTAL_PIPELINE_STAGES,
} from '@/types/content-gen'

export function StartPipelineForm({
  onSuccess,
  initialTheme,
}: {
  onSuccess?: (pipelineId: string) => void
  initialTheme?: string
} = {}) {
  const router = useRouter()
  const [theme, setTheme] = useState(initialTheme ?? '')
  const [contentType, setContentType] = useState('short_form_video')
  const [effortTier, setEffortTier] = useState<'quick' | 'standard' | 'deep'>('standard')
  const [owner, setOwner] = useState('')
  const [channelGoal, setChannelGoal] = useState('')
  const [successTarget, setSuccessTarget] = useState('')
  const [fromStage, setFromStage] = useState(1)
  const [toStage, setToStage] = useState(TOTAL_PIPELINE_STAGES - 1)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const hasInvalidRange = fromStage > toStage

  useEffect(() => {
    setTheme(initialTheme ?? '')
    setError(null)
  }, [initialTheme])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()

    if (!theme.trim()) {
      setError('Enter a theme to start.')
      return
    }

    if (hasInvalidRange) {
      setError('Choose a valid stage range where the end stage comes after the start stage.')
      return
    }

    setIsSubmitting(true)
    setError(null)

    try {
      const result = await startPipeline({
        theme: theme.trim(),
        content_type: contentType,
        effort_tier: effortTier,
        owner: owner.trim(),
        channel_goal: channelGoal.trim(),
        success_target: successTarget.trim(),
        from_stage: fromStage,
        to_stage: toStage,
      })
      if (onSuccess) {
        onSuccess(result.pipeline_id)
      } else {
        router.push(`/content-gen/pipeline/${result.pipeline_id}`)
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to start pipeline')
      setIsSubmitting(false)
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-5">
      <FormField>
        <FormLabel htmlFor="theme" required>
          Theme
        </FormLabel>
        <FormDescription>
          Define the topic or production theme that should drive the selected pipeline slice.
        </FormDescription>
        <Input
          id="theme"
          type="text"
          value={theme}
          onChange={(e) => setTheme(e.target.value)}
          placeholder='e.g. "productivity tips for remote workers"'
          disabled={isSubmitting}
        />
      </FormField>

      <div className="grid gap-4 sm:grid-cols-2">
        <FormField>
          <FormLabel htmlFor="content-type">Content Type</FormLabel>
          <NativeSelect
            id="content-type"
            value={contentType}
            onChange={(e) => setContentType(e.target.value)}
            disabled={isSubmitting}
          >
            <option value="short_form_video">Short-form video</option>
            <option value="carousel">Carousel</option>
            <option value="thread">Thread</option>
            <option value="newsletter">Newsletter</option>
            <option value="article">Article</option>
            <option value="launch_asset">Launch asset</option>
            <option value="webinar">Webinar</option>
          </NativeSelect>
        </FormField>

        <FormField>
          <FormLabel htmlFor="effort-tier">Effort Tier</FormLabel>
          <NativeSelect
            id="effort-tier"
            value={effortTier}
            onChange={(e) => setEffortTier(e.target.value as 'quick' | 'standard' | 'deep')}
            disabled={isSubmitting}
          >
            <option value="quick">Quick</option>
            <option value="standard">Standard</option>
            <option value="deep">Deep</option>
          </NativeSelect>
        </FormField>
      </div>

      <div className="grid gap-4 sm:grid-cols-3">
        <FormField>
          <FormLabel htmlFor="owner">Owner</FormLabel>
          <Input
            id="owner"
            type="text"
            value={owner}
            onChange={(e) => setOwner(e.target.value)}
            placeholder="content-team"
            disabled={isSubmitting}
          />
        </FormField>

        <FormField>
          <FormLabel htmlFor="channel-goal">Channel Goal</FormLabel>
          <Input
            id="channel-goal"
            type="text"
            value={channelGoal}
            onChange={(e) => setChannelGoal(e.target.value)}
            placeholder="Shorts growth"
            disabled={isSubmitting}
          />
        </FormField>

        <FormField>
          <FormLabel htmlFor="success-target">Success Target</FormLabel>
          <Input
            id="success-target"
            type="text"
            value={successTarget}
            onChange={(e) => setSuccessTarget(e.target.value)}
            placeholder="High save rate"
            disabled={isSubmitting}
          />
        </FormField>
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <FormField>
          <FormLabel htmlFor="from-stage">From</FormLabel>
          <NativeSelect
            id="from-stage"
            value={String(fromStage)}
            onChange={(e) => setFromStage(Number(e.target.value))}
            disabled={isSubmitting}
          >
            {PIPELINE_STAGE_ORDER.slice(1).map((stageName, idx) => (
              <option key={idx + 1} value={idx + 1}>
                {String(idx + 1).padStart(2, '0')} - {PIPELINE_STAGE_SHORT_LABELS[stageName]}
              </option>
            ))}
          </NativeSelect>
        </FormField>

        <FormField>
          <FormLabel htmlFor="to-stage">To</FormLabel>
          <NativeSelect
            id="to-stage"
            value={String(toStage)}
            onChange={(e) => setToStage(Number(e.target.value))}
            disabled={isSubmitting}
          >
            {PIPELINE_STAGE_ORDER.slice(1).map((stageName, idx) => (
              <option key={idx + 1} value={idx + 1}>
                {String(idx + 1).padStart(2, '0')} - {PIPELINE_STAGE_SHORT_LABELS[stageName]}
              </option>
            ))}
          </NativeSelect>
        </FormField>
      </div>

      {hasInvalidRange ? (
        <FormMessage tone="error">
          The selected stage range is invalid. Adjust the start or end stage before submitting.
        </FormMessage>
      ) : null}

      {error ? (
        <Alert variant="destructive">
          <AlertTitle>Pipeline start failed</AlertTitle>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      ) : null}

      <Button
        type="submit"
        disabled={isSubmitting || !theme.trim() || hasInvalidRange}
        className="w-full bg-warning text-background hover:bg-warning/90"
      >
        {isSubmitting ? 'Starting...' : 'Start Pipeline'}
      </Button>
    </form>
  )
}
