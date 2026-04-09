'use client'

import { useRouter } from 'next/navigation'
import { FileText, Play } from 'lucide-react'

import { Button, type ButtonSize, type ButtonVariant } from '@/components/ui/button'
import {
  buildContentStudioHref,
  storeResearchContentBridge,
  type ContentStudioIntent,
  type ResearchContentBridgePayload,
} from '@/lib/research-content-bridge'
import { cn } from '@/lib/utils'

interface ResearchContentActionsProps {
  payload: ResearchContentBridgePayload
  className?: string
  orientation?: 'row' | 'column'
  size?: ButtonSize
  variant?: ButtonVariant
  primaryIntent?: ContentStudioIntent
}

export function ResearchContentActions({
  payload,
  className,
  orientation = 'row',
  size = 'sm',
  variant = 'outline',
  primaryIntent = 'pipeline',
}: ResearchContentActionsProps) {
  const router = useRouter()

  const handleNavigate = (intent: ContentStudioIntent) => {
    storeResearchContentBridge(payload)
    router.push(buildContentStudioHref(payload, intent))
  }

  return (
    <div
      className={cn(
        'flex gap-2',
        orientation === 'column' ? 'flex-col' : 'flex-wrap items-center',
        className,
      )}
    >
      <Button
        type="button"
        variant={primaryIntent === 'pipeline' ? 'default' : variant}
        size={size}
        onClick={() => handleNavigate('pipeline')}
      >
        <Play className="h-3.5 w-3.5" />
        Start Pipeline
      </Button>
      <Button
        type="button"
        variant={primaryIntent === 'quick-script' ? 'default' : variant}
        size={size}
        onClick={() => handleNavigate('quick-script')}
      >
        <FileText className="h-3.5 w-3.5" />
        Open Quick Script
      </Button>
    </div>
  )
}
