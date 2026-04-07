'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { Activity, FlaskConical, Settings, FileVideo, Trophy } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { NotificationProvider } from '@/components/ui/notification-center';
import { CommandPalette, KeyboardHint } from '@/components/command-palette';
import { cn } from '@/lib/utils';

const navItems = [
  { href: '/', label: 'Research', icon: FlaskConical },
  { href: '/benchmark', label: 'Benchmark', icon: Trophy },
  { href: '/content-gen', label: 'Content Studio', icon: FileVideo },
  { href: '/settings', label: 'Settings', icon: Settings },
];

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const activeItem =
    navItems.find((item) => (item.href === '/' ? pathname === '/' : pathname.startsWith(item.href))) ??
    navItems[0];

  const isActive = (href: string) => {
    if (href === '/') return pathname === '/';
    return pathname.startsWith(href);
  };

  return (
    <NotificationProvider>
      <>
        <CommandPalette />
        <KeyboardHint />
        <header className="sticky top-0 z-50 border-b border-border/70 bg-background/82 backdrop-blur-xl">
          <div className="mx-auto max-w-content px-page-x">
            <div className="flex flex-col gap-4 py-4 lg:flex-row lg:items-end lg:justify-between">
              <div className="min-w-0">
                <Link href="/" className="inline-flex flex-col gap-1 text-foreground transition-opacity hover:opacity-90">
                  <span className="eyebrow">Multi-agent research observatory</span>
                  <span className="font-display text-[2.4rem] font-semibold uppercase tracking-[0.02em]">
                    CC Deep Research
                  </span>
                </Link>
                <div className="mt-3 flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
                  <Badge variant="outline" className="text-[0.64rem]">
                    {activeItem.label}
                  </Badge>
                  <span>Operational visibility for research runs, telemetry, and publishing pipelines.</span>
                </div>
              </div>

              <div className="flex flex-col gap-3 lg:items-end">
                <div className="flex items-center gap-2 rounded-full border border-border/70 bg-surface/75 px-3 py-1.5 text-[0.72rem] text-muted-foreground shadow-card">
                  <Activity className="h-3.5 w-3.5 text-primary" />
                  Workspace online
                </div>
                <nav
                  aria-label="Primary"
                  className="grid gap-2 rounded-[1.2rem] border border-border/70 bg-surface/70 p-2 sm:grid-cols-4"
                >
                  {navItems.map(({ href, label, icon: Icon }) => {
                    const active = isActive(href);
                    return (
                      <Link
                        key={href}
                        href={href}
                        className={cn(
                          'flex min-w-[9rem] items-center gap-3 rounded-[0.95rem] border px-3 py-3 transition-all',
                          active
                            ? 'border-primary/35 bg-card text-foreground shadow-[inset_0_1px_0_rgba(255,255,255,0.06)]'
                            : 'border-transparent text-muted-foreground hover:border-border/70 hover:bg-surface-raised/75 hover:text-foreground'
                        )}
                        aria-current={active ? 'page' : undefined}
                      >
                        <Icon className="h-4 w-4 shrink-0" />
                        <div className="min-w-0">
                          <p className="font-display text-[0.88rem] font-semibold uppercase tracking-[0.12em]">
                            {label}
                          </p>
                          <p className="truncate text-xs text-muted-foreground">
                            {href === '/' ? 'Sessions and live runs' : href === '/benchmark' ? 'Evaluation results' : href === '/content-gen' ? 'Production workflows' : 'Runtime controls'}
                          </p>
                        </div>
                      </Link>
                    );
                  })}
                </nav>
              </div>
            </div>
          </div>
        </header>
        {children}
      </>
    </NotificationProvider>
  );
}
