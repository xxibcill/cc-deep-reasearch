'use client';

import { SessionDetails } from '@/components/session-details';
import useDashboardStore from '@/hooks/useDashboard';
import { useWebSocket } from '@/lib/websocket';

export default function SessionPage({ params }: { params: { id: string } }) {
  const sessionId = params.id;
  const { connected, events } = useWebSocket(sessionId);
  const viewMode = useDashboardStore((state) => state.viewMode);
  const selectedEvent = useDashboardStore((state) => state.selectedEvent);

  return (
    <SessionDetails
      sessionId={sessionId}
      connected={connected}
      events={events}
      selectedEvent={selectedEvent}
      viewMode={viewMode}
      onSelectEvent={(event) => useDashboardStore.getState().setSelectedEvent(event)}
      onViewModeChange={(mode) => useDashboardStore.getState().setViewMode(mode)}
    />
  );
}
