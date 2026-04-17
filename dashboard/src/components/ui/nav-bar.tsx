'use client'

import { useEffect, useId, useState } from 'react'
import Link from 'next/link'
import { usePathname } from 'next/navigation'
import {
  BarChart3,
  FileVideo,
  FlaskConical,
  Menu,
  Search,
  Settings,
  Trophy,
  X,
} from 'lucide-react'

import { cn } from '@/lib/utils'

const COMMAND_PALETTE_OPEN_EVENT = 'ccdr.command-palette.open'

const navItems = [
  { href: '/', label: 'Research', icon: FlaskConical },
  { href: '/analytics', label: 'Analytics', icon: BarChart3 },
  { href: '/benchmark', label: 'Benchmark', icon: Trophy },
  { href: '/content-gen', label: 'Content', icon: FileVideo },
  { href: '/settings', label: 'Settings', icon: Settings },
]

function isActive(pathname: string, href: string): boolean {
  if (href === '/') return pathname === '/'
  return pathname.startsWith(href)
}

function openCommandPalette() {
  window.dispatchEvent(new Event(COMMAND_PALETTE_OPEN_EVENT))
}

function PrimaryLinks({
  pathname,
  orientation = 'desktop',
  onNavigate,
}: {
  pathname: string
  orientation?: 'desktop' | 'mobile'
  onNavigate?: () => void
}) {
  const isMobile = orientation === 'mobile'

  return (
    <nav
      aria-label={isMobile ? 'Primary mobile' : 'Primary'}
      className={cn(
        isMobile
          ? 'flex flex-col gap-1'
          : 'hidden lg:flex lg:items-center lg:gap-1 lg:rounded-[1rem] lg:border lg:border-border/70 lg:bg-surface/62 lg:p-1'
      )}
    >
      {navItems.map(({ href, label, icon: Icon }) => {
        const active = isActive(pathname, href)

        return (
          <Link
            key={href}
            href={href}
            className={cn(
              'group inline-flex items-center rounded-[0.85rem] border text-sm transition-all duration-200',
              isMobile
                ? 'h-11 justify-between px-3.5'
                : 'h-10 gap-2 border-transparent px-3.5 font-medium',
              active
                ? 'border-primary/30 bg-primary/12 text-foreground shadow-[inset_0_1px_0_rgba(255,255,255,0.04)]'
                : 'border-transparent text-muted-foreground hover:border-border/70 hover:bg-surface-raised/72 hover:text-foreground',
            )}
            aria-current={active ? 'page' : undefined}
            onClick={onNavigate}
          >
            <span className="flex items-center gap-2">
              <Icon
                className={cn(
                  'h-4 w-4 transition-colors',
                  active ? 'text-primary' : 'text-muted-foreground group-hover:text-foreground',
                )}
              />
              <span>{label}</span>
            </span>
            {isMobile ? (
              <span
                className={cn(
                  'rounded-full px-2 py-0.5 text-[0.65rem] uppercase tracking-[0.16em]',
                  active ? 'bg-primary/14 text-primary' : 'bg-muted/40 text-muted-foreground',
                )}
              >
                {active ? 'Current' : 'Open'}
              </span>
            ) : null}
          </Link>
        )
      })}
    </nav>
  )
}

function CommandTrigger({
  compact = false,
  className,
}: {
  compact?: boolean
  className?: string
}) {
  return (
    <button
      type="button"
      onClick={openCommandPalette}
      className={cn(
        'inline-flex items-center rounded-[0.9rem] border border-border/70 bg-surface/62 text-sm text-muted-foreground transition-all duration-200 hover:border-primary/35 hover:bg-surface-raised/78 hover:text-foreground',
        'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/45',
        compact
          ? 'h-10 w-10 justify-center'
          : 'h-10 min-w-[12rem] justify-between gap-3 px-3.5',
        className,
      )}
      aria-label="Open command palette"
    >
      <span className="flex items-center gap-2">
        <Search className="h-4 w-4" />
        {!compact ? <span>Search or jump</span> : null}
      </span>
      {!compact ? (
        <span className="flex items-center gap-1 text-[0.65rem] uppercase tracking-[0.16em] text-muted-foreground">
          <kbd className="rounded-md border border-border/60 bg-background/90 px-1.5 py-0.5 font-mono text-[0.68rem] text-foreground">
            ⌘
          </kbd>
          <kbd className="rounded-md border border-border/60 bg-background/90 px-1.5 py-0.5 font-mono text-[0.68rem] text-foreground">
            K
          </kbd>
        </span>
      ) : null}
    </button>
  )
}

export interface NavBarProps {
  className?: string
}

export function NavBar({ className }: NavBarProps) {
  const pathname = usePathname()
  const menuId = useId()
  const [mobileOpen, setMobileOpen] = useState(false)

  useEffect(() => {
    setMobileOpen(false)
  }, [pathname])

  return (
    <div className={className}>
      <div className="flex h-16 items-center justify-between gap-4">
        <div className="flex min-w-0 items-center gap-3 lg:gap-6">
          <Link
            href="/"
            className="flex min-w-0 items-center gap-3 rounded-[0.95rem] px-1 py-1 text-left transition-colors hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/45"
          >
            <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-[0.85rem] border border-border/70 bg-[linear-gradient(180deg,hsl(var(--surface-raised)),hsl(var(--surface)))] shadow-[inset_0_1px_0_rgba(255,255,255,0.04)]">
              <FlaskConical className="h-4 w-4 text-primary" />
            </span>
            <span className="min-w-0">
              <span className="block truncate font-display text-[1.02rem] font-semibold leading-none text-foreground">
                CC Deep Research
              </span>
              <span className="mt-1 block truncate text-[0.68rem] uppercase tracking-[0.18em] text-muted-foreground">
                Operations Console
              </span>
            </span>
          </Link>

          <PrimaryLinks pathname={pathname} />
        </div>

        <div className="flex items-center gap-2">
          <CommandTrigger className="hidden md:inline-flex" />
          <CommandTrigger compact className="md:hidden" />
          <button
            type="button"
            className="inline-flex h-10 w-10 items-center justify-center rounded-[0.9rem] border border-border/70 bg-surface/62 text-muted-foreground transition-all duration-200 hover:border-primary/35 hover:bg-surface-raised/78 hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/45 lg:hidden"
            aria-expanded={mobileOpen}
            aria-controls={menuId}
            aria-label={mobileOpen ? 'Close navigation menu' : 'Open navigation menu'}
            onClick={() => setMobileOpen((open) => !open)}
          >
            {mobileOpen ? <X className="h-4.5 w-4.5" /> : <Menu className="h-4.5 w-4.5" />}
          </button>
        </div>
      </div>

      <div
        id={menuId}
        className={cn(
          'grid overflow-hidden transition-[grid-template-rows,opacity] duration-200 ease-out lg:hidden',
          mobileOpen ? 'grid-rows-[1fr] opacity-100' : 'grid-rows-[0fr] opacity-0',
        )}
      >
        <div className="overflow-hidden">
          <div className="border-t border-border/60 pb-3 pt-3">
            <PrimaryLinks
              pathname={pathname}
              orientation="mobile"
              onNavigate={() => setMobileOpen(false)}
            />
            <CommandTrigger className="mt-3 w-full justify-between md:hidden" />
          </div>
        </div>
      </div>
    </div>
  )
}

export { navItems, isActive }
