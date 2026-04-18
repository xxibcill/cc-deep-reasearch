'use client';

import Link from 'next/link';
import { useEffect, useState } from 'react';
import {
  Radar,
  AlertCircle,
  Clock,
  TrendingUp,
  Filter,
  ChevronRight,
  Inbox,
} from 'lucide-react';

import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { EmptyState } from '@/components/ui/empty-state';
import { MetricCard } from '@/components/ui/metric-card';
import { getApiErrorMessage, getRadarOpportunities } from '@/lib/api';
import type { Opportunity, OpportunityListResult } from '@/types/radar';

const PRIORITY_CONFIG = {
  act_now: { label: 'Act Now', variant: 'destructive' as const },
  high_potential: { label: 'High Potential', variant: 'default' as const },
  monitor: { label: 'Monitor', variant: 'secondary' as const },
  low_priority: { label: 'Low Priority', variant: 'outline' as const },
};

const FRESHNESS_CONFIG = {
  new: { label: 'New', variant: 'info' as const },
  fresh: { label: 'Fresh', variant: 'success' as const },
  stale: { label: 'Stale', variant: 'warning' as const },
  expired: { label: 'Expired', variant: 'secondary' as const },
};

const STATUS_CONFIG = {
  new: { label: 'New', variant: 'info' as const },
  saved: { label: 'Saved', variant: 'default' as const },
  acted_on: { label: 'Acted On', variant: 'success' as const },
  monitoring: { label: 'Monitoring', variant: 'secondary' as const },
  dismissed: { label: 'Dismissed', variant: 'outline' as const },
  archived: { label: 'Archived', variant: 'secondary' as const },
};

function OpportunityRow({ opportunity }: { opportunity: Opportunity }) {
  const priority = PRIORITY_CONFIG[opportunity.priorityLabel] ?? PRIORITY_CONFIG.monitor;
  const freshness = FRESHNESS_CONFIG[opportunity.freshnessState] ?? FRESHNESS_CONFIG.stale;
  const status = STATUS_CONFIG[opportunity.status] ?? STATUS_CONFIG.new;

  return (
    <Link href={`/radar/opportunities/${opportunity.id}`}>
      <div className="group flex items-start justify-between gap-4 rounded-xl border border-transparent p-4 transition-all hover:border-border/60 hover:bg-surface-raised/40">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <h3 className="truncate text-sm font-medium text-foreground group-hover:text-primary">
              {opportunity.title}
            </h3>
          </div>
          <p className="mt-1 line-clamp-2 text-xs text-muted-foreground">
            {opportunity.summary}
          </p>
          <div className="mt-2 flex flex-wrap items-center gap-1.5">
            <Badge variant={status.variant} className="text-[0.62rem]">
              {status.label}
            </Badge>
            <Badge variant={freshness.variant} className="text-[0.62rem]">
              {freshness.label}
            </Badge>
            <span className="text-[0.62rem] text-muted-foreground">
              {opportunity.opportunityType.replace(/_/g, ' ')}
            </span>
          </div>
        </div>
        <div className="flex shrink-0 flex-col items-end gap-1.5">
          <div className="flex items-center gap-1">
            <span
              className={`text-lg font-semibold ${
                opportunity.totalScore >= 80
                  ? 'text-destructive'
                  : opportunity.totalScore >= 60
                    ? 'text-primary'
                    : 'text-muted-foreground'
              }`}
            >
              {opportunity.totalScore.toFixed(0)}
            </span>
            <span className="text-[0.62rem] uppercase tracking-[0.12em] text-muted-foreground">
              pts
            </span>
          </div>
          <Badge variant={priority.variant} className="text-[0.62rem]">
            {priority.label}
          </Badge>
          <ChevronRight className="h-3.5 w-3.5 text-muted-foreground transition-transform group-hover:translate-x-0.5" />
        </div>
      </div>
    </Link>
  );
}

function OpportunityListSkeleton() {
  return (
    <div className="space-y-3">
      {[...Array(5)].map((_, i) => (
        <div key={i} className="flex items-start justify-between gap-4 rounded-xl border border-border/40 p-4">
          <div className="min-w-0 flex-1 space-y-2">
            <div className="skeleton h-4 w-48 animate-pulse rounded-md bg-muted" />
            <div className="skeleton h-3 w-full animate-pulse rounded-md bg-muted" />
            <div className="skeleton h-3 w-3/4 animate-pulse rounded-md bg-muted" />
          </div>
          <div className="space-y-2 text-right">
            <div className="skeleton h-6 w-12 animate-pulse rounded-md bg-muted" />
            <div className="skeleton h-4 w-20 animate-pulse rounded-md bg-muted" />
          </div>
        </div>
      ))}
    </div>
  );
}

export default function RadarPage() {
  const [result, setResult] = useState<OpportunityListResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<string>('all');

  useEffect(() => {
    let mounted = true;

    const load = async () => {
      setLoading(true);
      setError(null);
      try {
        const data = await getRadarOpportunities(
          filter !== 'all' ? { status: filter } : undefined
        );
        if (!mounted) return;
        setResult(data);
      } catch (err) {
        console.error('Failed to load radar opportunities:', err);
        if (mounted) {
          setError(getApiErrorMessage(err, 'Failed to load opportunities.'));
        }
      } finally {
        if (mounted) setLoading(false);
      }
    };

    void load();
    return () => {
      mounted = false;
    };
  }, [filter]);

  const actNow = result?.opportunities.filter((o) => o.priorityLabel === 'act_now') ?? [];
  const highPotential = result?.opportunities.filter((o) => o.priorityLabel === 'high_potential') ?? [];
  const monitorCount = result?.opportunities.filter((o) => o.priorityLabel === 'monitor').length ?? 0;
  const newCount = result?.opportunities.filter((o) => o.freshnessState === 'new').length ?? 0;

  return (
    <div className="mx-auto max-w-content px-page-x py-page-y">
      <div className="space-y-8">
        <div className="space-y-4">
          <p className="eyebrow">Opportunity Radar</p>
          <div className="flex flex-wrap items-end justify-between gap-4">
            <div>
              <h1 className="font-display text-[clamp(2.8rem,6vw,4.8rem)] font-semibold uppercase tracking-[0.01em] text-foreground">
                Radar Inbox
              </h1>
              <p className="mt-2 max-w-2xl text-base leading-7 text-muted-foreground sm:text-lg">
                Detected opportunities ranked by strategic value and freshness.
              </p>
            </div>
          </div>
        </div>

        <div className="grid gap-4 md:grid-cols-4">
          <MetricCard
            description="Requires immediate attention"
            icon={AlertCircle}
            label="Act Now"
            tone="warning"
            value={loading ? '...' : actNow.length}
          />
          <MetricCard
            description="High strategic value"
            icon={TrendingUp}
            label="High Potential"
            tone="primary"
            value={loading ? '...' : highPotential.length}
          />
          <MetricCard
            description="Under active observation"
            icon={Clock}
            label="Monitor"
            tone="warning"
            value={loading ? '...' : monitorCount}
          />
          <MetricCard
            description="Just detected"
            icon={Radar}
            label="New"
            tone="success"
            value={loading ? '...' : newCount}
          />
        </div>

        <Card className="rounded-[1.45rem]">
          <CardHeader className="border-b border-border/70">
            <div className="flex items-center justify-between">
              <CardTitle className="text-[1.6rem]">All Opportunities</CardTitle>
              <div className="flex items-center gap-2">
                <Filter className="h-4 w-4 text-muted-foreground" />
                <select
                  value={filter}
                  onChange={(e) => setFilter(e.target.value)}
                  className="rounded-lg border border-border/60 bg-background px-3 py-1.5 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-ring"
                >
                  <option value="all">All statuses</option>
                  <option value="new">New</option>
                  <option value="saved">Saved</option>
                  <option value="monitoring">Monitoring</option>
                  <option value="acted_on">Acted On</option>
                  <option value="dismissed">Dismissed</option>
                  <option value="archived">Archived</option>
                </select>
              </div>
            </div>
          </CardHeader>
          <CardContent className="pt-5">
            {loading ? (
              <OpportunityListSkeleton />
            ) : error && !result ? (
              <EmptyState
                description={error}
                icon={AlertCircle}
                title="Failed to load"
              />
            ) : result?.opportunities.length === 0 ? (
              <EmptyState
                description="No opportunities detected yet. Configure sources to start monitoring."
                icon={Inbox}
                title="Inbox zero"
              />
            ) : (
              <div className="space-y-1">
                {result?.opportunities.map((opp) => (
                  <OpportunityRow key={opp.id} opportunity={opp} />
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}