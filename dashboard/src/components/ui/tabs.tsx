import { cn } from '@/lib/utils';

export function Tabs({
  value,
  onValueChange,
  tabs,
}: {
  value: string;
  onValueChange: (value: string) => void;
  tabs: Array<{ value: string; label: string }>;
}) {
  return (
    <div className="inline-flex rounded-lg border bg-muted/40 p-1">
      {tabs.map((tab) => (
        <button
          key={tab.value}
          className={cn(
            'rounded-md px-3 py-2 text-sm font-medium transition-colors',
            value === tab.value ? 'bg-background shadow-sm' : 'text-muted-foreground hover:text-foreground'
          )}
          onClick={() => onValueChange(tab.value)}
          type="button"
        >
          {tab.label}
        </button>
      ))}
    </div>
  );
}
