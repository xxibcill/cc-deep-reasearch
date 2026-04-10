'use client'

import Link from 'next/link'
import { Activity } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { CommandPalette, KeyboardHint } from '@/components/command-palette'
import { NotificationProvider } from '@/components/ui/notification-center'

export function AppShell({ children }: { children: React.ReactNode }) {
  return (
    <NotificationProvider>
      <CommandPalette />
      <KeyboardHint />
      <Link
        href="#main-content"
        className="sr-only fixed left-4 top-4 z-[60] rounded-md bg-background px-3 py-2 text-sm font-medium text-foreground shadow-lg focus:not-sr-only focus:outline-none focus:ring-2 focus:ring-ring"
      >
        Skip to main content
      </Link>
      <header className="sticky top-0 z-50 border-b border-border/70 bg-background/82 backdrop-blur-xl">
        <div className="mx-auto max-w-content px-page-x">
          <div className="flex flex-col gap-4 py-4 lg:flex-row lg:items-end lg:justify-between">
            <div className="min-w-0">
              <div className="mt-3 flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
                <Badge variant="outline" className="text-[0.64rem]">
                  Dashboard
                </Badge>
                <span>
                  Operational visibility for research runs, telemetry, and publishing pipelines.
                </span>
              </div>
            </div>

            <div className="flex flex-col gap-3 lg:items-end">
              <div className="flex items-center gap-2 rounded-full border border-border/70 bg-surface/75 px-3 py-1.5 text-[0.72rem] text-muted-foreground shadow-card">
                <Activity className="h-3.5 w-3.5 text-primary" />
                Workspace online
              </div>
            </div>
          </div>
        </div>
      </header>
      <main id="main-content">{children}</main>
    </NotificationProvider>
  )
}
