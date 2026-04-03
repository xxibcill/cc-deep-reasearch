'use client';

import { useDeferredValue, useEffect, useState } from 'react';
import { Activity, Archive, DatabaseZap, Radar } from 'lucide-react';

import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
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
  const activeSessions = sessions.filter((session) => session.active).length;
  const reportReady = sessions.filter((session) => session.hasReport).length;
  const archivedSessions = sessions.filter((session) => session.archived).length;

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
    <div className="mx-auto max-w-content px-page-x py-page-y">
      <section className="grid gap-6 xl:grid-cols-[minmax(0,1.15fr)_24rem]">
        <div className="panel-shell data-grid rounded-[1.5rem] p-6 sm:p-8">
          <div className="grid gap-8 xl:grid-cols-[minmax(0,1fr)_18rem]">
            <div className="space-y-6">
              <div className="space-y-4">
                <p className="eyebrow">Research control room</p>
                <h1 className="font-display text-[clamp(3.2rem,8vw,6.2rem)] font-semibold uppercase tracking-[0.01em] text-foreground">
                  Monitor the research machine, not just the prompt.
                </h1>
                <p className="max-w-2xl text-base leading-7 text-muted-foreground sm:text-lg">
                  A live workspace for starting runs, tracing agent behavior, and reviewing the
                  research archive without falling back into generic dashboard chrome.
                </p>
              </div>

              <div className="flex flex-wrap gap-2">
                <Badge variant="warning">Live telemetry</Badge>
                <Badge variant="secondary">Session archive</Badge>
                <Badge variant="outline">Traceable prompts</Badge>
              </div>

              <div className="grid gap-3 md:grid-cols-3">
                {[
                  {
                    label: 'Active sessions',
                    value: activeSessions,
                    note: 'Runs still generating telemetry',
                    icon: Activity,
                  },
                  {
                    label: 'Reports ready',
                    value: reportReady,
                    note: 'Sessions with exportable output',
                    icon: Radar,
                  },
                  {
                    label: 'Archive loaded',
                    value: total,
                    note: 'Sessions currently in scope',
                    icon: DatabaseZap,
                  },
                ].map(({ label, value, note, icon: Icon }) => (
                  <div
                    key={label}
                    className="rounded-[1rem] border border-border/75 bg-surface/72 p-4 shadow-card"
                  >
                    <div className="flex items-center justify-between gap-3">
                      <p className="eyebrow">{label}</p>
                      <Icon className="h-4 w-4 text-primary" />
                    </div>
                    <p className="mt-4 font-display text-[2.8rem] font-semibold leading-none tabular-nums text-foreground">
                      {loading ? '...' : value}
                    </p>
                    <p className="mt-2 text-sm leading-6 text-muted-foreground">{note}</p>
                  </div>
                ))}
              </div>
            </div>

            <div className="section-rule space-y-4 xl:pl-3">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <p className="eyebrow">Current frame</p>
                  <h2 className="mt-2 font-display text-[2rem] font-semibold uppercase tracking-[0.02em]">
                    Archive ledger
                  </h2>
                </div>
                <Archive className="h-5 w-5 text-primary" />
              </div>

              <div className="space-y-3 rounded-[1rem] border border-border/75 bg-surface/72 p-4 shadow-card">
                {[
                  ['Visible sessions', sessions.length],
                  ['Archived', archivedSessions],
                  ['With reports', reportReady],
                ].map(([label, value]) => (
                  <div key={label} className="flex items-center justify-between gap-4 border-b border-border/60 pb-3 last:border-b-0 last:pb-0">
                    <span className="text-sm text-muted-foreground">{label}</span>
                    <span className="font-mono text-sm tabular-nums text-foreground">{loading ? '--' : value}</span>
                  </div>
                ))}
              </div>

              <p className="text-sm leading-6 text-muted-foreground">
                The archive is optimized for technical operators: dense where it should be dense,
                quiet where it should let the data breathe.
              </p>
            </div>
          </div>
        </div>

        <aside className="xl:sticky xl:top-[7.5rem] xl:self-start">
          <Card className="rounded-[1.45rem]">
            <CardHeader className="border-b border-border/70">
              <p className="eyebrow">Launch console</p>
              <CardTitle className="text-[2rem]">Start Research</CardTitle>
              <p className="max-w-[28ch] text-sm leading-6 text-muted-foreground">
                Define the question, tune depth, and apply prompt overrides without leaving the
                primary workspace.
              </p>
            </CardHeader>
            <CardContent className="pt-6">
              <StartResearchForm />
            </CardContent>
          </Card>
        </aside>
      </section>

      <section className="mt-8">
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
      </section>
    </div>
  );
}
