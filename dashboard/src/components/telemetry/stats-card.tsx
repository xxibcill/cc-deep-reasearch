import { cn } from '@/lib/utils';
import { Card, CardContent } from '@/components/ui/card';

export function StatsCard({
  icon: Icon,
  label,
  value,
  accentClass,
  prominence = 'secondary',
}: {
  icon: typeof import('lucide-react').Activity;
  label: string;
  value: number;
  accentClass: string;
  prominence?: 'primary' | 'secondary';
}) {
  return (
    <Card className={cn(prominence === 'primary' && 'border-primary/20')}>
      <CardContent className="p-3">
        <div className="flex items-center gap-2">
          <Icon className={cn('h-4 w-4', accentClass)} />
          <span className="text-xs text-muted-foreground">{label}</span>
        </div>
        <div className={cn('mt-1 font-bold', prominence === 'primary' ? 'text-2xl' : 'text-xl')}>
          {value}
        </div>
      </CardContent>
    </Card>
  );
}
