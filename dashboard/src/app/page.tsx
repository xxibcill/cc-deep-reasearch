'use client';

import Link from 'next/link';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card'
import { useDeferredValue, useEffect, useState } from 'react';

import { SessionList } from '@/components/session-list';
import { StartResearchForm } from '@/components/start-research-form';
import { getApiErrorMessage, getSessions } from '@/lib/api';
import useDashboardStore from '@/hooks/useDashboard';

const SESSION_PAGE_SIZE = 24;

export default function HomePage() {
  const sessions = useDashboardStore((state) => state.sessions);
  const loading = useDashboardStore((state) => state.sessionsLoading);
  const loadingMore = useDashboardStore((state) => state.sessionsLoadingMore);
  const nextCursor = useDashboardStore((state) => state.sessionsNextCursor);
  const total = useDashboardStore((state) => state.sessionsTotal);
  const query = useDashboardStore((state) => state.sessionListQuery);
  const [sessionsError, setSessionsError] = useState<string | null>(null);
  const [loadMoreError, setLoadMoreError] = useState<string | null>(null);
  const [reloadNonce, setReloadNonce] = useState(0);
  const deferredSearch = useDeferredValue(query.search);

  useEffect(() => {
    let mounted = true;

    const loadSessions = async () => {
      useDashboardStore.getState().setSessionsLoading(true);
      if (mounted) {
        setSessionsError(null);
        setLoadMoreError(null);
      }

      try {
        const data = await getSessions({
          limit: SESSION_PAGE_SIZE,
          active_only: query.activeOnly,
          search: deferredSearch || null,
          status: query.status || null,
        });
        if (!mounted) {
          return;
        }
        useDashboardStore.getState().setSessions(data.sessions, {
          total: data.total,
          nextCursor: data.nextCursor,
        });
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
  }, [deferredSearch, query.activeOnly, query.status, reloadNonce]);

  const handleLoadMore = async () => {
    if (!nextCursor || loadingMore) {
      return;
    }

    useDashboardStore.getState().setSessionsLoadingMore(true);
    setLoadMoreError(null);

    try {
      const data = await getSessions({
        limit: SESSION_PAGE_SIZE,
        cursor: nextCursor,
        active_only: query.activeOnly,
        search: deferredSearch || null,
        status: query.status || null,
      });
      useDashboardStore.getState().setSessions(data.sessions, {
        total: data.total,
        nextCursor: data.nextCursor,
        append: true,
      });
    } catch (error) {
      console.error('Failed to load more sessions:', error);
      setLoadMoreError(
        getApiErrorMessage(error, 'Failed to load more sessions.')
      );
    } finally {
      useDashboardStore.getState().setSessionsLoadingMore(false);
    }
  };

  return (
    <div className="container mx-auto px-4 py-8">
      <header className="mb-8">
        <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
          <div>
            <h1 className="text-3xl font-bold tracking-tight">CC Deep Research</h1>
            <p className="text-sm text-muted-foreground mt-1">AI-powered research with real-time monitoring</p>
          </div>
          <Link
            className="inline-flex h-9 items-center justify-center rounded-md border border-border bg-background px-4 py-2 text-sm font-medium transition-colors hover:bg-accent hover:text-accent-foreground"
            href="/settings"
          >
            Open settings
          </Link>
        </div>
      </header>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[340px_1fr]">
        <aside className="lg:sticky lg:top-8 lg:self-start">
          <Card className="p-5">
            <CardHeader>
              <CardTitle>Start Research</CardTitle>
            </CardHeader>
            <CardContent>
              <StartResearchForm />
            </CardContent>
          </Card>
        </aside>

        <section>
          <div className="rounded-lg border bg-card p-5">
            <SessionList
              error={sessionsError}
              loading={loading}
              loadingMore={loadingMore}
              loadMoreError={loadMoreError}
              nextCursor={nextCursor}
              onRefresh={() => setReloadNonce((value) => value + 1)}
              onRetry={() => setReloadNonce((value) => value + 1)}
              onLoadMore={handleLoadMore}
              sessions={sessions}
              total={total}
            />
          </div>
        </section>
      </div>
    </div>
  );
}
