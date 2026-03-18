'use client';

import { useEffect, useState } from 'react';

import { SessionList } from '@/components/session-list';
import { StartResearchForm } from '@/components/start-research-form';
import { getApiErrorMessage, getSessions } from '@/lib/api';
import useDashboardStore from '@/hooks/useDashboard';

export default function HomePage() {
  const sessions = useDashboardStore((state) => state.sessions);
  const loading = useDashboardStore((state) => state.sessionsLoading);
  const [sessionsError, setSessionsError] = useState<string | null>(null);
  const [reloadNonce, setReloadNonce] = useState(0);

  useEffect(() => {
    let mounted = true;

    const loadSessions = async () => {
      useDashboardStore.getState().setSessionsLoading(true);
      if (mounted) {
        setSessionsError(null);
      }

      try {
        const data = await getSessions(false, 50);
        if (!mounted) {
          return;
        }
        useDashboardStore.getState().setSessions(data);
      } catch (error) {
        console.error('Failed to load sessions:', error);
        if (mounted) {
          setSessionsError(
            getApiErrorMessage(error, 'Failed to load recent sessions.')
          );
        }
      } finally {
        if (mounted) {
          useDashboardStore.getState().setSessionsLoading(false);
        }
      }
    };

    void loadSessions();

    return () => {
      mounted = false;
    };
  }, [reloadNonce]);

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
            <SessionList
              error={sessionsError}
              loading={loading}
              onRetry={() => setReloadNonce((value) => value + 1)}
              sessions={sessions}
            />
          </div>
        </div>
      </div>
    </div>
  );
}
