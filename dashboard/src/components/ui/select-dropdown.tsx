import * as React from 'react';

import { cn } from '@/lib/utils';

export function Select({
  value,
  onValueChange,
  children,
  className,
}: {
  value?: string;
  onValueChange?: (value: string) => void;
  children?: React.ReactNode;
  className?: string;
}) {
  const handleChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    if (onValueChange) {
      onValueChange(e.target.value);
    }
  };

  return (
    <select
      className={cn(
        'flex h-7 rounded-md border border-input/90 bg-surface/72 px-2 py-1 text-xs text-foreground transition-all focus:border-primary/55 focus:bg-surface-raised focus:outline-none',
        className,
      )}
      value={value}
      onChange={handleChange}
    >
      {children}
    </select>
  );
}

export function SelectTrigger({
  children,
  className,
}: {
  children?: React.ReactNode;
  className?: string;
}) {
  return <span className={cn('flex items-center gap-1', className)}>{children}</span>;
}

export function SelectValue({
  placeholder,
}: {
  placeholder?: string;
}) {
  return <span className="text-muted-foreground">{placeholder}</span>;
}

export function SelectContent({
  children,
}: {
  children?: React.ReactNode;
}) {
  return <>{React.Children.toArray(children)}</>;
}

export function SelectItem({
  value,
  children,
}: {
  value?: string;
  children?: React.ReactNode;
}) {
  return <option value={value}>{children}</option>;
}
