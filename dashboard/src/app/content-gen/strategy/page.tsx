'use client'

import Link from 'next/link'
import { ArrowLeft } from 'lucide-react'
import { StrategyEditor } from '@/components/content-gen/strategy-editor'

export default function StrategyPage() {
  return (
    <div className="max-w-2xl mx-auto space-y-6">
      <div className="flex items-center gap-3">
        <Link
          href="/content-gen"
          className="text-muted-foreground hover:text-foreground transition-colors"
        >
          <ArrowLeft className="h-5 w-5" />
        </Link>
        <div>
          <h1 className="text-xl font-bold">Strategy Memory</h1>
          <p className="text-sm text-muted-foreground">
            Configure your content strategy — niche, pillars, tone, and audience
          </p>
        </div>
      </div>

      <div className="border rounded-md p-6">
        <StrategyEditor />
      </div>
    </div>
  )
}
