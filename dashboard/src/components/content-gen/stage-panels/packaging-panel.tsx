'use client'

import { Badge } from '@/components/ui/badge'
import type { PipelineContext } from '@/types/content-gen'

export function PackagingPanel({ ctx }: { ctx: PipelineContext }) {
  if (!ctx.packaging) {
    return null
  }

  return (
    <div className="space-y-3">
      {ctx.packaging.platform_packages.map((pkg, index) => (
        <div
          key={`${pkg.platform}-${index}`}
          className="rounded-[1rem] border border-border/70 bg-background/45 px-4 py-3"
        >
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant="outline">{pkg.platform}</Badge>
            <Badge variant="secondary">{pkg.keywords.length} keywords</Badge>
          </div>
          <p className="mt-2 text-sm font-medium text-foreground/90">{pkg.primary_hook}</p>
          {pkg.alternate_hooks.length > 0 ? (
            <p className="mt-2 text-sm text-foreground/72">
              Alternates: {pkg.alternate_hooks.join(' | ')}
            </p>
          ) : null}
        </div>
      ))}
    </div>
  )
}
