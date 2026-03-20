'use client';

import { startTransition, useEffect, useState } from 'react';

import { Button } from '@/components/ui/button';
import {
  getSearchCacheStats,
  purgeExpiredSearchCacheEntries,
  clearSearchCache,
  getApiErrorMessage,
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

  const loadStats = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await getSearchCacheStats();
      startTransition(() => {
        setStats(response);
      });
    } catch (err) {
      setError(getApiErrorMessage(err, 'Failed to load cache stats.'));
    } finally {
      setLoading(false);
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
      await loadStats();
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
      await loadStats();
    } catch (err) {
      setError(getApiErrorMessage(err, 'Failed to clear cache.'));
    } finally {
      setActionLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="rounded-2xl border border-border bg-card p-5 shadow-sm">
        <h2 className="text-base font-semibold">Search cache</h2>
        <p className="mt-2 text-sm text-muted-foreground">Loading cache stats…</p>
      </div>
    );
  }

  if (error && !stats) {
    return (
      <div className="rounded-2xl border border-destructive/30 bg-card p-5 shadow-sm">
        <h2 className="text-base font-semibold">Search cache</h2>
        <p className="mt-2 text-sm text-destructive">{error}</p>
        <Button variant="outline" size="sm" className="mt-3" onClick={loadStats}>
          Retry
        </Button>
      </div>
    );
  }

  if (!stats) {
    return null;
  }

  return (
    <div className="space-y-4 rounded-2xl border border-border bg-card p-5 shadow-sm">
      <div className="flex items-start justify-between">
        <div>
          <h2 className="text-base font-semibold">Search cache</h2>
          <p className="mt-1 text-sm text-muted-foreground">
            {stats.enabled ? 'Cache is enabled' : 'Cache is disabled'}
          </p>
        </div>
        <span
          className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${
            stats.enabled
              ? 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200'
              : 'bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400'
          }`}
        >
          {stats.enabled ? 'Active' : 'Inactive'}
        </span>
      </div>

      {error && (
        <div className="rounded-lg border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
          {error}
        </div>
      )}

      {actionMessage && (
        <div className="rounded-lg border border-green-300/50 bg-green-50 px-3 py-2 text-sm text-green-800 dark:bg-green-900/30 dark:text-green-200">
          {actionMessage}
        </div>
      )}

      {stats.enabled && (
        <>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <div className="rounded-xl border border-border bg-background/50 px-3 py-2">
              <div className="text-xs text-muted-foreground">Total entries</div>
              <div className="text-lg font-semibold">{stats.total_entries}</div>
            </div>
            <div className="rounded-xl border border-border bg-background/50 px-3 py-2">
              <div className="text-xs text-muted-foreground">Active entries</div>
              <div className="text-lg font-semibold text-green-600 dark:text-green-400">
                {stats.active_entries}
              </div>
            </div>
            <div className="rounded-xl border border-border bg-background/50 px-3 py-2">
              <div className="text-xs text-muted-foreground">Expired entries</div>
              <div className="text-lg font-semibold text-amber-600 dark:text-amber-400">
                {stats.expired_entries}
              </div>
            </div>
            <div className="rounded-xl border border-border bg-background/50 px-3 py-2">
              <div className="text-xs text-muted-foreground">Total hits</div>
              <div className="text-lg font-semibold">{stats.total_hits}</div>
            </div>
          </div>

          <div className="grid gap-3 sm:grid-cols-3">
            <div className="rounded-xl border border-border bg-background/50 px-3 py-2">
              <div className="text-xs text-muted-foreground">TTL</div>
              <div className="text-sm font-medium">{formatTtl(stats.ttl_seconds)}</div>
            </div>
            <div className="rounded-xl border border-border bg-background/50 px-3 py-2">
              <div className="text-xs text-muted-foreground">Max entries</div>
              <div className="text-sm font-medium">{stats.max_entries.toLocaleString()}</div>
            </div>
            <div className="rounded-xl border border-border bg-background/50 px-3 py-2">
              <div className="text-xs text-muted-foreground">Size</div>
              <div className="text-sm font-medium">{formatBytes(stats.approximate_size_bytes)}</div>
            </div>
          </div>

          <div className="flex flex-wrap gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={handlePurgeExpired}
              disabled={actionLoading || stats.expired_entries === 0}
            >
              {actionLoading ? 'Working…' : `Purge expired (${stats.expired_entries})`}
            </Button>
            {!showClearConfirm ? (
              <Button
                variant="outline"
                size="sm"
                onClick={() => setShowClearConfirm(true)}
                disabled={actionLoading || stats.total_entries === 0}
                className="text-destructive hover:bg-destructive hover:text-destructive-foreground"
              >
                Clear all
              </Button>
            ) : (
              <div className="flex gap-2">
                <Button
                  variant="destructive"
                  size="sm"
                  onClick={handleClearCache}
                  disabled={actionLoading}
                >
                  Confirm clear
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setShowClearConfirm(false)}
                  disabled={actionLoading}
                >
                  Cancel
                </Button>
              </div>
            )}
          </div>
        </>
      )}

      {!stats.enabled && (
        <p className="text-sm text-muted-foreground">
          Enable the search cache in the config editor to reduce API costs by reusing search results.
        </p>
      )}

      <div className="text-xs text-muted-foreground">
        Database: {stats.db_path}
        {stats.db_exists ? '' : ' (not yet created)'}
      </div>
    </div>
  );
}
