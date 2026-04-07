import { useEffect, useId, useRef } from 'react';

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
  const fallbackId = useId();
  const selectId = testId ? `${testId}-input` : fallbackId;
  const selectRef = useRef<HTMLSelectElement | null>(null);
  const handleValueChange = (value: string) => {
    onChange(value);
  };

  useEffect(() => {
    const element = selectRef.current;
    if (!element) {
      return;
    }

    const syncValue = () => {
      handleValueChange(element.value);
    };

    element.addEventListener('change', syncValue);
    element.addEventListener('input', syncValue);
    return () => {
      element.removeEventListener('change', syncValue);
      element.removeEventListener('input', syncValue);
    };
  }, [onChange]);

  return (
    <div
      className={cn(
        'flex min-w-[10rem] flex-col gap-1.5 text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground',
        labelClassName
      )}
    >
      <label htmlFor={selectId}>
        {label}
      </label>
      <select
        id={selectId}
        className={cn(
          'h-11 rounded-[0.95rem] border border-input/90 bg-surface/72 px-3.5 text-sm text-foreground transition-all focus:border-primary/55 focus:bg-surface-raised',
          className
        )}
        data-testid={testId}
        ref={selectRef}
        onChange={(event) => handleValueChange(event.target.value)}
        onInput={(event) => handleValueChange((event.target as HTMLSelectElement).value)}
        value={value}
      >
        <option value="">{emptyLabel}</option>
        {options.map((option) => (
          <option key={option} value={option}>
            {option}
          </option>
        ))}
      </select>
    </div>
  );
}
