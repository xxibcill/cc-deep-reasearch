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
          ? 'gap-2 rounded-2xl border border-border bg-surface p-2 shadow-sm'
          : 'gap-0.5 rounded-lg border bg-muted/40 p-1',
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
                ? 'flex min-w-0 flex-col items-start gap-1 rounded-xl border px-3 py-3 text-left transition-all'
                : 'flex items-center gap-2 rounded-md px-3 py-1.5 text-sm font-medium transition-colors',
              isIconOnly && isProminent ? 'items-center justify-center px-0 py-3' : undefined,
              value === tab.value
                ? isProminent
                  ? 'border-primary/35 bg-surface-raised text-foreground shadow-sm'
                  : 'bg-background shadow-sm'
                : isProminent
                  ? 'border-transparent text-muted-foreground hover:border-border hover:bg-surface-raised hover:text-foreground'
                  : 'text-muted-foreground hover:text-foreground'
            )}
            aria-label={tab.label}
            aria-pressed={value === tab.value}
            onClick={() => onValueChange(tab.value)}
            title={tab.label}
            type="button"
          >
            {Icon ? (
              <Icon className={cn('h-4 w-4', isIconOnly ? 'h-[18px] w-[18px]' : undefined)} />
            ) : null}
            {!tab.hideLabel && (
              <span className={cn('truncate', isProminent ? 'text-sm font-semibold' : undefined)}>
                {tab.label}
              </span>
            )}
            {!tab.hideLabel && tab.badge !== undefined && (
              <span
                className={cn(
                  'rounded-full px-2 py-0.5 text-[11px] font-semibold',
                  value === tab.value
                    ? isProminent
                      ? 'bg-primary/15 text-primary'
                      : 'bg-muted text-foreground'
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
