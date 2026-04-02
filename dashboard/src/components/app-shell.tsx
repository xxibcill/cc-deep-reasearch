'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { FlaskConical, Settings, FileVideo } from 'lucide-react';
import { cn } from '@/lib/utils';

const navItems = [
  { href: '/', label: 'Research', icon: FlaskConical },
  { href: '/content-gen', label: 'Content Studio', icon: FileVideo },
  { href: '/settings', label: 'Settings', icon: Settings },
];

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();

  const isActive = (href: string) => {
    if (href === '/') return pathname === '/';
    return pathname.startsWith(href);
  };

  return (
    <>
      <header className="sticky top-0 z-50 border-b bg-background/95 backdrop-blur-sm">
        <nav className="mx-auto flex h-11 max-w-content items-center gap-6 px-page-x">
          <Link
            href="/"
            className="font-display text-sm font-bold tracking-tight text-foreground"
          >
            CC Deep Research
          </Link>
          <ul className="flex items-center gap-1">
            {navItems.map(({ href, label, icon: Icon }) => {
              const active = isActive(href);
              return (
                <li key={href}>
                  <Link
                    href={href}
                    className={cn(
                      'inline-flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm font-medium transition-colors',
                      active
                        ? 'bg-secondary text-foreground'
                        : 'text-muted-foreground hover:bg-secondary/50 hover:text-foreground'
                    )}
                    aria-current={active ? 'page' : undefined}
                  >
                    <Icon className="h-3.5 w-3.5" />
                    {label}
                  </Link>
                </li>
              );
            })}
          </ul>
        </nav>
      </header>
      {children}
    </>
  );
}
