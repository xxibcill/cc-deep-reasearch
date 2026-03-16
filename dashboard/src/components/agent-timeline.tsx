'use client';

import { AgentExecution, TelemetryEvent } from '@/types/telemetry';

const STATUS_CLASS: Record<string, string> = {
  completed: 'bg-emerald-500',
  success: 'bg-emerald-500',
  running: 'bg-blue-500',
  started: 'bg-blue-500',
  failed: 'bg-rose-500',
  error: 'bg-rose-500',
  timeout: 'bg-amber-500',
  unknown: 'bg-slate-400',
};

function percent(value: number, min: number, max: number): number {
  if (max <= min) {
    return 0;
  }
  return ((value - min) / (max - min)) * 100;
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

        return (
          <div key={lane.id} className="rounded-xl border bg-card p-4">
            <div className="mb-3 flex items-center justify-between gap-4">
              <div>
                <div className="text-sm font-semibold">{lane.agentName}</div>
                <div className="text-xs text-muted-foreground">
                  {lane.phase ?? 'No phase'} • {lane.duration} ms
                </div>
              </div>
              <button
                className="text-xs font-medium text-blue-700 hover:underline"
                onClick={() => onSelectEvent(representativeEvent ? eventIndex.get(representativeEvent) ?? null : null)}
                type="button"
              >
                Inspect lane
              </button>
            </div>
            <div className="relative h-16 rounded-lg bg-slate-100">
              <div
                className={`absolute top-5 h-6 rounded-full ${STATUS_CLASS[lane.status] ?? STATUS_CLASS.unknown}`}
                style={{ left: `${laneStart}%`, width: `${width}%` }}
              />
              {lane.markers.map((marker) => (
                <button
                  key={marker.id}
                  className="absolute top-2 h-12 -translate-x-1/2"
                  onClick={() => onSelectEvent(eventIndex.get(marker.eventId) ?? null)}
                  style={{ left: `${percent(marker.timestamp, minStart, maxEnd)}%` }}
                  type="button"
                >
                  <span className="block h-3 w-3 rounded-full bg-slate-900" />
                  <span className="mt-1 block max-w-[7rem] truncate text-[10px] text-slate-600">{marker.label}</span>
                </button>
              ))}
            </div>
          </div>
        );
      })}
    </div>
  );
}
