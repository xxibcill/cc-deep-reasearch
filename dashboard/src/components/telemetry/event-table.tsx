import { useCallback, useMemo, useRef, useState } from 'react';

import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { ScrollArea } from '@/components/ui/scroll-area';
import { getStatusBadgeVariant } from '@/lib/utils';
import type { TelemetryEvent } from '@/types/telemetry';

function formatEventTime(timestamp: string): string {
  const date = new Date(timestamp);
  return Number.isNaN(date.getTime()) ? timestamp : date.toLocaleTimeString();
}

function statusAccent(status: string) {
  return getStatusBadgeVariant(status) as 'success' | 'warning' | 'destructive' | 'secondary' | 'default' | 'info';
}

export function EventTable({
  events,
  onSelectEvent,
}: {
  events: TelemetryEvent[];
  onSelectEvent: (event: TelemetryEvent) => void;
}) {
  const [scrollTop, setScrollTop] = useState(0);
  const rowHeight = 56;
  const viewportHeight = 520;
  const overscan = 10;
  const rafRef = useRef<number | null>(null);
  const handleScroll = useCallback((event: React.UIEvent<HTMLDivElement>) => {
    if (rafRef.current !== null) {
      return;
    }
    rafRef.current = requestAnimationFrame(() => {
      setScrollTop(event.currentTarget.scrollTop);
      rafRef.current = null;
    });
  }, []);
  const sortedEvents = useMemo(() => {
    return [...events].sort((left, right) => {
      const timestampOrder = right.timestamp.localeCompare(left.timestamp);
      if (timestampOrder !== 0) {
        return timestampOrder;
      }

      return right.sequenceNumber - left.sequenceNumber;
    });
  }, [events]);
  const totalHeight = sortedEvents.length * rowHeight;
  const startIndex = Math.max(Math.floor(scrollTop / rowHeight) - overscan, 0);
  const visibleCount = Math.ceil(viewportHeight / rowHeight) + overscan * 2;
  const visibleEvents = sortedEvents.slice(startIndex, startIndex + visibleCount);
  const columnTemplate =
    'minmax(120px,0.95fr) minmax(160px,1.2fr) minmax(110px,0.8fr) minmax(220px,1.35fr) minmax(120px,0.8fr) minmax(110px,0.7fr)';

  return (
    <Card className="overflow-hidden">
      <CardHeader className="border-b bg-muted/20">
        <div className="flex flex-col gap-2 md:flex-row md:items-start md:justify-between">
          <div className="space-y-1">
            <CardTitle>Event Table</CardTitle>
            <p className="text-sm text-muted-foreground">
              Virtualized event rows keep the full session log responsive while preserving click-to-inspect detail access.
            </p>
          </div>
          <Badge variant="outline">{sortedEvents.length} events</Badge>
        </div>
      </CardHeader>
      <CardContent className="p-0">
        <ScrollArea
          className="h-[520px]"
          onScroll={handleScroll}
        >
          <div className="min-w-[920px] text-sm">
            <div
              className="sticky top-0 z-10 grid border-b bg-card"
              style={{ gridTemplateColumns: columnTemplate }}
            >
              <div className="p-3 font-medium">Time</div>
              <div className="p-3 font-medium">Type</div>
              <div className="p-3 font-medium">Category</div>
              <div className="p-3 font-medium">Name</div>
              <div className="p-3 font-medium">Status</div>
              <div className="p-3 font-medium">Agent</div>
            </div>
            <div style={{ height: totalHeight, position: 'relative' }}>
              <div
                className="absolute inset-x-0"
                style={{ transform: `translateY(${startIndex * rowHeight}px)` }}
              >
                {visibleEvents.map((event) => (
                  <button
                    key={event.eventId}
                    onClick={() => onSelectEvent(event)}
                    className="grid w-full cursor-pointer border-b text-left hover:bg-accent"
                    style={{ gridTemplateColumns: columnTemplate, minHeight: rowHeight }}
                    type="button"
                  >
                    <div className="p-3">{formatEventTime(event.timestamp)}</div>
                    <div className="p-3 font-mono text-xs">{event.eventType}</div>
                    <div className="p-3">{event.category}</div>
                    <div className="p-3">{event.name}</div>
                    <div className="p-3">
                      <Badge variant={statusAccent(event.status)}>
                        {event.status}
                      </Badge>
                    </div>
                    <div className="p-3">{event.agentId || '-'}</div>
                  </button>
                ))}
              </div>
            </div>
          </div>
        </ScrollArea>
      </CardContent>
    </Card>
  );
}
