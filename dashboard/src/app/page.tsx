'use client';

import { useEffect } from 'react';

import { SessionList } from '@/components/session-list';
import { StartResearchForm } from '@/components/start-research-form';
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
        <h1 className="text-4xl font-bold mb-2">CC Deep Research</h1>
        <p className="text-muted-foreground">AI-powered research with real-time monitoring</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        <div className="lg:col-span-1">
          <div className="bg-card border rounded-lg p-6">
            <h2 className="text-xl font-semibold mb-4">Start Research</h2>
            <StartResearchForm />
          </div>
        </div>

        <div className="lg:col-span-2">
          <div className="bg-card border rounded-lg p-6">
            <h2 className="text-xl font-semibold mb-4">Recent Sessions</h2>
            <SessionList loading={loading} sessions={sessions} />
          </div>
        </div>
      </div>
    </div>
  );
}
