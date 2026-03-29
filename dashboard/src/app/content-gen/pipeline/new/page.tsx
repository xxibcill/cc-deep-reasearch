'use client'

import Link from 'next/link'
import { ArrowLeft } from 'lucide-react'
import { StartPipelineForm } from '@/components/content-gen/start-pipeline-form'


export default function NewPipelinePage() {
  return (
    <div className="max-w-xl mx-auto space-y-6">
      <div className="flex items-center gap-3">
        <Link
          href="/content-gen"
          className="text-muted-foreground hover:text-foreground transition-colors"
        >
          <ArrowLeft className="h-5 w-5" />
        </Link>
        <div>
          <h1 className="text-xl font-bold">New Pipeline</h1>
          <p className="text-sm text-muted-foreground">
            Start a full 12-stage content generation pipeline
          </p>
        </div>
      </div>

      <div className="border rounded-md p-6">
        <StartPipelineForm />
      </div>
    </div>
  )
}
