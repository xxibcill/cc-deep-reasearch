'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { FlaskConical, BarChart3, Trophy, FileVideo, Settings } from 'lucide-react';
import { cn } from '@/lib/utils';

const navItems = [
  { href: '/', label: 'Research', icon: FlaskConical },
  { href: '/analytics', label: 'Analytics', icon: BarChart3 },
  { href: '/benchmark', label: 'Benchmark', icon: Trophy },
  { href: '/content-gen', label: 'Content', icon: FileVideo },
  { href: '/settings', label: 'Settings', icon: Settings },
];

function isActive(pathname: string, href: string): boolean {
  if (href === '/') return pathname === '/';
  return pathname.startsWith(href);
}

export interface NavBarProps {
  className?: string;
}

export function NavBar({ className }: NavBarProps) {
  const pathname = usePathname();

  return (
    <nav aria-label="Primary" className={cn('flex items-center gap-6', className)}>
      {navItems.map(({ href, label, icon: Icon }) => {
        const active = isActive(pathname, href);
        return (
          <Link
            key={href}
            href={href}
            className={cn(
              'flex items-center gap-1.5 text-sm transition-colors',
              active ? 'text-foreground font-medium' : 'text-muted-foreground hover:text-foreground'
            )}
            aria-current={active ? 'page' : undefined}
          >
            <Icon className="h-3.5 w-3.5" />
            <span>{label}</span>
          </Link>
        );
      })}
    </nav>
  );
}

export { navItems, isActive };
