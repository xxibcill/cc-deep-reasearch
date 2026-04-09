'use client';

import Link from 'next/link';
import { useEffect, useState } from 'react';
import { ArrowRight, BarChart3, Calendar, CheckCircle2, Clock, FileText, TrendingDown, TrendingUp, XCircle } from 'lucide-react';

import { Badge } from '@/components/ui/badge';
import { buttonVariants } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { MetricCard } from '@/components/ui/metric-card';
import { getAnalytics, getApiErrorMessage, getSessions, type AnalyticsResponse } from '@/lib/api';
import type { Session } from '@/types/telemetry';

const DAYS_OPTIONS = [
  { value: 7, label: '7 days' },
  { value: 14, label: '14 days' },
  { value: 30, label: '30 days' },
  { value: 90, label: '90 days' },
];

export default function AnalyticsPage() {
  const [daysBack, setDaysBack] = useState(30);
  const [analytics, setAnalytics] = useState<AnalyticsResponse | null>(null);
  const [recentSessions, setRecentSessions] = useState<Session[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;

    const loadAnalytics = async () => {
      setLoading(true);
      setError(null);

      try {
        const [data, recent] = await Promise.all([
          getAnalytics(daysBack),
          getSessions({ limit: 24 }),
        ]);
        if (!mounted) {
          return;
        }
        setAnalytics(data);
        setRecentSessions(recent.sessions);
      } catch (err) {
        console.error('Failed to load analytics:', err);
        if (mounted) {
          setError(getApiErrorMessage(err, 'Failed to load analytics data.'));
        }
      } finally {
        if (mounted) {
          setLoading(false);
        }
      }
    };

    void loadAnalytics();

    return () => {
      mounted = false;
    };
  }, [daysBack]);

  const formatDuration = (ms: number): string => {
    if (ms < 1000) {
      return `${ms}ms`;
    }
    const seconds = Math.floor(ms / 1000);
    if (seconds < 60) {
      return `${seconds}s`;
    }
    const minutes = Math.floor(seconds / 60);
    const remainingSeconds = seconds % 60;
    if (minutes < 60) {
      return `${minutes}m ${remainingSeconds}s`;
    }
    const hours = Math.floor(minutes / 60);
    const remainingMinutes = minutes % 60;
    return `${hours}h ${remainingMinutes}m`;
  };

  const formatDate = (dateStr: string | null): string => {
    if (!dateStr) {
      return 'N/A';
    }
    try {
      return new Date(dateStr).toLocaleDateString('en-US', {
        month: 'short',
        day: 'numeric',
      });
    } catch {
      return 'N/A';
    }
  };

  const summary = analytics?.summary;
  const cutoff = Date.now() - daysBack * 24 * 60 * 60 * 1000;
  const contributingSessions = recentSessions.filter((session) => {
    const anchor = session.createdAt ?? session.lastEventAt ?? session.completedAt;
    if (!anchor) {
      return false;
    }

    const timestamp = new Date(anchor).getTime();
    return Number.isFinite(timestamp) && timestamp >= cutoff;
  });

  return (
    <div className="mx-auto max-w-content px-page-x py-page-y">
      <div className="space-y-8">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="space-y-2">
            <p className="eyebrow">Operational analytics</p>
            <h1 className="font-display text-[clamp(2.8rem,6vw,4.8rem)] font-semibold uppercase tracking-[0.01em] text-foreground">
              System health
            </h1>
            <p className="max-w-2xl text-base leading-7 text-muted-foreground sm:text-lg">
              Aggregate trends and operational metrics across research runs.
            </p>
          </div>

          <div className="flex items-center gap-2 rounded-full border border-border/70 bg-surface/75 px-4 py-2 text-sm shadow-card">
            <Calendar className="h-4 w-4 text-muted-foreground" />
            <label htmlFor="analytics-range" className="sr-only">
              Analytics time window
            </label>
            <select
              id="analytics-range"
              aria-label="Analytics time window"
              value={daysBack}
              onChange={(e) => setDaysBack(Number(e.target.value))}
              className="bg-transparent text-foreground focus:outline-none"
            >
              {DAYS_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          <Badge variant="outline">Trends across the last {daysBack} days</Badge>
          <Link href="/" className={buttonVariants({ variant: 'outline', size: 'sm' })}>
            Open research archive
            <ArrowRight className="ml-2 h-3.5 w-3.5" />
          </Link>
        </div>

        {error && (
          <Card className="border-destructive/50 bg-destructive/10">
            <CardContent className="py-4">
              <p className="text-destructive">{error}</p>
            </CardContent>
          </Card>
        )}

        {loading ? (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {[...Array(4)].map((_, i) => (
              <Card key={i} className="animate-pulse">
                <CardHeader className="pb-2">
                  <div className="h-4 w-24 rounded bg-muted" />
                </CardHeader>
                <CardContent>
                  <div className="h-8 w-16 rounded bg-muted" />
                </CardContent>
              </Card>
            ))}
          </div>
        ) : summary ? (
          <>
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              <MetricCard
                description="Total research runs"
                icon={BarChart3}
                label="Total runs"
                tone="neutral"
                value={summary.total_runs}
              />

              <MetricCard
                description="Successfully completed"
                icon={CheckCircle2}
                label="Completed"
                tone="success"
                value={summary.completed_runs}
              />

              <MetricCard
                description="Failed or errored"
                icon={XCircle}
                label="Failed"
                tone="warning"
                value={summary.failed_runs}
              />

              <MetricCard
                description="Cancelled or stopped"
                icon={TrendingDown}
                label="Interrupted"
                tone="warning"
                value={summary.interrupted_runs}
              />
            </div>

            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              <MetricCard
                description="Average completion time"
                icon={Clock}
                label="Avg duration"
                tone="neutral"
                value={formatDuration(summary.avg_duration_ms)}
              />

              <MetricCard
                description="Average sources per run"
                icon={FileText}
                label="Avg sources"
                tone="neutral"
                value={summary.avg_sources.toFixed(1)}
              />

              <MetricCard
                description="Sessions with generated reports"
                icon={FileText}
                label="Report availability"
                tone={summary.report_availability_rate >= 70 ? 'success' : 'warning'}
                value={`${summary.report_availability_rate}%`}
              />

              <MetricCard
                description="Active vs archived sessions"
                icon={TrendingUp}
                label="Active sessions"
                tone="neutral"
                value={`${summary.active_sessions} / ${summary.archived_sessions}`}
              />
            </div>

            {analytics && analytics.status_counts.length > 0 && (
              <Card>
                <CardHeader>
                  <CardTitle className="text-lg">Status distribution</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="flex flex-wrap gap-2">
                    {analytics.status_counts.map((item) => {
                      const tone =
                        item.status === 'completed' || item.status === 'success'
                          ? 'success'
                          : item.status === 'failed' || item.status === 'error'
                            ? 'warning'
                            : item.status === 'interrupted' || item.status === 'cancelled'
                              ? 'warning'
                              : 'neutral';
                      return (
                        <Badge key={item.status} variant={tone as 'default'}>
                          {item.status}: {item.count}
                        </Badge>
                      );
                    })}
                  </div>
                </CardContent>
              </Card>
            )}

            {analytics && analytics.duration_by_status.length > 0 && (
              <Card>
                <CardHeader>
                  <CardTitle className="text-lg">Duration by status</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="border-b border-border/70 text-left">
                          <th className="pb-2 pr-4 font-medium text-muted-foreground">Status</th>
                          <th className="pb-2 pr-4 font-medium text-muted-foreground">Count</th>
                          <th className="pb-2 pr-4 font-medium text-muted-foreground">Avg</th>
                          <th className="pb-2 pr-4 font-medium text-muted-foreground">Min</th>
                          <th className="pb-2 font-medium text-muted-foreground">Max</th>
                        </tr>
                      </thead>
                      <tbody>
                        {analytics.duration_by_status.map((row) => (
                          <tr key={row.status} className="border-b border-border/30">
                            <td className="py-2 pr-4">{row.status}</td>
                            <td className="py-2 pr-4">{row.count}</td>
                            <td className="py-2 pr-4">{formatDuration(row.avg_duration_ms)}</td>
                            <td className="py-2 pr-4">{formatDuration(row.min_duration_ms)}</td>
                            <td className="py-2">{formatDuration(row.max_duration_ms)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </CardContent>
              </Card>
            )}

            {analytics && analytics.daily_volume.length > 0 && (
              <Card>
                <CardHeader>
                  <CardTitle className="text-lg">Daily volume</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="border-b border-border/70 text-left">
                          <th className="pb-2 pr-4 font-medium text-muted-foreground">Date</th>
                          <th className="pb-2 pr-4 font-medium text-muted-foreground">Total</th>
                          <th className="pb-2 pr-4 font-medium text-muted-foreground">Completed</th>
                          <th className="pb-2 pr-4 font-medium text-muted-foreground">Failed</th>
                          <th className="pb-2 font-medium text-muted-foreground">Interrupted</th>
                        </tr>
                      </thead>
                      <tbody>
                        {analytics.daily_volume.slice(0, 14).map((row) => (
                          <tr key={row.day} className="border-b border-border/30">
                            <td className="py-2 pr-4">{formatDate(row.day)}</td>
                            <td className="py-2 pr-4">{row.total_runs}</td>
                            <td className="py-2 pr-4 text-emerald-600">{row.completed}</td>
                            <td className="py-2 pr-4 text-red-600">{row.failed}</td>
                            <td className="py-2 text-amber-600">{row.interrupted}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </CardContent>
              </Card>
            )}

            {analytics && analytics.sources_trend.length > 0 && (
              <Card>
                <CardHeader>
                  <CardTitle className="text-lg">Sources trend</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="border-b border-border/70 text-left">
                          <th className="pb-2 pr-4 font-medium text-muted-foreground">Date</th>
                          <th className="pb-2 pr-4 font-medium text-muted-foreground">Runs</th>
                          <th className="pb-2 pr-4 font-medium text-muted-foreground">Total sources</th>
                          <th className="pb-2 font-medium text-muted-foreground">Avg sources</th>
                        </tr>
                      </thead>
                      <tbody>
                        {analytics.sources_trend.slice(0, 14).map((row) => (
                          <tr key={row.day} className="border-b border-border/30">
                            <td className="py-2 pr-4">{formatDate(row.day)}</td>
                            <td className="py-2 pr-4">{row.run_count}</td>
                            <td className="py-2 pr-4">{row.total_sources}</td>
                            <td className="py-2">{row.avg_sources.toFixed(1)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </CardContent>
              </Card>
            )}

            {analytics && analytics.depth_distribution.length > 0 && (
              <Card>
                <CardHeader>
                  <CardTitle className="text-lg">Duration by depth</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="border-b border-border/70 text-left">
                          <th className="pb-2 pr-4 font-medium text-muted-foreground">Depth</th>
                          <th className="pb-2 pr-4 font-medium text-muted-foreground">Count</th>
                          <th className="pb-2 font-medium text-muted-foreground">Avg duration</th>
                        </tr>
                      </thead>
                      <tbody>
                        {analytics.depth_distribution.map((row) => (
                          <tr key={row.depth} className="border-b border-border/30">
                            <td className="py-2 pr-4">{row.depth}</td>
                            <td className="py-2 pr-4">{row.count}</td>
                            <td className="py-2">{formatDuration(row.avg_duration_ms)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </CardContent>
              </Card>
            )}

            <Card>
              <CardHeader>
                <CardTitle className="text-lg">Recent sessions behind these metrics</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                {contributingSessions.length > 0 ? (
                  <div className="space-y-3">
                    <p className="text-sm text-muted-foreground">
                      Drill back into recent sessions from the selected window to validate any aggregate trend before acting on it.
                    </p>
                    <div className="grid gap-3">
                      {contributingSessions.slice(0, 6).map((session) => (
                        <Link
                          key={session.sessionId}
                          href={`/session/${session.sessionId}`}
                          className="flex flex-wrap items-center justify-between gap-3 rounded-[1rem] border border-border/70 bg-surface/58 px-4 py-3 transition-colors hover:bg-surface-raised/70"
                        >
                          <div className="space-y-1">
                            <p className="text-sm font-medium text-foreground">{session.label}</p>
                            <p className="text-xs text-muted-foreground">
                              {session.status} • {session.depth ?? 'standard'} depth •{' '}
                              {session.totalSources} sources
                            </p>
                          </div>
                          <div className="flex items-center gap-2">
                            {session.hasReport ? <Badge variant="success">Report</Badge> : null}
                            {session.archived ? <Badge variant="outline">Archived</Badge> : null}
                            <ArrowRight className="h-4 w-4 text-muted-foreground" />
                          </div>
                        </Link>
                      ))}
                    </div>
                  </div>
                ) : (
                  <p className="text-sm text-muted-foreground">
                    No recent sessions were found for the selected window.
                  </p>
                )}
              </CardContent>
            </Card>

            {analytics &&
              analytics.status_counts.length === 0 &&
              analytics.daily_volume.length === 0 && (
                <Card>
                  <CardContent className="py-12 text-center">
                    <BarChart3 className="mx-auto h-12 w-12 text-muted-foreground" />
                    <p className="mt-4 text-lg text-muted-foreground">
                      No data available for the selected period
                    </p>
                    <p className="text-sm text-muted-foreground">
                      Run some research sessions to see analytics here
                    </p>
                  </CardContent>
                </Card>
              )}
          </>
        ) : (
          <Card>
            <CardContent className="py-12 text-center">
              <BarChart3 className="mx-auto h-12 w-12 text-muted-foreground" />
              <p className="mt-4 text-lg text-muted-foreground">No analytics data available</p>
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
}
