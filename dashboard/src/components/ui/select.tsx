import { cn } from '@/lib/utils';

export function Select({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: string;
  options: string[];
  onChange: (value: string) => void;
}) {
  return (
    <label className="flex min-w-[10rem] flex-col gap-1 text-xs font-medium uppercase tracking-wide text-muted-foreground">
      {label}
      <select
        className={cn('h-10 rounded-md border bg-background px-3 text-sm text-foreground')}
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
