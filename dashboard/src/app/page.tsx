'use client';

import { useEffect } from 'react';

import { SessionList } from '@/components/session-list';
import { getSessions } from '@/lib/api';
import useDashboardStore from '@/hooks/useDashboard';

export default function HomePage() {
  const sessions = useDashboardStore((state) => state.sessions);
  const loading = useDashboardStore((state) => state.sessionsLoading);

  useEffect(() => {
    const loadSessions = async () => {
      useDashboardStore.getState().setSessionsLoading(true);

      try {
        const data = await getSessions(false, 50);
        useDashboardStore.getState().setSessions(data);
      } catch (error) {
        console.error('Failed to load sessions:', error);
      } finally {
        useDashboardStore.getState().setSessionsLoading(false);
      }
    };

    void loadSessions();
  }, []);

  return (
    <div className="container mx-auto px-4 py-8">
      <div className="mb-8">
        <h1 className="text-4xl font-bold mb-2">CC Deep Research Monitoring</h1>
        <p className="text-muted-foreground">Real-time workflow visualization and agent tracking</p>
      </div>
      <SessionList loading={loading} sessions={sessions} />
    </div>
  );
}
