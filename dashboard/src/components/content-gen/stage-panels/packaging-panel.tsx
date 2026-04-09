'use client'

import { Badge } from '@/components/ui/badge'
import type { PlatformPackage, PipelineContext } from '@/types/content-gen'

function PackageCard({ pkg }: { pkg: PlatformPackage }) {
  return (
    <div className="rounded-[1rem] border border-border/70 bg-background/45 px-4 py-3 space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <Badge variant="outline">{pkg.platform}</Badge>
        <Badge variant="secondary">{pkg.keywords.length} keywords</Badge>
      </div>

      <div className="space-y-2">
        <div>
          <p className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground">Primary Hook</p>
          <p className="text-sm font-medium text-foreground/90">{pkg.primary_hook}</p>
        </div>

        {pkg.alternate_hooks.length > 0 && (
          <div>
            <p className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground">Alternate Hooks</p>
            <p className="text-sm text-foreground/72">{pkg.alternate_hooks.join(' | ')}</p>
          </div>
        )}

        <div>
          <p className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground">Cover Text</p>
          <p className="text-sm text-foreground/80 line-clamp-2">{pkg.cover_text || '—'}</p>
        </div>

        <div>
          <p className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground">Caption</p>
          <p className="text-sm text-foreground/80 line-clamp-3">{pkg.caption || '—'}</p>
        </div>

        {pkg.hashtags.length > 0 && (
          <div>
            <p className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground">Hashtags</p>
            <p className="text-sm text-foreground/60">{pkg.hashtags.join(' ')}</p>
          </div>
        )}

        {pkg.pinned_comment && (
          <div>
            <p className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground">Pinned Comment</p>
            <p className="text-sm text-foreground/72 line-clamp-2">{pkg.pinned_comment}</p>
          </div>
        )}

        {pkg.cta && (
          <div>
            <p className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground">CTA</p>
            <p className="text-sm text-foreground/80">{pkg.cta}</p>
          </div>
        )}

        {pkg.version_notes && (
          <div>
            <p className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground">Version Notes</p>
            <p className="text-sm text-foreground/60 line-clamp-2">{pkg.version_notes}</p>
          </div>
        )}
      </div>
    </div>
  )
}

export function PackagingPanel({ ctx }: { ctx: PipelineContext }) {
  if (!ctx.packaging) {
    return null
  }

  return (
    <div className="grid gap-4 lg:grid-cols-2">
      {ctx.packaging.platform_packages.map((pkg, index) => (
        <PackageCard key={`${pkg.platform}-${index}`} pkg={pkg} />
      ))}
    </div>
  )
}
