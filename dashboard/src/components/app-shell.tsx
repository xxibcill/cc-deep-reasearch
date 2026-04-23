'use client'

import { Suspense } from 'react'
import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { NavBar, NavBarBrand } from '@/components/ui/nav-bar'
import { NotificationProvider } from '@/components/ui/notification-center'
import { CommandPalette, KeyboardHint } from '@/components/command-palette'
import { ContentGenNavigation } from '@/components/content-gen/content-gen-navigation'

function ContentGenNavigationSkeleton() {
  return <div className="h-10 w-full animate-pulse rounded-md bg-muted/25" />
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname()
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
        <header className="sticky top-0 z-50 border-b border-border/70 bg-background/86 backdrop-blur-xl">
          <div className="mx-auto max-w-content px-page-x">
            <NavBar leadingSlot={<NavBarBrand />} showCommandTrigger />
            {isContentGenRoute ? (
              <div className="border-t border-border/50 py-2">
                <Suspense fallback={<ContentGenNavigationSkeleton />}>
                  <ContentGenNavigation />
                </Suspense>
              </div>
            ) : null}
          </div>
        </header>
        <main id="main-content">{children}</main>
      </>
    </NotificationProvider>
  )
}
