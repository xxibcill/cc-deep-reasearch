'use client';

import { useDeferredValue, useEffect, useState } from 'react';
import { AlertCircle, Play, Radar } from 'lucide-react';

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

  const activeSessions = sessions.filter((s) => s.active);
  const failedSessions = sessions.filter((s) => !s.active && (s.status === 'failed' || s.status === 'interrupted'));
  const readySessions = sessions.filter((s) => s.hasReport && !s.active);
  const featuredReadySession = readySessions[0] ?? null;
  const hasNoSessions = total === 0 && !loading;

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
      <section className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_minmax(20rem,0.62fr)]">
        <div className="panel-shell data-grid rounded-[1.5rem] p-6 sm:p-8">
          <div className="space-y-8">
            <div className="space-y-4">
              <p className="eyebrow">Control room</p>
              <h1 className="font-display text-[clamp(2.8rem,6vw,4.8rem)] font-semibold uppercase tracking-[0.01em] text-foreground">
                {hasNoSessions ? 'Ready to research' : 'Operations overview'}
              </h1>
              <p className="max-w-2xl text-base leading-7 text-muted-foreground sm:text-lg">
                {hasNoSessions
                  ? 'Start your first research session to begin monitoring runs, tracing agent behavior, and building your archive.'
                  : 'Active runs, attention-needed sessions, and completed research with reports ready.'}
              </p>
            </div>

            {hasNoSessions ? (
              <div className="flex flex-wrap gap-2">
                <Badge variant="default">No sessions yet</Badge>
              </div>
            ) : (
              <div className="space-y-4">
                <div className="grid gap-3 md:grid-cols-3">
                  <Card className="border-slate-200/80 shadow-sm">
                    <CardContent className="flex items-center gap-3 p-4">
                      <div className="rounded-xl bg-slate-100 p-2 text-slate-700">
                        <Play className="h-4 w-4" />
                      </div>
                      <div>
                        <p className="text-xs uppercase tracking-wide text-muted-foreground">Running now</p>
                        <p className="text-lg font-semibold text-slate-900">{loading ? '...' : activeSessions.length}</p>
                      </div>
                    </CardContent>
                  </Card>

                  <Card className="border-slate-200/80 shadow-sm">
                    <CardContent className="flex items-center gap-3 p-4">
                      <div className="rounded-xl bg-amber-100 p-2 text-amber-700">
                        <AlertCircle className="h-4 w-4" />
                      </div>
                      <div>
                        <p className="text-xs uppercase tracking-wide text-muted-foreground">Needs attention</p>
                        <p className="text-lg font-semibold text-slate-900">{loading ? '...' : failedSessions.length}</p>
                      </div>
                    </CardContent>
                  </Card>

                  <Card className="border-slate-200/80 shadow-sm">
                    <CardContent className="flex items-center gap-3 p-4">
                      <div className="rounded-xl bg-emerald-100 p-2 text-emerald-700">
                        <Radar className="h-4 w-4" />
                      </div>
                      <div>
                        <p className="text-xs uppercase tracking-wide text-muted-foreground">Reports ready</p>
                        <p className="text-lg font-semibold text-slate-900">{loading ? '...' : readySessions.length}</p>
                      </div>
                    </CardContent>
                  </Card>
                </div>
              </div>
            )}
          </div>
        </div>

        <aside className="xl:sticky xl:top-[7.5rem] xl:self-start">
          <Card className={`rounded-[1.45rem] ${hasNoSessions ? '' : 'opacity-75'}`}>
            <CardHeader className="border-b border-border/70">
              <p className="eyebrow">Launch console</p>
              <CardTitle className="text-[2rem]">Start Research</CardTitle>
              <p className="max-w-[28ch] text-sm leading-6 text-muted-foreground">
                Pick a preset, describe the question, then open operator controls only when the
                run needs custom tuning.
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
