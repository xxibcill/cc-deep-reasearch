import type { ComponentType } from 'react';

import { cn } from '@/lib/utils';

type TabIcon = ComponentType<{ className?: string }>;

export function Tabs({
  value,
  onValueChange,
  tabs,
  variant = 'default',
  stretch = false,
  className,
}: {
  value: string;
  onValueChange: (value: string) => void;
  tabs: Array<{
    value: string;
    label: string;
    badge?: string | number;
    icon?: TabIcon;
    hideLabel?: boolean;
  }>;
  variant?: 'default' | 'prominent';
  stretch?: boolean;
  className?: string;
}) {
  const isProminent = variant === 'prominent';

  return (
    <div
      className={cn(
        stretch ? 'grid' : 'inline-flex',
        isProminent
          ? 'gap-2 rounded-[1.1rem] border border-border/80 bg-surface/80 p-2 shadow-card'
          : 'gap-1 rounded-[1rem] border border-border/70 bg-surface/65 p-1.5',
        className
      )}
      style={stretch ? { gridTemplateColumns: `repeat(${tabs.length}, minmax(0, 1fr))` } : undefined}
    >
      {tabs.map((tab) => {
        const Icon = tab.icon;
        const isIconOnly = Boolean(Icon && tab.hideLabel);

        return (
          <button
            key={tab.value}
            className={cn(
              isProminent
                ? 'flex min-w-0 flex-col items-start gap-1 rounded-[0.95rem] border px-3 py-3 text-left transition-all'
                : 'flex items-center gap-2 rounded-[0.8rem] px-3 py-2 text-[0.8rem] font-semibold uppercase tracking-[0.14em] transition-all',
              isIconOnly && isProminent ? 'items-center justify-center px-0 py-3' : undefined,
              value === tab.value
                ? isProminent
                  ? 'border-primary/50 bg-primary/20 text-foreground shadow-sm ring-1 ring-primary/20'
                  : 'bg-primary/25 text-foreground shadow-[inset_0_1px_0_rgba(255,255,255,0.06)] ring-1 ring-primary/30'
                : isProminent
                  ? 'border-transparent text-muted-foreground hover:border-border hover:bg-surface-raised hover:text-foreground'
                  : 'text-muted-foreground hover:bg-surface-raised/80 hover:text-foreground'
            )}
            aria-label={tab.label}
            aria-pressed={value === tab.value}
            onClick={() => onValueChange(tab.value)}
            title={tab.label}
            type="button"
          >
            {Icon ? (
              <Icon className={cn('h-4 w-4', isIconOnly ? 'h-[18px] w-[18px]' : undefined, value === tab.value && 'text-primary')} />
            ) : null}
            {!tab.hideLabel && (
              <span className={cn('truncate', isProminent ? 'text-sm font-semibold' : undefined, value === tab.value && 'text-primary')}>
                {tab.label}
              </span>
            )}
            {!tab.hideLabel && tab.badge !== undefined && (
              <span
                className={cn(
                  'rounded-md px-2 py-0.5 font-mono text-[0.68rem] uppercase tracking-[0.16em]',
                  value === tab.value
                    ? isProminent
                      ? 'bg-primary/30 text-primary'
                      : 'bg-primary/25 text-primary'
                    : 'bg-muted text-muted-foreground'
                )}
              >
                {tab.badge}
              </span>
            )}
          </button>
        );
      })}
    </div>
  );
}
