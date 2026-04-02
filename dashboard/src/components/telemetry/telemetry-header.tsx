import { Activity, GitBranch, List, Network } from 'lucide-react';

import { Badge } from '@/components/ui/badge';
import { Tabs } from '@/components/ui/tabs';
import type { ViewMode } from '@/types/telemetry';

export function StatusBadge({
  connected,
  eventCount,
}: {
  connected: boolean;
  eventCount: number;
}) {
  if (connected) {
    return <Badge variant="info">Live</Badge>;
  }

  if (eventCount > 0) {
    return <Badge variant="secondary">Snapshot</Badge>;
  }

  return <Badge variant="destructive">Offline</Badge>;
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
