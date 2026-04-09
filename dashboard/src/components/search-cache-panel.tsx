'use client';

import { startTransition, useCallback, useEffect, useState } from 'react';

import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { AlertDialog } from '@/components/ui/alert-dialog';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import {
  clearSearchCache,
  deleteSearchCacheEntry,
  getApiErrorMessage,
  getSearchCacheEntries,
  getSearchCacheStats,
  purgeExpiredSearchCacheEntries,
} from '@/lib/api';
import type { SearchCacheEntry, SearchCacheStats } from '@/types/search-cache';

const RECENT_ENTRY_LIMIT = 8;

type CacheAction = 'refresh' | 'purge' | 'clear' | 'delete' | null;

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

function formatDateTime(value: string): string {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
}

function formatRelativeTime(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }

  const diffMs = date.getTime() - Date.now();
  const absMs = Math.abs(diffMs);
  const minuteMs = 60_000;
  const hourMs = 60 * minuteMs;
  const dayMs = 24 * hourMs;

  if (absMs < minuteMs) {
    return diffMs >= 0 ? 'in under 1 minute' : 'under 1 minute ago';
  }

  if (absMs < hourMs) {
    const minutes = Math.round(absMs / minuteMs);
    return diffMs >= 0 ? `in ${minutes}m` : `${minutes}m ago`;
  }

  if (absMs < dayMs) {
    const hours = Math.round(absMs / hourMs);
    return diffMs >= 0 ? `in ${hours}h` : `${hours}h ago`;
  }

  const days = Math.round(absMs / dayMs);
  return diffMs >= 0 ? `in ${days}d` : `${days}d ago`;
}

function formatPercent(value: number): string {
  return `${Math.round(value)}%`;
}

function describeReuse(entry: SearchCacheEntry): string {
  if (entry.hit_count === 0) {
    return 'Not reused yet';
  }
  if (entry.hit_count === 1) {
    return '1 cache hit';
  }
  return `${entry.hit_count.toLocaleString()} cache hits`;
}

function shortenCacheKey(cacheKey: string): string {
  if (cacheKey.length <= 18) {
    return cacheKey;
  }
  return `${cacheKey.slice(0, 8)}…${cacheKey.slice(-8)}`;
}

function getHealthSummary(stats: SearchCacheStats): {
  tone: 'secondary' | 'info' | 'warning' | 'success';
  label: string;
  headline: string;
  detail: string;
} {
  const capacityRatio = stats.max_entries > 0 ? (stats.total_entries / stats.max_entries) * 100 : 0;
  const expiredRatio = stats.total_entries > 0 ? (stats.expired_entries / stats.total_entries) * 100 : 0;

  if (!stats.enabled) {
    return {
      tone: 'secondary',
      label: 'Disabled',
      headline: 'Every search goes back to the upstream provider.',
      detail: 'Turn cache back on when you want identical searches to reuse prior results and reduce repeat provider calls.',
    };
  }

  if (!stats.db_exists || stats.total_entries === 0) {
    return {
      tone: 'info',
      label: 'Cold',
      headline: 'The cache is ready but not holding reusable search results yet.',
      detail: 'That is normal after first setup or after a full clear. Fresh runs will repopulate entries automatically.',
    };
  }

  if (stats.expired_entries > 0 && expiredRatio >= 25) {
    return {
      tone: 'warning',
      label: 'Cleanup due',
      headline: `${stats.expired_entries.toLocaleString()} expired entries are taking space that active results could use.`,
      detail: 'Purge expired entries first. It is the lowest-risk cleanup because it only removes results that are already outside the configured TTL.',
    };
  }

  if (capacityRatio >= 90) {
    return {
      tone: 'warning',
      label: 'Near capacity',
      headline: 'The cache is close to its configured entry limit.',
      detail: 'If new results arrive, older entries will churn sooner. Clear only when you explicitly want to reset all cached research behavior.',
    };
  }

  if (stats.total_hits === 0) {
    return {
      tone: 'info',
      label: 'Warming',
      headline: 'Entries exist, but repeat searches have not reused them yet.',
      detail: 'This usually means the cache is still filling with new queries or provider combinations rather than serving repeats.',
    };
  }

  return {
    tone: 'success',
    label: 'Healthy',
    headline: `${stats.active_entries.toLocaleString()} reusable entries are available right now.`,
    detail: `The cache has served ${stats.total_hits.toLocaleString()} total hits, which suggests repeated research work is benefiting from reuse.`,
  };
}

function getEntryState(entry: SearchCacheEntry): {
  label: string;
  tone: 'success' | 'warning' | 'info';
  detail: string;
} {
  if (entry.is_expired) {
    return {
      label: 'Expired',
      tone: 'warning',
      detail: `Expired ${formatRelativeTime(entry.expires_at)}. Safe to purge if you do not need this stale result around for inspection.`,
    };
  }

  if (entry.hit_count > 0) {
    return {
      label: 'Reused',
      tone: 'success',
      detail: `Still reusable for ${formatRelativeTime(entry.expires_at)}. This entry has already reduced repeat provider work.`,
    };
  }

  return {
    label: 'Fresh',
    tone: 'info',
    detail: `Stored ${formatRelativeTime(entry.created_at)} and available until ${formatDateTime(entry.expires_at)}.`,
  };
}

export function SearchCachePanel() {
  const [stats, setStats] = useState<SearchCacheStats | null>(null);
  const [entries, setEntries] = useState<SearchCacheEntry[]>([]);
  const [includeExpired, setIncludeExpired] = useState(true);
  const [statsLoading, setStatsLoading] = useState(true);
  const [entriesLoading, setEntriesLoading] = useState(true);
  const [statsError, setStatsError] = useState<string | null>(null);
  const [entriesError, setEntriesError] = useState<string | null>(null);
  const [entriesMessage, setEntriesMessage] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [actionMessage, setActionMessage] = useState<string | null>(null);
  const [activeAction, setActiveAction] = useState<CacheAction>(null);
  const [showClearConfirm, setShowClearConfirm] = useState(false);
  const [pendingDeleteEntry, setPendingDeleteEntry] = useState<SearchCacheEntry | null>(null);

  const loadStats = useCallback(
    async ({ preserveVisibleState = false }: { preserveVisibleState?: boolean } = {}) => {
      if (!preserveVisibleState) {
        setStatsLoading(true);
      }
      setStatsError(null);

      try {
        const response = await getSearchCacheStats();
        startTransition(() => {
          setStats(response);
        });
      } catch (err) {
        setStatsError(getApiErrorMessage(err, 'Failed to load cache stats.'));
      } finally {
        if (!preserveVisibleState) {
          setStatsLoading(false);
        }
      }
    },
    []
  );

  const loadEntries = useCallback(
    async ({
      preserveVisibleState = false,
      includeExpiredOverride,
    }: {
      preserveVisibleState?: boolean;
      includeExpiredOverride?: boolean;
    } = {}) => {
      if (!preserveVisibleState) {
        setEntriesLoading(true);
      }
      setEntriesError(null);

      try {
        const response = await getSearchCacheEntries(
          includeExpiredOverride ?? includeExpired,
          RECENT_ENTRY_LIMIT,
          0
        );
        startTransition(() => {
          setEntries(response.entries);
          setEntriesMessage(response.message ?? null);
        });
      } catch (err) {
        setEntriesError(getApiErrorMessage(err, 'Failed to load cache entries.'));
      } finally {
        if (!preserveVisibleState) {
          setEntriesLoading(false);
        }
      }
    },
    [includeExpired]
  );

  const refreshPanel = useCallback(
    async ({ preserveVisibleState = true }: { preserveVisibleState?: boolean } = {}) => {
      setActionError(null);
      await Promise.all([
        loadStats({ preserveVisibleState }),
        loadEntries({ preserveVisibleState, includeExpiredOverride: includeExpired }),
      ]);
    },
    [includeExpired, loadEntries, loadStats]
  );

  useEffect(() => {
    void loadStats();
  }, [loadStats]);

  useEffect(() => {
    void loadEntries({ includeExpiredOverride: includeExpired });
  }, [includeExpired, loadEntries]);

  const handleRefresh = async () => {
    setActiveAction('refresh');
    try {
      await refreshPanel();
    } finally {
      setActiveAction(null);
    }
  };

  const handlePurgeExpired = async () => {
    setActiveAction('purge');
    setActionError(null);
    setActionMessage(null);

    try {
      const response = await purgeExpiredSearchCacheEntries();
      setActionMessage(response.message || `Purged ${response.purged} expired entries.`);
      await refreshPanel();
    } catch (err) {
      setActionError(getApiErrorMessage(err, 'Failed to purge expired entries.'));
    } finally {
      setActiveAction(null);
    }
  };

  const handleClearCache = async () => {
    setActiveAction('clear');
    setActionError(null);
    setActionMessage(null);
    setShowClearConfirm(false);

    try {
      const response = await clearSearchCache();
      setActionMessage(response.message || `Cleared ${response.cleared} entries.`);
      await refreshPanel();
    } catch (err) {
      setActionError(getApiErrorMessage(err, 'Failed to clear cache.'));
    } finally {
      setActiveAction(null);
    }
  };

  const handleDeleteEntry = async () => {
    if (!pendingDeleteEntry) {
      return;
    }

    const entryToDelete = pendingDeleteEntry;
    setActiveAction('delete');
    setActionError(null);
    setActionMessage(null);

    try {
      const response = await deleteSearchCacheEntry(entryToDelete.cache_key);
      setActionMessage(
        response.deleted
          ? `Removed cache entry for "${entryToDelete.normalized_query}".`
          : `No cache entry was removed for "${entryToDelete.normalized_query}".`
      );
      if (response.deleted) {
        setEntries((current) =>
          current.filter((entry) => entry.cache_key !== entryToDelete.cache_key)
        );
      }
      setPendingDeleteEntry(null);
      await refreshPanel();
    } catch (err) {
      setActionError(getApiErrorMessage(err, 'Failed to delete cache entry.'));
    } finally {
      setActiveAction(null);
    }
  };

  if (statsLoading) {
    return (
      <Card className="border-border/80 bg-card/95">
        <CardHeader>
          <CardTitle className="text-base">Search cache</CardTitle>
          <CardDescription>Loading cache health, cleanup posture, and recent research reuse.</CardDescription>
        </CardHeader>
        <CardContent>
          <Alert variant="default">
            <AlertTitle>Loading cache status</AlertTitle>
            <AlertDescription>Fetching the latest search-cache stats and recent entries from the backend.</AlertDescription>
          </Alert>
        </CardContent>
      </Card>
    );
  }

  if (statsError && !stats) {
    return (
      <Card className="border-border/80 bg-card/95">
        <CardHeader>
          <CardTitle className="text-base">Search cache</CardTitle>
          <CardDescription>Cache operations stay unavailable until the stats endpoint responds again.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <Alert variant="destructive">
            <AlertTitle>Cache stats unavailable</AlertTitle>
            <AlertDescription>{statsError}</AlertDescription>
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

  const health = getHealthSummary(stats);
  const capacityRatio = stats.max_entries > 0 ? (stats.total_entries / stats.max_entries) * 100 : 0;
  const activeRatio = stats.total_entries > 0 ? (stats.active_entries / stats.total_entries) * 100 : 0;
  const expiredRatio = stats.total_entries > 0 ? (stats.expired_entries / stats.total_entries) * 100 : 0;
  const approximateReuseRatio =
    stats.total_entries > 0 ? Math.round((stats.total_hits / stats.total_entries) * 10) / 10 : 0;
  const safeCleanupLabel =
    stats.expired_entries > 0
      ? `Safest cleanup: purge ${stats.expired_entries.toLocaleString()} expired ${stats.expired_entries === 1 ? 'entry' : 'entries'}`
      : 'Safest cleanup: nothing expired right now';
  const isBusy = activeAction !== null;

  return (
    <>
      <Card className="overflow-hidden border-border/80 bg-card/95">
        <CardHeader className="gap-4 border-b border-border/80 bg-muted/20">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
            <div className="space-y-3">
              <div className="flex flex-wrap items-center gap-2">
                <CardTitle className="text-base">Search cache</CardTitle>
                <Badge variant={stats.enabled ? 'success' : 'secondary'}>
                  {stats.enabled ? 'Active' : 'Inactive'}
                </Badge>
                <Badge variant={stats.db_exists ? 'outline' : 'warning'}>
                  {stats.db_exists ? 'Database ready' : 'Database pending'}
                </Badge>
                <Badge variant={health.tone}>{health.label}</Badge>
              </div>
              <div className="space-y-1">
                <CardDescription>{health.headline}</CardDescription>
                <p className="max-w-3xl text-sm text-muted-foreground">{health.detail}</p>
              </div>
            </div>

            <div className="flex flex-wrap gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={handleRefresh}
                disabled={isBusy}
              >
                {activeAction === 'refresh' ? 'Refreshing…' : 'Refresh'}
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={handlePurgeExpired}
                disabled={isBusy || !stats.enabled || stats.expired_entries === 0}
              >
                {activeAction === 'purge'
                  ? 'Purging…'
                  : stats.expired_entries > 0
                    ? `Purge expired only (${stats.expired_entries})`
                    : 'No expired entries'}
              </Button>
              <Button
                variant="destructive"
                size="sm"
                onClick={() => setShowClearConfirm(true)}
                disabled={isBusy || !stats.enabled || stats.total_entries === 0}
              >
                Clear all cached results
              </Button>
            </div>
          </div>
        </CardHeader>

        <CardContent className="space-y-5 pt-6">
          {statsError ? (
            <Alert variant="destructive">
              <AlertTitle>Stats refresh failed</AlertTitle>
              <AlertDescription>{statsError}</AlertDescription>
            </Alert>
          ) : null}

          {actionError ? (
            <Alert variant="destructive">
              <AlertTitle>Cache action failed</AlertTitle>
              <AlertDescription>{actionError}</AlertDescription>
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
                Enable the cache in the config editor above if you want identical searches to reuse previous results instead of calling the provider again every time.
              </AlertDescription>
            </Alert>
          ) : null}

          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
            <CacheMetric label="Approx. size" value={formatBytes(stats.approximate_size_bytes)} />
            <CacheMetric
              label="Capacity used"
              value={`${stats.total_entries.toLocaleString()} / ${stats.max_entries.toLocaleString()}`}
              detail={formatPercent(capacityRatio)}
              emphasis={capacityRatio >= 90 ? 'warning' : 'default'}
            />
            <CacheMetric
              label="Reusable now"
              value={stats.active_entries.toLocaleString()}
              detail={stats.total_entries > 0 ? formatPercent(activeRatio) : '0% of entries'}
              emphasis="success"
            />
            <CacheMetric
              label="Expired backlog"
              value={stats.expired_entries.toLocaleString()}
              detail={stats.total_entries > 0 ? formatPercent(expiredRatio) : '0% of entries'}
              emphasis={stats.expired_entries > 0 ? 'warning' : 'default'}
            />
            <CacheMetric label="TTL" value={formatTtl(stats.ttl_seconds)} detail="Configured retention" />
            <CacheMetric label="Total hits" value={stats.total_hits.toLocaleString()} detail="Repeat searches served from cache" />
            <CacheMetric
              label="Reuse ratio"
              value={`${approximateReuseRatio}x`}
              detail="Hits per cached entry"
              emphasis={approximateReuseRatio > 0 ? 'success' : 'default'}
            />
            <CacheMetric
              label="Database"
              value={stats.db_exists ? 'Ready' : 'Pending'}
              detail={safeCleanupLabel}
              emphasis={stats.db_exists ? 'default' : 'warning'}
            />
          </div>

          <div className="grid gap-4 xl:grid-cols-[1.2fr_0.8fr]">
            <div className="rounded-[1.2rem] border border-border bg-background/55 p-4">
              <div className="space-y-1">
                <div className="text-sm font-medium">How to read this cache</div>
                <p className="text-sm text-muted-foreground">
                  Active entries can still satisfy repeat searches. Expired entries explain why a query may no longer reuse older results, and they are the safest things to clean up first.
                </p>
              </div>
              <div className="mt-4 grid gap-3 md:grid-cols-2">
                <ActionFrame
                  tone="success"
                  title="Low-risk cleanup"
                  description={
                    stats.expired_entries > 0
                      ? `Purging expired entries only removes results already outside the ${formatTtl(stats.ttl_seconds)} TTL. It does not touch currently reusable cache hits.`
                      : 'There are no expired entries right now, so there is nothing safe-and-obvious to purge.'
                  }
                />
                <ActionFrame
                  tone="warning"
                  title="High-impact reset"
                  description={
                    stats.total_entries > 0
                      ? `Clear all deletes every cached result, including ${stats.active_entries.toLocaleString()} entries that could still satisfy repeat research. The next identical search will hit the provider again.`
                      : 'Clear all stays disabled until the cache holds entries.'
                  }
                />
              </div>
            </div>

            <div className="rounded-[1.2rem] border border-border bg-background/55 p-4">
              <div className="space-y-1">
                <div className="text-sm font-medium">Cache database</div>
                <p className="text-sm text-muted-foreground">
                  This is the local SQLite file backing search reuse across runs on this machine.
                </p>
              </div>
              <div className="mt-4 flex flex-wrap items-center gap-2">
                <Badge variant={stats.db_exists ? 'success' : 'warning'}>
                  {stats.db_exists ? 'Ready for reads and writes' : 'Created on first write'}
                </Badge>
                <Badge variant="outline">Max {stats.max_entries.toLocaleString()} entries</Badge>
              </div>
              <p className="mt-4 break-all rounded-lg border border-border/80 bg-surface/60 px-3 py-2 font-mono text-xs text-muted-foreground">
                {stats.db_path}
              </p>
            </div>
          </div>

          <div className="rounded-[1.2rem] border border-border bg-background/55 p-4">
            <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
              <div className="space-y-1">
                <div className="flex flex-wrap items-center gap-2">
                  <div className="text-sm font-medium">Recent cache activity</div>
                  <Badge variant="info">Latest {RECENT_ENTRY_LIMIT}</Badge>
                </div>
                <p className="text-sm text-muted-foreground">
                  Use recent entries to connect stale or repeated research behavior to what is actually stored in the cache.
                </p>
              </div>

              <div className="flex flex-wrap gap-2">
                <Button
                  type="button"
                  variant={includeExpired ? 'outline' : 'ghost'}
                  size="sm"
                  onClick={() => setIncludeExpired(true)}
                  disabled={entriesLoading}
                >
                  Show active + expired
                </Button>
                <Button
                  type="button"
                  variant={!includeExpired ? 'outline' : 'ghost'}
                  size="sm"
                  onClick={() => setIncludeExpired(false)}
                  disabled={entriesLoading}
                >
                  Active only
                </Button>
              </div>
            </div>

            {entriesError ? (
              <Alert variant="destructive" className="mt-4">
                <AlertTitle>Recent entries unavailable</AlertTitle>
                <AlertDescription>{entriesError}</AlertDescription>
              </Alert>
            ) : null}

            {entriesLoading && entries.length === 0 ? (
              <Alert className="mt-4" variant="default">
                <AlertTitle>Loading recent entries</AlertTitle>
                <AlertDescription>Gathering the latest cached queries and their reuse status.</AlertDescription>
              </Alert>
            ) : null}

            {!entriesLoading && entries.length === 0 ? (
              <div className="mt-4 rounded-xl border border-dashed border-border/80 bg-surface/40 px-4 py-6">
                <div className="text-sm font-medium">
                  {entriesMessage ?? (includeExpired ? 'No recent cache entries to review.' : 'No active cache entries are currently reusable.')}
                </div>
                <p className="mt-2 text-sm text-muted-foreground">
                  {stats.enabled
                    ? includeExpired
                      ? 'Run new research or refresh after the first cached queries land here. If you recently cleared the cache, this empty state is expected.'
                      : 'Either the cache is empty or every stored result has already expired. Switch to "Show active + expired" to inspect stale entries before purging.'
                    : 'The cache list stays empty until search caching is enabled.'}
                </p>
              </div>
            ) : null}

            {entries.length > 0 ? (
              <div className="mt-4 grid gap-3">
                {entries.map((entry) => {
                  const entryState = getEntryState(entry);

                  return (
                    <article
                      key={entry.cache_key}
                      className="rounded-xl border border-border/85 bg-card/70 p-4 shadow-[inset_0_1px_0_rgba(255,255,255,0.02)]"
                    >
                      <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                        <div className="space-y-2">
                          <div className="flex flex-wrap items-center gap-2">
                            <Badge variant="outline">{entry.provider}</Badge>
                            <Badge variant={entryState.tone}>{entryState.label}</Badge>
                            <Badge variant={entry.hit_count > 0 ? 'success' : 'secondary'}>
                              {describeReuse(entry)}
                            </Badge>
                          </div>
                          <div className="max-w-3xl text-sm font-medium leading-6 text-foreground">
                            {entry.normalized_query}
                          </div>
                          <p className="font-mono text-[11px] text-muted-foreground">
                            Key {shortenCacheKey(entry.cache_key)}
                          </p>
                        </div>

                        <Button
                          type="button"
                          variant="ghost"
                          size="sm"
                          onClick={() => setPendingDeleteEntry(entry)}
                          disabled={isBusy}
                        >
                          Delete entry
                        </Button>
                      </div>

                      <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
                        <EntryMetric
                          label="Last accessed"
                          value={formatRelativeTime(entry.last_accessed_at)}
                          detail={formatDateTime(entry.last_accessed_at)}
                        />
                        <EntryMetric
                          label="Expires"
                          value={entry.is_expired ? 'Expired' : formatRelativeTime(entry.expires_at)}
                          detail={formatDateTime(entry.expires_at)}
                        />
                        <EntryMetric
                          label="Created"
                          value={formatRelativeTime(entry.created_at)}
                          detail={formatDateTime(entry.created_at)}
                        />
                        <EntryMetric
                          label="Cache hits"
                          value={entry.hit_count.toLocaleString()}
                          detail={entry.hit_count > 0 ? 'Repeated searches reused this result.' : 'No repeat lookups yet.'}
                        />
                      </div>

                      <p className="mt-4 text-sm text-muted-foreground">{entryState.detail}</p>
                    </article>
                  );
                })}
              </div>
            ) : null}
          </div>
        </CardContent>
      </Card>

      <AlertDialog
        open={showClearConfirm}
        onOpenChange={setShowClearConfirm}
        title="Clear all cached search results?"
        description={
          <>
            This removes <strong>{stats.total_entries.toLocaleString()}</strong> cached search
            {stats.total_entries === 1 ? ' result' : ' results'}, including{' '}
            <strong>{stats.active_entries.toLocaleString()}</strong>{' '}
            {stats.active_entries === 1 ? 'entry' : 'entries'} that could still satisfy repeat research. The next identical search will hit the upstream provider again and rebuild the cache from scratch.
          </>
        }
        confirmLabel="Clear all results"
        destructive
        loading={activeAction === 'clear'}
        loadingLabel="Clearing…"
        onConfirm={handleClearCache}
      />

      <AlertDialog
        open={pendingDeleteEntry !== null}
        onOpenChange={(open) => {
          if (!open) {
            setPendingDeleteEntry(null);
          }
        }}
        title="Delete this cached result?"
        description={
          pendingDeleteEntry ? (
            <>
              This removes the cached result for <strong>{pendingDeleteEntry.normalized_query}</strong>. Only this entry is deleted, so other cache entries remain untouched. The next identical search for this query will go back to the provider until it is cached again.
            </>
          ) : (
            'This removes one cached result.'
          )
        }
        confirmLabel="Delete entry"
        destructive
        loading={activeAction === 'delete'}
        loadingLabel="Deleting…"
        onConfirm={handleDeleteEntry}
      />
    </>
  );
}

function CacheMetric({
  label,
  value,
  detail,
  emphasis = 'default',
}: {
  label: string;
  value: string;
  detail?: string;
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
      {detail ? <div className="mt-1 text-xs text-muted-foreground">{detail}</div> : null}
    </div>
  );
}

function ActionFrame({
  title,
  description,
  tone,
}: {
  title: string;
  description: string;
  tone: 'success' | 'warning';
}) {
  return (
    <div
      className={
        tone === 'success'
          ? 'rounded-xl border border-success/25 bg-success-muted/20 p-4'
          : 'rounded-xl border border-warning/25 bg-warning-muted/20 p-4'
      }
    >
      <div className="text-sm font-medium">{title}</div>
      <p className="mt-2 text-sm text-muted-foreground">{description}</p>
    </div>
  );
}

function EntryMetric({
  label,
  value,
  detail,
}: {
  label: string;
  value: string;
  detail: string;
}) {
  return (
    <div className="rounded-lg border border-border/70 bg-background/45 px-3 py-2">
      <div className="text-[11px] uppercase tracking-[0.18em] text-muted-foreground">{label}</div>
      <div className="mt-2 text-sm font-medium text-foreground">{value}</div>
      <div className="mt-1 text-xs text-muted-foreground">{detail}</div>
    </div>
  );
}
