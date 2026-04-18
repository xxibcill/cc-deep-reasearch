'use client';

import * as React from 'react';
import { useEffect, useState } from 'react';
import { Plus, Radar, AlertCircle, RefreshCw, ExternalLink, Trash2 } from 'lucide-react';

import { Badge } from '@/components/ui/badge';
import { Button, buttonVariants } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { EmptyState } from '@/components/ui/empty-state';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog';
import {
  getApiErrorMessage,
  getRadarSources,
  createRadarSource,
  type CreateRadarSourceRequest,
} from '@/lib/api';
import type { RadarSource } from '@/types/radar';

const SOURCE_TYPE_OPTIONS = [
  { value: 'news', label: 'News Feed' },
  { value: 'blog', label: 'Blog' },
  { value: 'changelog', label: 'Changelog' },
  { value: 'forum', label: 'Forum' },
  { value: 'social', label: 'Social Media' },
  { value: 'competitor', label: 'Competitor Site' },
  { value: 'custom', label: 'Custom URL' },
] as const;

const STATUS_CONFIG = {
  active: { label: 'Active', variant: 'success' as const },
  inactive: { label: 'Inactive', variant: 'secondary' as const },
  error: { label: 'Error', variant: 'destructive' as const },
};

function SourceRow({ source }: { source: RadarSource }) {
  const status = STATUS_CONFIG[source.status] ?? STATUS_CONFIG.inactive;

  return (
    <div className="flex items-start justify-between gap-4 rounded-xl border border-border/50 p-4">
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium text-foreground">{source.label}</span>
          <Badge variant={status.variant} className="text-[0.62rem]">
            {status.label}
          </Badge>
          <Badge variant="outline" className="text-[0.62rem] capitalize">
            {source.sourceType}
          </Badge>
        </div>
        <p className="mt-1 truncate text-xs text-muted-foreground">
          {source.urlOrIdentifier}
        </p>
        <div className="mt-2 flex flex-wrap items-center gap-3 text-[0.62rem] text-muted-foreground">
          <span>Cadence: {source.scanCadence}</span>
          {source.lastScannedAt && (
            <span>Last scan: {new Date(source.lastScannedAt).toLocaleString()}</span>
          )}
          <span>Created {new Date(source.createdAt).toLocaleDateString()}</span>
        </div>
      </div>
      {source.urlOrIdentifier.startsWith('http') && (
        <a
          href={source.urlOrIdentifier}
          target="_blank"
          rel="noopener noreferrer"
          className={buttonVariants({ variant: 'ghost', size: 'sm' }) + ' shrink-0 h-auto p-1.5'}
          aria-label={`Open ${source.label}`}
        >
          <ExternalLink className="h-3.5 w-3.5" />
        </a>
      )}
    </div>
  );
}

function AddSourceDialog({
  open,
  onOpenChange,
  onCreated,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onCreated: (source: RadarSource) => void;
}) {
  const [label, setLabel] = useState('');
  const [url, setUrl] = useState('');
  const [sourceType, setSourceType] = useState<string>('news');
  const [cadence, setCadence] = useState('6h');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!label.trim() || !url.trim()) return;

    setLoading(true);
    setError(null);
    try {
      const request: CreateRadarSourceRequest = {
        source_type: sourceType,
        label: label.trim(),
        url_or_identifier: url.trim(),
        scan_cadence: cadence,
      };
      const created = await createRadarSource(request);
      onCreated(created);
      setLabel('');
      setUrl('');
      setSourceType('news');
      setCadence('6h');
      onOpenChange(false);
    } catch (err) {
      setError(getApiErrorMessage(err, 'Failed to create source.'));
    } finally {
      setLoading(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Add Radar Source</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-4">
          {error && (
            <div className="rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">
              {error}
            </div>
          )}

          <div className="space-y-2">
            <Label htmlFor="source-label">Label</Label>
            <Input
              id="source-label"
              value={label}
              onChange={(e) => setLabel(e.target.value)}
              placeholder="Anthropic News Feed"
              required
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="source-url">URL or Identifier</Label>
            <Input
              id="source-url"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              placeholder="https://www.anthropic.com/news/rss"
              required
            />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="source-type">Source Type</Label>
              <select
                id="source-type"
                value={sourceType}
                onChange={(e) => setSourceType(e.target.value)}
                className="w-full rounded-lg border border-border/60 bg-background px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-ring"
              >
                {SOURCE_TYPE_OPTIONS.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </select>
            </div>

            <div className="space-y-2">
              <Label htmlFor="source-cadence">Scan Cadence</Label>
              <select
                id="source-cadence"
                value={cadence}
                onChange={(e) => setCadence(e.target.value)}
                className="w-full rounded-lg border border-border/60 bg-background px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-ring"
              >
                <option value="1h">Every hour</option>
                <option value="2h">Every 2 hours</option>
                <option value="6h">Every 6 hours</option>
                <option value="12h">Every 12 hours</option>
                <option value="1d">Daily</option>
                <option value="1w">Weekly</option>
              </select>
            </div>
          </div>

          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={loading || !label.trim() || !url.trim()}>
              {loading ? 'Creating...' : 'Create Source'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function SourcesListSkeleton() {
  return (
    <div className="space-y-3">
      {[...Array(3)].map((_, i) => (
        <div key={i} className="flex items-start justify-between gap-4 rounded-xl border border-border/40 p-4">
          <div className="min-w-0 flex-1 space-y-2">
            <div className="skeleton h-4 w-48 animate-pulse rounded-md bg-muted" />
            <div className="skeleton h-3 w-full animate-pulse rounded-md bg-muted" />
          </div>
          <div className="skeleton h-4 w-16 animate-pulse rounded-md bg-muted" />
        </div>
      ))}
    </div>
  );
}

export default function SourcesPage() {
  const [sources, setSources] = useState<RadarSource[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isAddDialogOpen, setIsAddDialogOpen] = useState(false);

  useEffect(() => {
    let mounted = true;

    const load = async () => {
      setLoading(true);
      setError(null);
      try {
        const result = await getRadarSources();
        if (!mounted) return;
        setSources(result.sources);
      } catch (err) {
        console.error('Failed to load radar sources:', err);
        if (mounted) {
          setError(getApiErrorMessage(err, 'Failed to load sources.'));
        }
      } finally {
        if (mounted) setLoading(false);
      }
    };

    void load();
    return () => {
      mounted = false;
    };
  }, []);

  const handleSourceCreated = (source: RadarSource) => {
    setSources((prev) => [source, ...prev]);
  };

  return (
    <div className="mx-auto max-w-content px-page-x py-page-y">
      <div className="space-y-8">
        <div className="space-y-4">
          <p className="eyebrow">Opportunity Radar</p>
          <div className="flex flex-wrap items-end justify-between gap-4">
            <div>
              <h1 className="font-display text-[clamp(2.8rem,6vw,4.8rem)] font-semibold uppercase tracking-[0.01em] text-foreground">
                Source Management
              </h1>
              <p className="mt-2 max-w-2xl text-base leading-7 text-muted-foreground sm:text-lg">
                Configure and monitor the sources that Radar watches for opportunities.
              </p>
            </div>
            <Button onClick={() => setIsAddDialogOpen(true)}>
              <Plus className="mr-2 h-4 w-4" />
              Add Source
            </Button>
          </div>
        </div>

        <Card className="rounded-[1.45rem]">
          <CardHeader className="border-b border-border/70">
            <CardTitle className="text-[1.6rem]">Monitored Sources</CardTitle>
          </CardHeader>
          <CardContent className="pt-5">
            {loading ? (
              <SourcesListSkeleton />
            ) : error && sources.length === 0 ? (
              <EmptyState
                description={error}
                icon={AlertCircle}
                title="Failed to load sources"
              />
            ) : sources.length === 0 ? (
              <EmptyState
                description="No sources configured yet. Add your first source to start monitoring."
                icon={Radar}
                title="No sources"
              />
            ) : (
              <div className="space-y-3">
                {sources.map((source) => (
                  <SourceRow key={source.id} source={source} />
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      <AddSourceDialog
        open={isAddDialogOpen}
        onOpenChange={setIsAddDialogOpen}
        onCreated={handleSourceCreated}
      />
    </div>
  );
}