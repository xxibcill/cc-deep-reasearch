'use client'

import { Suspense } from 'react'
import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { Badge } from '@/components/ui/badge'
import { NavBar, navItems } from '@/components/ui/nav-bar'
import { NotificationProvider } from '@/components/ui/notification-center'
import { CommandPalette, KeyboardHint } from '@/components/command-palette'
import { ContentGenNavigation } from '@/components/content-gen/content-gen-navigation'

function ContentGenNavigationSkeleton() {
  return <div className="h-[72px] animate-pulse rounded-md bg-muted/30" />
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname()
  const activeItem =
    navItems.find((item) =>
      item.href === '/' ? pathname === '/' : pathname.startsWith(item.href),
    ) ?? navItems[0]
  const isContentGenRoute = pathname.startsWith('/content-gen')

  return (
    <NotificationProvider>
      <>
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
            <div className="flex flex-col gap-4 py-4">
              <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
                    <Badge variant="outline" className="text-[0.64rem]">
                      {activeItem.label}
                    </Badge>
                  </div>
                </div>

                <div>
                  <NavBar />
                </div>
              </div>

              {isContentGenRoute ? (
                <Suspense fallback={<ContentGenNavigationSkeleton />}>
                  <ContentGenNavigation />
                </Suspense>
              ) : null}
            </div>
          </div>
        </header>
        <main id="main-content">{children}</main>
      </>
    </NotificationProvider>
  )
}
