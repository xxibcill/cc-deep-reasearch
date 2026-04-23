'use client'

import { useEffect, useId, useRef, useState, type ReactNode } from 'react'
import Link from 'next/link'
import { usePathname } from 'next/navigation'
import {
  BarChart3,
  FileVideo,
  FlaskConical,
  Menu,
  Radar,
  Search,
  Settings,
  Trophy,
  X,
  type LucideIcon,
} from 'lucide-react'

import { cn } from '@/lib/utils'

const COMMAND_PALETTE_OPEN_EVENT = 'ccdr.command-palette.open'

export interface NavBarItem {
  href: string
  label: string
  icon: LucideIcon
  match?: (pathname: string) => boolean
}

const defaultNavItems: NavBarItem[] = [
  { href: '/', label: 'Research', icon: FlaskConical },
  { href: '/analytics', label: 'Analytics', icon: BarChart3 },
  { href: '/benchmark', label: 'Benchmark', icon: Trophy },
  { href: '/radar', label: 'Radar', icon: Radar },
  { href: '/content-gen', label: 'Content', icon: FileVideo },
  { href: '/settings', label: 'Settings', icon: Settings },
]

function isActive(pathname: string, href: string): boolean {
  if (href === '/') {
    return pathname === '/'
  }

  return pathname === href || pathname.startsWith(`${href}/`)
}

function isNavItemActive(pathname: string, item: NavBarItem): boolean {
  if (item.match) {
    return item.match(pathname)
  }

  return isActive(pathname, item.href)
}

function getActiveItem(pathname: string, items: NavBarItem[]) {
  return items.find((item) => isNavItemActive(pathname, item)) ?? items[0] ?? null
}

function openCommandPalette() {
  window.dispatchEvent(new Event(COMMAND_PALETTE_OPEN_EVENT))
}

function NavMenuLink({
  item,
  pathname,
  onNavigate,
}: {
  item: NavBarItem
  pathname: string
  onNavigate: () => void
}) {
  const active = isNavItemActive(pathname, item)
  const Icon = item.icon

  return (
    <Link
      href={item.href}
      aria-current={active ? 'page' : undefined}
      onClick={onNavigate}
      className={cn(
        'flex min-h-11 items-center justify-between gap-4 rounded-md px-3 text-sm transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/45',
        active
          ? 'bg-primary/12 text-foreground'
          : 'text-muted-foreground hover:bg-surface-raised/70 hover:text-foreground',
      )}
    >
      <span className="flex min-w-0 items-center gap-3">
        <Icon
          className={cn('h-4 w-4 shrink-0', active ? 'text-primary' : 'text-muted-foreground')}
        />
        <span className="truncate font-medium">{item.label}</span>
      </span>
      {active ? <span className="h-1.5 w-1.5 rounded-full bg-primary" /> : null}
    </Link>
  )
}

export function CommandTrigger({
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
        'inline-flex items-center rounded-md border border-border/70 bg-background text-sm text-muted-foreground transition-colors hover:border-border hover:bg-surface-raised/70 hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/45 motion-reduce:transition-none',
        compact ? 'h-10 w-10 justify-center' : 'h-10 min-w-[11rem] justify-between gap-3 px-3',
        className,
      )}
      aria-label="Open command palette"
    >
      <span className="flex items-center gap-2">
        <Search className="h-4 w-4" />
        {!compact ? <span>Search</span> : null}
      </span>
      {!compact ? (
        <span className="flex items-center gap-1 text-[0.65rem] uppercase tracking-[0.14em] text-muted-foreground">
          <kbd className="rounded border border-border/60 bg-surface px-1.5 py-0.5 font-mono text-[0.68rem] text-foreground">
            ⌘
          </kbd>
          <kbd className="rounded border border-border/60 bg-surface px-1.5 py-0.5 font-mono text-[0.68rem] text-foreground">
            K
          </kbd>
        </span>
      ) : null}
    </button>
  )
}

export function NavBarBrand({
  href = '/',
  title = 'CC Deep Research',
  subtitle = 'Operations Console',
  icon: Icon = FlaskConical,
  className,
}: {
  href?: string
  title?: string
  subtitle?: string
  icon?: LucideIcon
  className?: string
}) {
  return (
    <Link
      href={href}
      className={cn(
        'flex min-w-0 shrink-0 items-center gap-2 rounded-md px-1 py-1 text-left transition-colors hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/45',
        className,
      )}
    >
      <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md border border-border/70 bg-surface">
        <Icon className="h-4 w-4 text-primary" />
      </span>
      <span className="min-w-0">
        <span className="block whitespace-nowrap font-display text-[0.98rem] font-semibold leading-none text-foreground">
          {title}
        </span>
        <span className="mt-1 hidden truncate text-[0.66rem] uppercase tracking-[0.16em] text-muted-foreground sm:block">
          {subtitle}
        </span>
      </span>
    </Link>
  )
}

export interface NavBarProps {
  className?: string
  items?: NavBarItem[]
  pathname?: string
  leadingSlot?: ReactNode
  utilitySlot?: ReactNode
  actionSlot?: ReactNode
  navLabel?: string
  showCommandTrigger?: boolean
}

export function NavBar({
  className,
  items = defaultNavItems,
  pathname: pathnameProp,
  leadingSlot,
  utilitySlot,
  actionSlot,
  navLabel = 'Primary navigation',
  showCommandTrigger = false,
}: NavBarProps) {
  const currentPathname = usePathname()
  const pathname = pathnameProp ?? currentPathname
  const menuId = useId()
  const containerRef = useRef<HTMLDivElement>(null)
  const [menuOpen, setMenuOpen] = useState(false)
  const activeItem = getActiveItem(pathname, items)
  const hasItems = items.length > 0 && activeItem !== null

  useEffect(() => {
    setMenuOpen(false)
  }, [pathname])

  useEffect(() => {
    if (!menuOpen) {
      return
    }

    const handlePointerDown = (event: MouseEvent) => {
      const target = event.target
      if (target instanceof Node && !containerRef.current?.contains(target)) {
        setMenuOpen(false)
      }
    }

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setMenuOpen(false)
      }
    }

    window.addEventListener('mousedown', handlePointerDown)
    window.addEventListener('keydown', handleKeyDown)

    return () => {
      window.removeEventListener('mousedown', handlePointerDown)
      window.removeEventListener('keydown', handleKeyDown)
    }
  }, [menuOpen])

  return (
    <div className={className}>
      <div className="flex min-h-14 items-center justify-between gap-3 py-1.5">
        <div className="flex min-w-0 items-center gap-2 sm:gap-3">
          {leadingSlot}
          {hasItems && activeItem ? (
            <div ref={containerRef} className="relative">
              <button
                type="button"
                aria-expanded={menuOpen}
                aria-controls={menuId}
                aria-label={menuOpen ? 'Close main navigation' : 'Open main navigation'}
                onClick={() => setMenuOpen((open) => !open)}
                className={cn(
                  'inline-flex h-10 items-center gap-2 rounded-md border px-3 text-sm transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/45',
                  menuOpen
                    ? 'border-primary/35 bg-primary/12 text-foreground'
                    : 'border-border/70 bg-background text-muted-foreground hover:border-border hover:bg-surface-raised/70 hover:text-foreground',
                )}
              >
                {menuOpen ? <X className="h-4 w-4" /> : <Menu className="h-4 w-4" />}
                <span className="hidden sm:inline">Menu</span>
                <span className="max-w-[7rem] truncate text-foreground sm:max-w-[9rem]">
                  {activeItem.label}
                </span>
              </button>

              <div
                id={menuId}
                className={cn(
                  'fixed left-4 top-14 z-[100] mt-2 w-[min(18rem,calc(100vw-2rem))] origin-top-left transition-transform duration-150 motion-reduce:transition-none sm:absolute sm:left-0 sm:top-full sm:z-[90]',
                  menuOpen
                    ? 'translate-y-0 opacity-100'
                    : 'pointer-events-none translate-y-1 opacity-0',
                )}
              >
                <nav
                  aria-label={navLabel}
                  className="relative z-[100] rounded-lg border border-border bg-background p-1.5 shadow-2xl sm:z-[90]"
                >
                  {items.map((item) => (
                    <NavMenuLink
                      key={item.href}
                      item={item}
                      pathname={pathname}
                      onNavigate={() => setMenuOpen(false)}
                    />
                  ))}
                </nav>
              </div>
            </div>
          ) : null}
        </div>

        <div className="flex min-w-0 items-center gap-2">
          {utilitySlot}
          {actionSlot}
          {showCommandTrigger ? <CommandTrigger className="hidden md:inline-flex" /> : null}
          {showCommandTrigger ? <CommandTrigger compact className="md:hidden" /> : null}
        </div>
      </div>
    </div>
  )
}

export { defaultNavItems as navItems, isActive, isNavItemActive }
