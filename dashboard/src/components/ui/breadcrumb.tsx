import Link from 'next/link';
import { ChevronRight } from 'lucide-react';

export interface BreadcrumbItem {
  label: string;
  href?: string;
}

export function Breadcrumb({ items }: { items: BreadcrumbItem[] }) {
  return (
    <nav
      aria-label="Breadcrumb"
      className="flex flex-wrap items-center gap-1 font-mono text-[0.72rem] uppercase tracking-[0.18em] text-muted-foreground"
    >
      {items.map((item, i) => (
        <span key={i} className="flex items-center gap-1">
          {i > 0 && <ChevronRight className="h-3 w-3" />}
          {item.href && i < items.length - 1 ? (
            <Link href={item.href} className="hover:text-foreground transition-colors">
              {item.label}
            </Link>
          ) : (
            <span aria-current={i === items.length - 1 ? 'page' : undefined}>
              {item.label}
            </span>
          )}
        </span>
      ))}
    </nav>
  );
}
