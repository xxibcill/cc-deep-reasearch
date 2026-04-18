'use client'

import { useEffect, useId, useState, type CSSProperties, type ReactNode } from 'react'
import Link from 'next/link'
import { usePathname } from 'next/navigation'
import {
  BarChart3,
  ChevronRight,
  ChevronsRight,
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

function getItemTransitionStyle(open: boolean, index: number): CSSProperties {
  return {
    transitionDelay: open ? `${index * 36}ms` : '0ms',
  }
}

function NavLinkCard({
  item,
  pathname,
  onNavigate,
  expanded = false,
  orientation = 'desktop',
  index = 0,
}: {
  item: NavBarItem
  pathname: string
  onNavigate?: () => void
  expanded?: boolean
  orientation?: 'desktop' | 'mobile'
  index?: number
}) {
  const active = isNavItemActive(pathname, item)
  const Icon = item.icon
  const isMobile = orientation === 'mobile'

  return (
    <Link
      href={item.href}
      aria-current={active ? 'page' : undefined}
      onClick={onNavigate}
      style={!isMobile ? getItemTransitionStyle(expanded, index) : undefined}
      className={cn(
        'group relative overflow-hidden rounded-[1rem] border transition-[transform,opacity,border-color,background-color,color,box-shadow] duration-200 ease-[cubic-bezier(0.22,1,0.36,1)] motion-reduce:transform-none motion-reduce:transition-none',
        isMobile
          ? 'flex items-center justify-between gap-3 px-3.5 py-3.5'
          : 'flex min-w-[13rem] flex-1 items-center justify-between gap-3 px-3.5 py-3',
        expanded || isMobile ? 'translate-y-0 opacity-100' : 'translate-y-1 opacity-0',
        active
          ? 'border-primary/35 bg-[linear-gradient(135deg,hsl(var(--primary)/0.18),hsl(var(--surface-raised)/0.88))] text-foreground shadow-[0_14px_30px_hsl(190_45%_4%/0.26),inset_0_1px_0_hsl(var(--foreground)/0.06)]'
          : 'border-border/65 bg-surface/72 text-muted-foreground hover:-translate-y-0.5 hover:border-primary/24 hover:bg-surface-raised/88 hover:text-foreground hover:shadow-[0_16px_30px_hsl(190_45%_4%/0.22)]',
      )}
    >
      <span
        className={cn(
          'pointer-events-none absolute inset-0 bg-[linear-gradient(110deg,transparent_15%,hsl(var(--foreground)/0.07)_48%,transparent_76%)] transition-transform duration-500 ease-[cubic-bezier(0.22,1,0.36,1)] motion-reduce:transition-none',
          active ? 'translate-x-0' : '-translate-x-full group-hover:translate-x-full',
        )}
      />
      <span className="relative flex min-w-0 items-center gap-3">
        <span
          className={cn(
            'flex h-10 w-10 shrink-0 items-center justify-center rounded-[0.95rem] border transition-colors duration-200',
            active
              ? 'border-primary/30 bg-primary/16 text-primary'
              : 'border-border/70 bg-background/55 text-muted-foreground group-hover:border-primary/24 group-hover:text-foreground',
          )}
        >
          <Icon className="h-4.5 w-4.5" />
        </span>
        <span className="min-w-0">
          <span className="block truncate text-sm font-medium text-foreground">{item.label}</span>
          <span className="mt-0.5 block truncate text-[0.68rem] uppercase tracking-[0.18em] text-muted-foreground">
            {active ? 'Current view' : 'Open section'}
          </span>
        </span>
      </span>
      <span className="relative flex shrink-0 items-center gap-2">
        {active ? (
          <span className="inline-flex h-2.5 w-2.5 rounded-full bg-primary shadow-[0_0_0_6px_hsl(var(--primary)/0.16)]" />
        ) : null}
        <ChevronRight
          className={cn(
            'h-4 w-4 text-muted-foreground transition-transform duration-200 motion-reduce:transition-none',
            active ? 'text-primary' : 'group-hover:translate-x-0.5 group-hover:text-foreground',
          )}
        />
      </span>
    </Link>
  )
}

function DesktopExpandableNav({
  items,
  pathname,
  navLabel,
  open,
  onOpenChange,
}: {
  items: NavBarItem[]
  pathname: string
  navLabel: string
  open: boolean
  onOpenChange: (open: boolean) => void
}) {
  const panelId = useId()
  const activeItem = getActiveItem(pathname, items)

  if (!activeItem) {
    return null
  }

  const ActiveIcon = activeItem.icon

  return (
    <div
      className="relative hidden lg:block"
      onMouseEnter={() => onOpenChange(true)}
      onMouseLeave={() => onOpenChange(false)}
      onFocusCapture={() => onOpenChange(true)}
      onBlurCapture={(event) => {
        const nextTarget = event.relatedTarget
        if (!(nextTarget instanceof Node) || !event.currentTarget.contains(nextTarget)) {
          onOpenChange(false)
        }
      }}
      onKeyDown={(event) => {
        if (event.key === 'Escape') {
          onOpenChange(false)
        }
      }}
    >
      <button
        type="button"
        aria-expanded={open}
        aria-controls={panelId}
        onClick={() => onOpenChange(!open)}
        className={cn(
          'group inline-flex h-12 items-center gap-3 rounded-[1.15rem] border px-3.5 text-left transition-[border-color,background-color,box-shadow,transform] duration-200 ease-[cubic-bezier(0.22,1,0.36,1)] motion-reduce:transform-none motion-reduce:transition-none',
          open
            ? 'border-primary/30 bg-surface-raised/88 shadow-[0_20px_40px_hsl(190_46%_3%/0.24),inset_0_1px_0_hsl(var(--foreground)/0.06)]'
            : 'border-border/70 bg-surface/68 hover:border-primary/28 hover:bg-surface-raised/82 hover:shadow-[0_14px_30px_hsl(190_46%_3%/0.16)]',
        )}
      >
        <span className="flex min-w-0 items-center gap-3">
          <span
            className={cn(
              'flex h-9 w-9 shrink-0 items-center justify-center rounded-[0.9rem] border border-primary/20 bg-primary/14 text-primary transition-transform duration-200 motion-reduce:transition-none',
              open && 'scale-[1.03]',
            )}
          >
            <ActiveIcon className="h-4.5 w-4.5" />
          </span>
          <span className="min-w-0">
            <span className="block text-[0.66rem] uppercase tracking-[0.2em] text-muted-foreground">
              Current page
            </span>
            <span className="mt-0.5 block truncate text-sm font-medium text-foreground">
              {activeItem.label}
            </span>
          </span>
        </span>
        <span className="flex shrink-0 items-center gap-2 pl-1 text-[0.68rem] uppercase tracking-[0.18em] text-muted-foreground">
          <span className="hidden xl:inline">{items.length} sections</span>
          <ChevronsRight
            className={cn(
              'h-4 w-4 transition-transform duration-200 motion-reduce:transition-none',
              open ? 'translate-x-0.5 text-primary' : 'group-hover:translate-x-0.5',
            )}
          />
        </span>
      </button>

      <div
        id={panelId}
        className={cn(
          'pointer-events-none absolute left-0 top-full z-[70] w-[min(42rem,calc(100vw-6rem))] origin-top-left pt-3 transition-all duration-200 ease-[cubic-bezier(0.22,1,0.36,1)] motion-reduce:transition-none',
          open ? 'translate-y-0 opacity-100' : 'translate-y-1.5 opacity-0',
        )}
      >
        <div
          className={cn(
            'panel-shell overflow-hidden rounded-[1.35rem] border border-border/70 bg-popover/94 backdrop-blur-xl',
            open ? 'pointer-events-auto' : 'pointer-events-none',
          )}
        >
          <div className="flex items-center justify-between gap-4 border-b border-border/60 px-4 py-3">
            <div className="min-w-0">
              <div className="text-[0.66rem] uppercase tracking-[0.2em] text-muted-foreground">
                Navigation
              </div>
              <div className="mt-1 text-sm text-foreground">
                Jump across sections without keeping the full nav mounted in the header.
              </div>
            </div>
            <span className="hidden items-center gap-2 rounded-full border border-primary/18 bg-primary/10 px-2.5 py-1 text-[0.66rem] uppercase tracking-[0.18em] text-primary xl:inline-flex">
              <span className="h-1.5 w-1.5 rounded-full bg-primary shadow-[0_0_0_4px_hsl(var(--primary)/0.14)]" />
              Hover reveal
            </span>
          </div>

          <nav
            aria-label={navLabel}
            className="flex flex-wrap gap-2 p-2"
          >
            {items.map((item, index) => (
              <NavLinkCard
                key={item.href}
                item={item}
                pathname={pathname}
                expanded={open}
                index={index}
              />
            ))}
          </nav>
        </div>
      </div>
    </div>
  )
}

function MobileNavLinks({
  items,
  pathname,
  onNavigate,
}: {
  items: NavBarItem[]
  pathname: string
  onNavigate: () => void
}) {
  return (
    <nav aria-label="Primary mobile" className="flex flex-col gap-2">
      {items.map((item, index) => (
        <NavLinkCard
          key={item.href}
          item={item}
          pathname={pathname}
          onNavigate={onNavigate}
          orientation="mobile"
          expanded
          index={index}
        />
      ))}
    </nav>
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
        'inline-flex items-center rounded-[0.9rem] border border-border/70 bg-surface/62 text-sm text-muted-foreground transition-all duration-200 hover:border-primary/35 hover:bg-surface-raised/78 hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/45 motion-reduce:transition-none',
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
        'flex min-w-0 items-center gap-3 rounded-[0.95rem] px-1 py-1 text-left transition-colors hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/45',
        className,
      )}
    >
      <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-[0.95rem] border border-border/70 bg-[linear-gradient(180deg,hsl(var(--surface-raised)),hsl(var(--surface)))] shadow-[inset_0_1px_0_rgba(255,255,255,0.04)]">
        <Icon className="h-4.5 w-4.5 text-primary" />
      </span>
      <span className="min-w-0">
        <span className="block truncate font-display text-[1.02rem] font-semibold leading-none text-foreground">
          {title}
        </span>
        <span className="mt-1 block truncate text-[0.68rem] uppercase tracking-[0.18em] text-muted-foreground">
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
  const [mobileOpen, setMobileOpen] = useState(false)
  const [desktopOpen, setDesktopOpen] = useState(false)
  const activeItem = getActiveItem(pathname, items)
  const hasItems = items.length > 0 && activeItem !== null
  const ActiveItemIcon = activeItem?.icon

  useEffect(() => {
    setMobileOpen(false)
    setDesktopOpen(false)
  }, [pathname])

  return (
    <div className={className}>
      <div className="flex min-h-16 items-center justify-between gap-4 py-1">
        <div className="flex min-w-0 items-center gap-3 lg:gap-5">
          {leadingSlot}
          {hasItems ? (
            <DesktopExpandableNav
              items={items}
              pathname={pathname}
              navLabel={navLabel}
              open={desktopOpen}
              onOpenChange={setDesktopOpen}
            />
          ) : null}
        </div>

        <div className="flex items-center gap-2">
          {utilitySlot}
          {actionSlot}
          {showCommandTrigger ? <CommandTrigger className="hidden md:inline-flex" /> : null}
          {showCommandTrigger ? <CommandTrigger compact className="md:hidden" /> : null}
          {hasItems && ActiveItemIcon !== undefined && activeItem ? (
            <button
              type="button"
              className="inline-flex h-10 items-center gap-2 rounded-[0.95rem] border border-border/70 bg-surface/62 px-3 text-muted-foreground transition-all duration-200 hover:border-primary/35 hover:bg-surface-raised/78 hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/45 motion-reduce:transition-none lg:hidden"
              aria-expanded={mobileOpen}
              aria-controls={menuId}
              aria-label={mobileOpen ? 'Close navigation menu' : 'Open navigation menu'}
              onClick={() => setMobileOpen((open) => !open)}
            >
              <span className="flex min-w-0 items-center gap-2">
                <ActiveItemIcon className="h-4 w-4 shrink-0 text-primary" />
                <span className="max-w-[8.5rem] truncate text-sm text-foreground">
                  {activeItem.label}
                </span>
              </span>
              {mobileOpen ? <X className="h-4.5 w-4.5" /> : <Menu className="h-4.5 w-4.5" />}
            </button>
          ) : null}
        </div>
      </div>

      {hasItems && ActiveItemIcon !== undefined && activeItem ? (
        <div
          id={menuId}
          className={cn(
            'grid overflow-hidden transition-[grid-template-rows,opacity] duration-200 ease-[cubic-bezier(0.22,1,0.36,1)] motion-reduce:transition-none lg:hidden',
            mobileOpen ? 'grid-rows-[1fr] opacity-100' : 'grid-rows-[0fr] opacity-0',
          )}
        >
          <div className="overflow-hidden">
            <div className="border-t border-border/60 pb-3 pt-3">
              <div className="mb-3 flex items-center gap-3 rounded-[1rem] border border-primary/20 bg-primary/10 px-3.5 py-3">
                <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-[0.95rem] border border-primary/20 bg-primary/16 text-primary">
                  <ActiveItemIcon className="h-4.5 w-4.5" />
                </span>
                <div className="min-w-0">
                  <div className="text-[0.66rem] uppercase tracking-[0.18em] text-muted-foreground">
                    Current page
                  </div>
                  <div className="truncate text-sm font-medium text-foreground">
                    {activeItem.label}
                  </div>
                </div>
              </div>
              <MobileNavLinks
                items={items}
                pathname={pathname}
                onNavigate={() => setMobileOpen(false)}
              />
              {showCommandTrigger ? (
                <CommandTrigger className="mt-3 w-full justify-between md:hidden" />
              ) : null}
            </div>
          </div>
        </div>
      ) : null}
    </div>
  )
}

export { defaultNavItems as navItems, isActive, isNavItemActive }
