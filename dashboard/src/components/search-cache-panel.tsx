'use client';

import { startTransition, useEffect, useState } from 'react';

import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { AlertDialog } from '@/components/ui/alert-dialog';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import {
  clearSearchCache,
  getApiErrorMessage,
  getSearchCacheStats,
  purgeExpiredSearchCacheEntries,
} from '@/lib/api';
import type { SearchCacheStats } from '@/types/search-cache';

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function formatTtl(seconds: number): string {
  if (seconds < 60) return `${seconds}s`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ${Math.floor((seconds % 3600) / 60)}m`;
  return `${Math.floor(seconds / 86400)}d ${Math.floor((seconds % 86400) / 3600)}h`;
}

export function SearchCachePanel() {
  const [stats, setStats] = useState<SearchCacheStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState(false);
  const [actionMessage, setActionMessage] = useState<string | null>(null);
  const [showClearConfirm, setShowClearConfirm] = useState(false);

  const loadStats = async ({ preserveVisibleState = false }: { preserveVisibleState?: boolean } = {}) => {
    if (!preserveVisibleState) {
      setLoading(true);
    }
    setError(null);
    try {
      const response = await getSearchCacheStats();
      startTransition(() => {
        setStats(response);
      });
    } catch (err) {
      setError(getApiErrorMessage(err, 'Failed to load cache stats.'));
    } finally {
      if (!preserveVisibleState) {
        setLoading(false);
      }
    }
  };

  useEffect(() => {
    void loadStats();
  }, []);

  const handlePurgeExpired = async () => {
    setActionLoading(true);
    setActionMessage(null);
    setError(null);
    try {
      const response = await purgeExpiredSearchCacheEntries();
      setActionMessage(response.message || `Purged ${response.purged} expired entries.`);
      await loadStats({ preserveVisibleState: true });
    } catch (err) {
      setError(getApiErrorMessage(err, 'Failed to purge expired entries.'));
    } finally {
      setActionLoading(false);
    }
  };

  const handleClearCache = async () => {
    setActionLoading(true);
    setActionMessage(null);
    setError(null);
    setShowClearConfirm(false);
    try {
      const response = await clearSearchCache();
      setActionMessage(response.message || `Cleared ${response.cleared} entries.`);
      await loadStats({ preserveVisibleState: true });
    } catch (err) {
      setError(getApiErrorMessage(err, 'Failed to clear cache.'));
    } finally {
      setActionLoading(false);
    }
  };

  if (loading) {
    return (
      <Card className="border-border/80 bg-card/95">
        <CardHeader>
          <CardTitle className="text-base">Search cache</CardTitle>
          <CardDescription>Loading cache health, capacity, and retention details.</CardDescription>
        </CardHeader>
        <CardContent>
          <Alert variant="default">
            <AlertTitle>Loading cache stats</AlertTitle>
            <AlertDescription>Fetching the latest search cache status from the backend.</AlertDescription>
          </Alert>
        </CardContent>
      </Card>
    );
  }

  if (error && !stats) {
    return (
      <Card className="border-border/80 bg-card/95">
        <CardHeader>
          <CardTitle className="text-base">Search cache</CardTitle>
          <CardDescription>Cache operations are unavailable until the stats endpoint responds again.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <Alert variant="destructive">
            <AlertTitle>Cache stats unavailable</AlertTitle>
            <AlertDescription>{error}</AlertDescription>
          </Alert>
          <Button variant="outline" size="sm" onClick={() => void loadStats()}>
            Retry
          </Button>
        </CardContent>
      </Card>
    );
  }

  if (!stats) {
    return null;
  }

  return (
    <>
      <Card className="overflow-hidden border-border/80 bg-card/95">
        <CardHeader className="gap-4 border-b border-border/80 bg-muted/20">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
            <div className="space-y-2">
              <div className="flex flex-wrap items-center gap-2">
                <CardTitle className="text-base">Search cache</CardTitle>
                <Badge variant={stats.enabled ? 'success' : 'secondary'}>
                  {stats.enabled ? 'Active' : 'Inactive'}
                </Badge>
                <Badge variant={stats.db_exists ? 'outline' : 'warning'}>
                  {stats.db_exists ? 'Database ready' : 'Database pending'}
                </Badge>
              </div>
              <CardDescription>
                {stats.enabled
                  ? 'Reuse identical queries to reduce provider calls and keep repeat runs cheaper.'
                  : 'Caching is disabled, so every query goes back to the upstream provider.'}
              </CardDescription>
            </div>

            <div className="flex flex-wrap gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => void loadStats({ preserveVisibleState: true })}
                disabled={actionLoading}
              >
                Refresh
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={handlePurgeExpired}
                disabled={actionLoading || !stats.enabled || stats.expired_entries === 0}
              >
                {actionLoading ? 'Working…' : `Purge expired (${stats.expired_entries})`}
              </Button>
              <Button
                variant="destructive"
                size="sm"
                onClick={() => setShowClearConfirm(true)}
                disabled={actionLoading || !stats.enabled || stats.total_entries === 0}
              >
                Clear all
              </Button>
            </div>
          </div>
        </CardHeader>

        <CardContent className="space-y-4 pt-6">
          {error ? (
            <Alert variant="destructive">
              <AlertTitle>Cache action failed</AlertTitle>
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          ) : null}

          {actionMessage ? (
            <Alert variant="success">
              <AlertTitle>Cache updated</AlertTitle>
              <AlertDescription>{actionMessage}</AlertDescription>
            </Alert>
          ) : null}

          {!stats.enabled ? (
            <Alert variant="warning">
              <AlertTitle>Search cache is disabled</AlertTitle>
              <AlertDescription>
                Enable the cache in the config editor above if you want identical searches to reuse previous results.
              </AlertDescription>
            </Alert>
          ) : null}

          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
            <CacheMetric label="Total entries" value={stats.total_entries.toLocaleString()} />
            <CacheMetric
              label="Active entries"
              value={stats.active_entries.toLocaleString()}
              emphasis="success"
            />
            <CacheMetric
              label="Expired entries"
              value={stats.expired_entries.toLocaleString()}
              emphasis={stats.expired_entries > 0 ? 'warning' : 'default'}
            />
            <CacheMetric label="Total hits" value={stats.total_hits.toLocaleString()} />
            <CacheMetric label="TTL" value={formatTtl(stats.ttl_seconds)} />
            <CacheMetric label="Capacity" value={stats.max_entries.toLocaleString()} />
            <CacheMetric label="Approx. size" value={formatBytes(stats.approximate_size_bytes)} />
            <CacheMetric
              label="Hit reuse ratio"
              value={
                stats.total_entries > 0
                  ? `${Math.round((stats.total_hits / stats.total_entries) * 10) / 10}x`
                  : '0x'
              }
            />
          </div>

          <div className="rounded-xl border border-border bg-background/50 px-4 py-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="space-y-1">
                <div className="text-sm font-medium">Cache database</div>
                <div className="text-xs text-muted-foreground">
                  {stats.db_exists
                    ? 'Persistent cache file is available for new and existing entries.'
                    : 'The database file will be created the first time the cache is written.'}
                </div>
              </div>
              <Badge variant={stats.db_exists ? 'success' : 'warning'}>
                {stats.db_exists ? 'Ready' : 'Not created'}
              </Badge>
            </div>
            <p className="mt-3 break-all font-mono text-xs text-muted-foreground">{stats.db_path}</p>
          </div>
        </CardContent>
      </Card>

      <AlertDialog
        open={showClearConfirm}
        onOpenChange={setShowClearConfirm}
        title="Clear all search cache entries?"
        description={
          <>
            This removes <strong>{stats.total_entries.toLocaleString()}</strong> cached search
            {stats.total_entries === 1 ? ' result' : ' results'} from the local cache database.
            New searches will repopulate entries as they run.
          </>
        }
        confirmLabel="Clear cache"
        destructive
        loading={actionLoading}
        loadingLabel="Clearing…"
        onConfirm={handleClearCache}
      />
    </>
  );
}

function CacheMetric({
  label,
  value,
  emphasis = 'default',
}: {
  label: string;
  value: string;
  emphasis?: 'default' | 'success' | 'warning';
}) {
  const valueClassName =
    emphasis === 'success'
      ? 'text-success'
      : emphasis === 'warning'
        ? 'text-warning'
        : 'text-foreground';

  return (
    <div className="rounded-xl border border-border bg-background/50 px-4 py-3">
      <div className="text-xs uppercase tracking-[0.18em] text-muted-foreground">{label}</div>
      <div className={`mt-2 text-xl font-semibold tabular-nums ${valueClassName}`}>{value}</div>
    </div>
  );
}
