'use client'

import { CheckCircle2, Megaphone } from 'lucide-react'
import type { HookSet } from '@/types/content-gen'
import { cn } from '@/lib/utils'

interface HooksCtaTabProps {
  hooks: HookSet
  cta: string
}

export function HooksCtaTab({ hooks, cta }: HooksCtaTabProps) {
  return (
    <div className="space-y-6">
      <div className="space-y-4">
        <h2 className="text-lg font-semibold font-display">Hook Variations</h2>
        <p className="text-sm text-muted-foreground">
          {hooks.best_hook_reason && (
            <span className="italic">&ldquo;{hooks.best_hook_reason}&rdquo;</span>
          )}
        </p>
        <div className="space-y-3">
          {hooks.hooks.map((hook, i) => {
            const isBest = hook === hooks.best_hook
            return (
              <div
                key={i}
                className={cn(
                  'rounded-sm border p-4 transition-all',
                  isBest
                    ? 'border-primary/50 bg-primary/10 ring-1 ring-primary/30'
                    : 'border-border bg-background'
                )}
              >
                {isBest && (
                  <div className="flex items-center gap-1.5 mb-2">
                    <CheckCircle2 className="h-3.5 w-3.5 text-primary" />
                    <span className="text-xs font-semibold uppercase tracking-wider text-primary">
                      Best Hook
                    </span>
                  </div>
                )}
                <p className="text-sm leading-relaxed text-foreground">{hook}</p>
              </div>
            )
          })}
        </div>
      </div>

      {cta && (
        <div className="space-y-3">
          <h2 className="text-lg font-semibold font-display">Call to Action</h2>
          <div className="rounded-sm border border-border bg-background p-4">
            <div className="flex items-start gap-3">
              <Megaphone className="h-4 w-4 text-muted-foreground mt-0.5" />
              <p className="text-sm leading-relaxed text-foreground">{cta}</p>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
