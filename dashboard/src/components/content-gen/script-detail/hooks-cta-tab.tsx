'use client'

import { useState } from 'react'
import { CheckCircle2, Megaphone, Loader2, Sparkles } from 'lucide-react'
import type { CtaVariants, HookSet } from '@/types/content-gen'
import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/button'
import { generateScriptVariants, updateScript } from '@/lib/content-gen-api'

interface HooksCtaTabProps {
  hooks: HookSet
  cta: string
  script: string
  runId: string
  onApply: () => void
}

export function HooksCtaTab({ hooks, cta, script, runId, onApply }: HooksCtaTabProps) {
  const [isGenerating, setIsGenerating] = useState(false)
  const [selectedHook, setSelectedHook] = useState<string | null>(hooks.best_hook)
  const [selectedCta, setSelectedCta] = useState<string | null>(cta || null)
  const [ctaVariants, setCtaVariants] = useState<CtaVariants | null>(null)
  const [isApplying, setIsApplying] = useState(false)

  const handleGenerateVariants = async () => {
    setIsGenerating(true)
    try {
      const result = await generateScriptVariants(runId)
      setCtaVariants(result.cta_variants)
      setSelectedHook(result.hooks.best_hook)
      setSelectedCta(result.cta_variants.best_cta)
    } catch (err) {
      console.error('Failed to generate variants:', err)
    } finally {
      setIsGenerating(false)
    }
  }

  const handleApply = async () => {
    if (!selectedHook && !selectedCta) return

    setIsApplying(true)
    try {
      // Build updated script with selected hook prepended and CTA appended
      let updatedScript = script
      if (selectedHook) {
        // Remove existing hook line if present
        const lines = updatedScript.split('\n')
        const nonHookLines = lines.filter(
          (line) => !line.trim().toLowerCase().startsWith('hook:')
        )
        updatedScript = `Hook: ${selectedHook}\n${nonHookLines.join('\n').trim()}`
      }

      await updateScript(runId, {
        hook: selectedHook ?? undefined,
        cta: selectedCta ?? undefined,
        script: updatedScript,
      })
      onApply()
    } catch (err) {
      console.error('Failed to apply variants:', err)
    } finally {
      setIsApplying(false)
    }
  }

  const allHooks = ctaVariants ? [...new Set([...hooks.hooks, ctaVariants.ctas.length > 0 ? '(New)' : ''].filter(Boolean))] : hooks.hooks
  const displayHooks = ctaVariants ? [...hooks.hooks, ...ctaVariants.ctas.filter(c => !hooks.hooks.includes(c))] : hooks.hooks
  const displayCtas = ctaVariants ? ctaVariants.ctas : (cta ? [cta] : [])
  const hasNewVariants = ctaVariants !== null

  const hasChanges = selectedHook !== hooks.best_hook || selectedCta !== (cta || null)

  return (
    <div className="space-y-6">
      {/* Header with actions */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Sparkles className="h-4 w-4 text-muted-foreground" />
          <span className="text-sm text-muted-foreground">
            Generate new variants with AI
          </span>
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={handleGenerateVariants}
          disabled={isGenerating}
        >
          {isGenerating ? (
            <>
              <Loader2 className="h-3.5 w-3.5 mr-1.5 animate-spin" />
              Generating...
            </>
          ) : (
            <>
              <Sparkles className="h-3.5 w-3.5 mr-1.5" />
              Generate Variants
            </>
          )}
        </Button>
      </div>

      {/* Hook Variations */}
      <div className="space-y-4">
        <h2 className="text-lg font-semibold font-display">Hook Variations</h2>
        {hooks.best_hook_reason && (
          <p className="text-sm text-muted-foreground">
            <span className="italic">&ldquo;{hooks.best_hook_reason}&rdquo;</span>
          </p>
        )}
        <div className="space-y-3">
          {displayHooks.map((hook, i) => {
            const isOriginal = i < hooks.hooks.length
            const isBest = hook === hooks.best_hook
            const isSelected = hook === selectedHook
            return (
              <div
                key={`${hook}-${i}`}
                className={cn(
                  'rounded-sm border p-4 transition-all cursor-pointer',
                  isSelected
                    ? 'border-primary bg-primary/10 ring-1 ring-primary/30'
                    : 'border-border bg-background hover:border-primary/30'
                )}
                onClick={() => setSelectedHook(hook)}
              >
                {isBest && !hasNewVariants && (
                  <div className="flex items-center gap-1.5 mb-2">
                    <CheckCircle2 className="h-3.5 w-3.5 text-primary" />
                    <span className="text-xs font-semibold uppercase tracking-wider text-primary">
                      Best Hook
                    </span>
                  </div>
                )}
                {isSelected && (
                  <div className="flex items-center gap-1.5 mb-2">
                    <CheckCircle2 className="h-3.5 w-3.5 text-primary" />
                    <span className="text-xs font-semibold uppercase tracking-wider text-primary">
                      Selected
                    </span>
                  </div>
                )}
                {!isOriginal && (
                  <div className="flex items-center gap-1.5 mb-2">
                    <Sparkles className="h-3.5 w-3.5 text-amber-500" />
                    <span className="text-xs font-semibold uppercase tracking-wider text-amber-500">
                      New
                    </span>
                  </div>
                )}
                <p className="text-sm leading-relaxed text-foreground">{hook}</p>
              </div>
            )
          })}
        </div>
      </div>

      {/* CTA Variations */}
      {displayCtas.length > 0 && (
        <div className="space-y-3">
          <h2 className="text-lg font-semibold font-display">Call to Action</h2>
          <div className="space-y-3">
            {displayCtas.map((ct, i) => {
              const isOriginal = cta && ct === cta
              const isSelected = ct === selectedCta
              return (
                <div
                  key={`${ct}-${i}`}
                  className={cn(
                    'rounded-sm border p-4 transition-all cursor-pointer',
                    isSelected
                      ? 'border-primary bg-primary/10 ring-1 ring-primary/30'
                      : 'border-border bg-background hover:border-primary/30'
                  )}
                  onClick={() => setSelectedCta(ct)}
                >
                  {isSelected && (
                    <div className="flex items-center gap-1.5 mb-2">
                      <CheckCircle2 className="h-3.5 w-3.5 text-primary" />
                      <span className="text-xs font-semibold uppercase tracking-wider text-primary">
                        Selected
                      </span>
                    </div>
                  )}
                  {!isOriginal && (
                    <div className="flex items-center gap-1.5 mb-2">
                      <Sparkles className="h-3.5 w-3.5 text-amber-500" />
                      <span className="text-xs font-semibold uppercase tracking-wider text-amber-500">
                        New
                      </span>
                    </div>
                  )}
                  <div className="flex items-start gap-3">
                    <Megaphone className="h-4 w-4 text-muted-foreground mt-0.5" />
                    <p className="text-sm leading-relaxed text-foreground">{ct}</p>
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      )}

      {/* Apply Button */}
      {hasChanges && (
        <div className="flex items-center justify-between pt-4 border-t">
          <p className="text-sm text-muted-foreground">
            You have unsaved changes
          </p>
          <Button onClick={handleApply} disabled={isApplying}>
            {isApplying ? (
              <>
                <Loader2 className="h-3.5 w-3.5 mr-1.5 animate-spin" />
                Applying...
              </>
            ) : (
              'Apply to Script'
            )}
          </Button>
        </div>
      )}
    </div>
  )
}
