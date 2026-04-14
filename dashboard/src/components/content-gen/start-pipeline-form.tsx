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
