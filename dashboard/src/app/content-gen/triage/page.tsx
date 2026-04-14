'use client'

import dynamic from 'next/dynamic'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { List } from 'lucide-react'

import { Button } from '@/components/ui/button'

const TriageWorkspace = dynamic(
  () => import('@/components/content-gen/triage-workspace').then((mod) => mod.TriageWorkspace),
  {
    ssr: false,
    loading: () => (
      <div className="py-8 text-center text-sm text-muted-foreground">Loading triage workspace…</div>
    ),
  },
)

export default function TriagePage() {
  const router = useRouter()

  return (
    <div className="flex flex-col gap-4 lg:gap-6 lg:items-start">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Link href="/content-gen/backlog">
            <Button
              type="button"
              variant="ghost"
              size="sm"
              className="gap-1.5 h-8"
            >
              <List className="h-3.5 w-3.5" />
              Back to backlog
            </Button>
          </Link>
        </div>
      </div>
      <TriageWorkspace onClose={() => router.push('/content-gen/backlog')} />
    </div>
  )
}
