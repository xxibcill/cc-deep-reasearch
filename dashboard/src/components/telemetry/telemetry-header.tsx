import { Activity, GitBranch, List, Network } from 'lucide-react';

import { Badge } from '@/components/ui/badge';
import { Tabs } from '@/components/ui/tabs';
import type { LiveStreamStatus, ViewMode } from '@/types/telemetry';

export function getStatusBadgeMeta(
  liveStreamStatus: LiveStreamStatus,
  eventCount: number
): {
  label: string;
  variant: 'default' | 'secondary' | 'success' | 'warning' | 'destructive' | 'outline' | 'info';
} {
  switch (liveStreamStatus.phase) {
    case 'live':
      return { label: 'Live', variant: 'info' };
    case 'connecting':
      return { label: 'Connecting', variant: 'secondary' };
    case 'reconnecting':
      return { label: 'Reconnecting', variant: 'warning' };
    case 'historical':
      return { label: 'Historical', variant: 'secondary' };
    case 'failed':
      return { label: eventCount > 0 ? 'Disconnected' : 'Offline', variant: 'destructive' };
    default:
      return { label: eventCount > 0 ? 'Snapshot' : 'Offline', variant: 'secondary' };
  }
}

export function StatusBadge({
  liveStreamStatus,
  eventCount,
}: {
  liveStreamStatus: LiveStreamStatus;
  eventCount: number;
}) {
  const badge = getStatusBadgeMeta(liveStreamStatus, eventCount);
  return <Badge variant={badge.variant}>{badge.label}</Badge>;
}

export function ViewModeSelector({
  currentMode,
  onViewModeChange,
}: {
  currentMode: ViewMode;
  onViewModeChange: (mode: ViewMode) => void;
}) {
  const buttons: Array<{ mode: ViewMode; title: string; icon: typeof Network }> = [
    { mode: 'graph', title: 'Workflow Graph', icon: Network },
    { mode: 'decision_graph', title: 'Decision Graph', icon: GitBranch },
    { mode: 'timeline', title: 'Agent Timeline', icon: Activity },
    { mode: 'table', title: 'Event Table', icon: List },
  ];

  return (
    <Tabs
      className="max-w-full"
      onValueChange={(value) => onViewModeChange(value as ViewMode)}
      tabs={buttons.map(({ mode, title, icon }) => ({
        value: mode,
        label: title,
        icon,
      }))}
      value={currentMode}
    />
  );
}
