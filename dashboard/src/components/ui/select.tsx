import { cn } from '@/lib/utils';

export function Select({
  label,
  value,
  options,
  onChange,
  emptyLabel = 'All',
  testId,
  className,
  labelClassName,
}: {
  label: string;
  value: string;
  options: string[];
  onChange: (value: string) => void;
  emptyLabel?: string;
  testId?: string;
  className?: string;
  labelClassName?: string;
}) {
  return (
    <label
      className={cn(
        'flex min-w-[10rem] flex-col gap-1.5 text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground',
        labelClassName
      )}
    >
      {label}
      <select
        className={cn(
          'h-11 rounded-[0.95rem] border border-input/90 bg-surface/72 px-3.5 text-sm text-foreground transition-all focus:border-primary/55 focus:bg-surface-raised',
          className
        )}
        data-testid={testId}
        onChange={(event) => onChange(event.target.value)}
        value={value}
      >
        <option value="">{emptyLabel}</option>
        {options.map((option) => (
          <option key={option} value={option}>
            {option}
          </option>
        ))}
      </select>
    </label>
  );
}
