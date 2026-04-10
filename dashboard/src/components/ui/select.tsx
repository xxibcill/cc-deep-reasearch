import { cn } from '@/lib/utils';

export function Select({
  label,
  value,
  options,
  onChange,
  className,
  labelClassName,
  testId,
}: {
  label: string;
  value: string;
  options: string[];
  onChange: (value: string) => void;
  className?: string;
  labelClassName?: string;
  testId?: string;
}) {
  return (
    <label
      className={cn(
        'flex min-w-[10rem] flex-col gap-1 text-xs font-medium uppercase tracking-wide text-muted-foreground',
        labelClassName
      )}
    >
      {label}
      <select
        className={cn('h-10 rounded-md border bg-background px-3 text-sm text-foreground', className)}
        onChange={(event) => onChange(event.target.value)}
        value={value}
      >
        <option value="">All</option>
        {options.map((option) => (
          <option key={option} value={option}>
            {option}
          </option>
        ))}
      </select>
    </label>
  );
}
