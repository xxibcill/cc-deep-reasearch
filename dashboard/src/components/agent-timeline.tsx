'use client';

import { AgentExecution, TelemetryEvent } from '@/types/telemetry';

const MAX_VISIBLE_MARKERS_PER_LANE = 18;

const STATUS_CLASS: Record<string, string> = {
  completed: 'bg-success',
  success: 'bg-success',
  running: 'bg-primary',
  started: 'bg-primary',
  failed: 'bg-error',
  error: 'bg-error',
  timeout: 'bg-warning',
  unknown: 'bg-muted-foreground',
};

function percent(value: number, min: number, max: number): number {
  if (max <= min) {
    return 0;
  }
  return ((value - min) / (max - min)) * 100;
}

function sampleMarkers(markers: AgentExecution['markers']) {
  if (markers.length <= MAX_VISIBLE_MARKERS_PER_LANE) {
    return {
      markers,
      hiddenCount: 0,
    };
  }

  const firstTimestamp = markers[0]?.timestamp ?? 0;
  const lastTimestamp = markers[markers.length - 1]?.timestamp ?? 0;
  const timeRange = lastTimestamp - firstTimestamp;

  // Always include first and last markers (key checkpoints)
  const selectedMarkers: typeof markers = [markers[0]];

  if (timeRange > 0) {
    const targetInteriorCount = MAX_VISIBLE_MARKERS_PER_LANE - 2;

    // Build sorted index array by timestamp for O(log n) closest lookups
    const sortedIndices = markers
      .map((marker, index) => ({ index, timestamp: marker.timestamp ?? 0 }))
      .sort((a, b) => a.timestamp - b.timestamp);

    for (let step = 1; step <= targetInteriorCount; step += 1) {
      const targetTimestamp = firstTimestamp + (step / (targetInteriorCount + 1)) * timeRange;

      // Binary search for closest timestamp
      let left = 0;
      let right = sortedIndices.length - 1;
      while (left < right) {
        const mid = Math.floor((left + right) / 2);
        if (sortedIndices[mid].timestamp < targetTimestamp) {
          left = mid + 1;
        } else {
          right = mid;
        }
      }

      // left is now the first index with timestamp >= targetTimestamp
      // Compare with left and left-1 to find closest
      let closestIdx: number;
      if (left === 0) {
        closestIdx = 0;
      } else if (left >= sortedIndices.length) {
        closestIdx = sortedIndices.length - 1;
      } else {
        const diffLeft = Math.abs(sortedIndices[left].timestamp - targetTimestamp);
        const diffPrev = Math.abs(sortedIndices[left - 1].timestamp - targetTimestamp);
        closestIdx = diffLeft < diffPrev ? left : left - 1;
      }

      const sortedIndex = sortedIndices[closestIdx].index;
      // Avoid duplicates and edge positions
      if (sortedIndex !== 0 && sortedIndex !== markers.length - 1) {
        selectedMarkers.push(markers[sortedIndex]);
      }
    }
  }

  selectedMarkers.push(markers[markers.length - 1]);

  return {
    markers: selectedMarkers,
    hiddenCount: markers.length - selectedMarkers.length,
  };
}

export function AgentTimeline({
  lanes,
  eventIndex,
  onSelectEvent,
}: {
  lanes: AgentExecution[];
  eventIndex: Map<string, TelemetryEvent>;
  onSelectEvent: (event: TelemetryEvent | null) => void;
}) {
  if (lanes.length === 0) {
    return <div className="rounded-xl border border-dashed p-8 text-sm text-muted-foreground">No agent activity matches the current filters.</div>;
  }

  const minStart = Math.min(...lanes.map((lane) => lane.startTime));
  const maxEnd = Math.max(...lanes.map((lane) => lane.endTime ?? lane.startTime));

  return (
    <div className="space-y-4">
      {lanes.map((lane) => {
        const laneStart = percent(lane.startTime, minStart, maxEnd);
        const laneEnd = percent(lane.endTime ?? lane.startTime, minStart, maxEnd);
        const width = Math.max(laneEnd - laneStart, 3);
        const representativeEvent = lane.eventIds.at(-1);
        const visibleMarkers = sampleMarkers(lane.markers);

        return (
          <div key={lane.id} className="rounded-xl border border-border/70 bg-surface/56 p-4">
            <div className="mb-3 flex items-center justify-between gap-4">
              <div>
                <div className="text-sm font-semibold">{lane.agentName}</div>
                <div className="text-xs text-muted-foreground">
                  {lane.phase ?? 'No phase'} • {lane.duration} ms
                </div>
              </div>
              <button
                className="text-xs font-medium text-primary hover:underline"
                onClick={() => onSelectEvent(representativeEvent ? eventIndex.get(representativeEvent) ?? null : null)}
                type="button"
              >
                Inspect lane
              </button>
            </div>
            {visibleMarkers.hiddenCount > 0 ? (
              <p className="mb-3 text-xs text-muted-foreground">
                Showing key checkpoints plus a sampled subset of markers for this dense lane.
              </p>
            ) : null}
            <div className="relative h-16 rounded-lg border border-border/60 bg-surface-raised/72">
              <div
                className={`absolute top-5 h-6 rounded-full ${STATUS_CLASS[lane.status] ?? STATUS_CLASS.unknown}`}
                style={{ left: `${laneStart}%`, width: `${width}%` }}
              />
              {visibleMarkers.markers.map((marker) => (
                <button
                  key={marker.id}
                  className="absolute top-2 h-12 -translate-x-1/2"
                  onClick={() => onSelectEvent(eventIndex.get(marker.eventId) ?? null)}
                  style={{ left: `${percent(marker.timestamp, minStart, maxEnd)}%` }}
                  type="button"
                >
                  <span className="block h-3 w-3 rounded-full bg-primary" />
                  <span className="mt-1 block max-w-[7rem] truncate text-[10px] text-muted-foreground">{marker.label}</span>
                </button>
              ))}
            </div>
          </div>
        );
      })}
    </div>
  );
}
