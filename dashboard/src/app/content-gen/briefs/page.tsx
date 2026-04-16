'use client'

import { useEffect } from 'react'
import dynamic from 'next/dynamic'
import { useSearchParams } from 'next/navigation'

import { BriefIndexPanel } from '@/components/content-gen/brief-index-panel'

function PanelLoadingMessage({ label }: { label: string }) {
  return <div className="py-8 text-center text-sm text-muted-foreground">{label}</div>
}

export default function BriefsPage() {
  const searchParams = useSearchParams()
  const lifecycleFilter = searchParams.get('lifecycle_state') || undefined

  return (
    <div className="space-y-6">
      <BriefIndexPanel initialLifecycleState={lifecycleFilter} />
    </div>
  )
}