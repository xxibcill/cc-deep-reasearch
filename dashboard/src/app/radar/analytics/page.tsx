'use client';

import * as React from 'react';
import Link from 'next/link';
import { useEffect, useState } from 'react';
import {
  Radar,
  TrendingUp,
  Clock,
  BarChart3,
  AlertCircle,
  CheckCircle2,
  Loader2,
} from 'lucide-react';

import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { EmptyState } from '@/components/ui/empty-state';
import { MetricCard } from '@/components/ui/metric-card';
import { getApiErrorMessage } from '@/lib/api';

interface RadarAnalytics {
  total_opportunities: number;
  opportunities_by_status: Record<string, number>;
  opportunities_by_type: Record<string, number>;
  feedback_counts: Record<string, number>;
  conversion_rates: Record<string, number>;
  avg_time_to_action_hours: number | null;
  top_opportunity_types: [string, number][];
}

interface ConversionFunnel {
  funnel: { stage: string; label: string; count: number }[];
  total: number;
}

interface ScoreDistribution {
  distribution: Record<string, number>;
  total: number;
  avg_score: number;
}

const STATUS_LABELS: Record<string, string> = {
  new: 'New',
  saved: 'Saved',
  acted_on: 'Acted On',
  monitoring: 'Monitoring',
  dismissed: 'Dismissed',
  archived: 'Archived',
};

export default function RadarAnalyticsPage() {
  const [analytics, setAnalytics] = useState<RadarAnalytics | null>(null);
  const [funnel, setFunnel] = useState<ConversionFunnel | null>(null);
  const [scoreDist, setScoreDist] = useState<ScoreDistribution | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;

    const load = async () => {
      setLoading(true);
      setError(null);
      try {
        const [analyticsRes, funnelRes, scoreRes] = await Promise.all([
          fetch(`${process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000'}/api/radar/analytics`),
          fetch(`${process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000'}/api/radar/analytics/funnel`),
          fetch(`${process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000'}/api/radar/analytics/score-distribution`),
        ]);

        if (!analyticsRes.ok || !funnelRes.ok || !scoreRes.ok) {
          throw new Error('Failed to load analytics data');
        }

        const [analyticsData, funnelData, scoreData] = await Promise.all([
          analyticsRes.json(),
          funnelRes.json(),
          scoreRes.json(),
        ]);

        if (!mounted) return;
        setAnalytics(analyticsData);
        setFunnel(funnelData);
        setScoreDist(scoreData);
      } catch (err) {
        console.error('Failed to load radar analytics:', err);
        if (mounted) {
          setError(getApiErrorMessage(err, 'Failed to load analytics.'));
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

  if (loading) {
    return (
      <div className="mx-auto max-w-content px-page-x py-page-y">
        <div className="flex items-center justify-center py-20">
          <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
        </div>
      </div>
    );
  }

  if (error && !analytics) {
    return (
      <div className="mx-auto max-w-content px-page-x py-page-y">
        <EmptyState
          description={error}
          icon={AlertCircle}
          title="Failed to load analytics"
        />
      </div>
    );
  }

  if (!analytics || !funnel || !scoreDist) return null;

  const actedOnCount = analytics.opportunities_by_status['acted_on'] || 0;
  const totalConverted = (analytics.conversion_rates['research_run'] || 0) * actedOnCount;
  const actedOnPercent = analytics.total_opportunities > 0
    ? (actedOnCount / analytics.total_opportunities) * 100
    : 0;

  return (
    <div className="mx-auto max-w-content px-page-x py-page-y">
      <div className="space-y-8">
        <div className="space-y-4">
          <p className="eyebrow">Radar</p>
          <div className="flex flex-wrap items-end justify-between gap-4">
            <div>
              <h1 className="font-display text-[clamp(2.8rem,6vw,4.8rem)] font-semibold uppercase tracking-[0.01em] text-foreground">
                Analytics
              </h1>
              <p className="mt-2 max-w-2xl text-base leading-7 text-muted-foreground sm:text-lg">
                Radar performance metrics and conversion insights for operators.
              </p>
            </div>
          </div>
        </div>

        {/* Summary Metrics */}
        <div className="grid gap-4 md:grid-cols-4">
          <MetricCard
            description="Total opportunities detected"
            icon={Radar}
            label="Total Opportunities"
            tone="primary"
            value={loading ? '...' : analytics.total_opportunities}
          />
          <MetricCard
            description="Opportunities acted upon"
            icon={CheckCircle2}
            label="Acted On"
            tone="success"
            value={loading ? '...' : actedOnCount}
          />
          <MetricCard
            description="Research runs launched"
            icon={TrendingUp}
            label="Research Conversions"
            tone="primary"
            value={loading ? '...' : Math.round(totalConverted)}
          />
          <MetricCard
            description="Hours from detection to action"
            icon={Clock}
            label="Avg Time to Action"
            tone="warning"
            value={loading ? '...' : analytics.avg_time_to_action_hours?.toFixed(1) || 'N/A'}
          />
        </div>

        <div className="grid gap-6 lg:grid-cols-2">
          {/* Conversion Funnel */}
          <Card className="rounded-[1.45rem]">
            <CardHeader className="border-b border-border/70">
              <CardTitle className="text-[1.4rem]">Conversion Funnel</CardTitle>
            </CardHeader>
            <CardContent className="pt-4">
              <div className="space-y-4">
                {funnel.funnel.map((stage, index) => {
                  const maxCount = Math.max(...funnel.funnel.map(s => s.count), 1);
                  const width = (stage.count / maxCount) * 100;

                  return (
                    <div key={stage.stage} className="space-y-2">
                      <div className="flex items-center justify-between text-sm">
                        <span className="font-medium">{stage.label}</span>
                        <span className="text-muted-foreground">{stage.count}</span>
                      </div>
                      <div className="h-3 w-full overflow-hidden rounded-full bg-muted">
                        <div
                          className="h-full rounded-full bg-primary transition-all"
                          style={{ width: `${width}%` }}
                        />
                      </div>
                      {index < funnel.funnel.length - 1 && (
                        <div className="flex justify-center">
                          <div className="h-4 w-px bg-border" />
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </CardContent>
          </Card>

          {/* Score Distribution */}
          <Card className="rounded-[1.45rem]">
            <CardHeader className="border-b border-border/70">
              <CardTitle className="text-[1.4rem]">Score Distribution</CardTitle>
            </CardHeader>
            <CardContent className="pt-4">
              <div className="space-y-4">
                <div className="flex items-center justify-between text-sm">
                  <span className="text-muted-foreground">Average Score</span>
                  <span className="font-semibold">{scoreDist.avg_score.toFixed(1)}</span>
                </div>
                <div className="space-y-2">
                  {Object.entries(scoreDist.distribution).reverse().map(([range, count]) => {
                    const width = scoreDist.total > 0 ? (count / scoreDist.total) * 100 : 0;
                    const color = range === '80-100' ? 'bg-destructive' :
                      range === '60-79' ? 'bg-primary' :
                        range === '40-59' ? 'bg-warning' : 'bg-muted-foreground';

                    return (
                      <div key={range} className="space-y-1">
                        <div className="flex items-center justify-between text-xs">
                          <span className="text-muted-foreground">{range}</span>
                          <span className="font-medium">{count}</span>
                        </div>
                        <div className="h-2 w-full overflow-hidden rounded-full bg-muted">
                          <div
                            className={`h-full rounded-full ${color} transition-all`}
                            style={{ width: `${width}%` }}
                          />
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Opportunities by Status and Type */}
        <div className="grid gap-6 lg:grid-cols-2">
          <Card className="rounded-[1.45rem]">
            <CardHeader className="border-b border-border/70">
              <CardTitle className="text-[1.4rem]">By Status</CardTitle>
            </CardHeader>
            <CardContent className="pt-4">
              <div className="space-y-3">
                {Object.entries(analytics.opportunities_by_status).map(([status, count]) => (
                  <div key={status} className="flex items-center justify-between">
                    <Badge variant="outline" className="capitalize">
                      {STATUS_LABELS[status] || status}
                    </Badge>
                    <span className="font-medium">{count}</span>
                  </div>
                ))}
                {Object.keys(analytics.opportunities_by_status).length === 0 && (
                  <p className="text-sm text-muted-foreground">No opportunities yet.</p>
                )}
              </div>
            </CardContent>
          </Card>

          <Card className="rounded-[1.45rem]">
            <CardHeader className="border-b border-border/70">
              <CardTitle className="text-[1.4rem]">By Type</CardTitle>
            </CardHeader>
            <CardContent className="pt-4">
              <div className="space-y-3">
                {analytics.top_opportunity_types.map(([type, count]) => (
                  <div key={type} className="flex items-center justify-between">
                    <Badge variant="outline" className="capitalize">
                      {type.replace(/_/g, ' ')}
                    </Badge>
                    <span className="font-medium">{count}</span>
                  </div>
                ))}
                {analytics.top_opportunity_types.length === 0 && (
                  <p className="text-sm text-muted-foreground">No opportunities yet.</p>
                )}
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Feedback Counts */}
        <Card className="rounded-[1.45rem]">
          <CardHeader className="border-b border-border/70">
            <CardTitle className="text-[1.4rem]">Feedback Summary</CardTitle>
          </CardHeader>
          <CardContent className="pt-4">
            <div className="grid gap-4 md:grid-cols-3 lg:grid-cols-6">
              {Object.entries(analytics.feedback_counts).map(([type, count]) => (
                <div key={type} className="flex items-center justify-between rounded-lg border border-border/50 p-3">
                  <span className="text-xs capitalize text-muted-foreground">
                    {type.replace(/_/g, ' ')}
                  </span>
                  <span className="font-semibold">{count}</span>
                </div>
              ))}
              {Object.keys(analytics.feedback_counts).length === 0 && (
                <p className="text-sm text-muted-foreground col-span-full">No feedback recorded yet.</p>
              )}
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
