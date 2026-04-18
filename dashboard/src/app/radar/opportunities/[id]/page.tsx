'use client';

import * as React from 'react';
import Link from 'next/link';
import { useEffect, useState } from 'react';
import {
  ArrowLeft,
  AlertCircle,
  Clock,
  CheckCircle2,
  Bookmark,
  Archive,
  MessageSquare,
  ExternalLink,
  ChevronRight,
  PlayCircle,
  FileText,
  ListChecks,
  Loader2,
} from 'lucide-react';
import { Breadcrumb } from '@/components/ui/breadcrumb';
import { Badge } from '@/components/ui/badge';
import { Button, buttonVariants } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { EmptyState } from '@/components/ui/empty-state';
import {
  getApiErrorMessage,
  getRadarOpportunityDetail,
  updateRadarOpportunityStatus,
  recordRadarOpportunityFeedback,
  launchRadarOpportunityResearch,
  launchRadarOpportunityBrief,
  launchRadarOpportunityBacklog,
  getRadarOpportunityHistory,
  type OpportunityStatusUpdate,
  type FeedbackTypeInput,
} from '@/lib/api';
import type { OpportunityDetail as OpportunityDetailType, OpportunityStatus } from '@/types/radar';
import type { StatusHistoryEntry } from '@/lib/api';

const PRIORITY_CONFIG = {
  act_now: { label: 'Act Now', variant: 'destructive' as const },
  high_potential: { label: 'High Potential', variant: 'default' as const },
  monitor: { label: 'Monitor', variant: 'secondary' as const },
  low_priority: { label: 'Low Priority', variant: 'outline' as const },
};

const STATUS_CONFIG = {
  new: { label: 'New', variant: 'info' as const },
  saved: { label: 'Saved', variant: 'default' as const },
  acted_on: { label: 'Acted On', variant: 'success' as const },
  monitoring: { label: 'Monitoring', variant: 'secondary' as const },
  dismissed: { label: 'Dismissed', variant: 'outline' as const },
  archived: { label: 'Archived', variant: 'secondary' as const },
};

const STATUS_TRANSITIONS: Record<OpportunityStatus, { label: string; icon: typeof CheckCircle2; status: OpportunityStatusUpdate }[]> = {
  new: [
    { label: 'Save', icon: Bookmark, status: 'saved' },
    { label: 'Start monitoring', icon: Clock, status: 'monitoring' },
    { label: 'Dismiss', icon: Archive, status: 'dismissed' },
  ],
  saved: [
    { label: 'Act on it', icon: CheckCircle2, status: 'acted_on' },
    { label: 'Start monitoring', icon: Clock, status: 'monitoring' },
    { label: 'Archive', icon: Archive, status: 'archived' },
  ],
  monitoring: [
    { label: 'Act on it', icon: CheckCircle2, status: 'acted_on' },
    { label: 'Save', icon: Bookmark, status: 'saved' },
    { label: 'Dismiss', icon: Archive, status: 'dismissed' },
  ],
  acted_on: [
    { label: 'Return to new', icon: ArrowLeft, status: 'new' },
  ],
  dismissed: [
    { label: 'Return to new', icon: ArrowLeft, status: 'new' },
  ],
  archived: [
    { label: 'Return to new', icon: ArrowLeft, status: 'new' },
  ],
};

function ScoreGauge({ score, label }: { score: number; label: string }) {
  const color =
    score >= 80 ? 'bg-destructive' : score >= 60 ? 'bg-primary' : score >= 40 ? 'bg-warning' : 'bg-muted-foreground';

  return (
    <div className="space-y-1.5">
      <div className="flex items-baseline justify-between">
        <span className="text-xs text-muted-foreground">{label}</span>
        <span className="font-mono text-sm font-medium">{score.toFixed(0)}</span>
      </div>
      <div className="h-1.5 w-full overflow-hidden rounded-full bg-muted">
        <div className={`h-full rounded-full ${color}`} style={{ width: `${score}%` }} />
      </div>
    </div>
  );
}

export default function OpportunityDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = React.use(params);
  const [detail, setDetail] = useState<OpportunityDetailType | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [statusUpdating, setStatusUpdating] = useState(false);
  const [feedbackUpdating, setFeedbackUpdating] = useState(false);
  const [feedbackError, setFeedbackError] = useState<string | null>(null);
  const [history, setHistory] = useState<StatusHistoryEntry[]>([]);
  const [workflowLaunching, setWorkflowLaunching] = useState<string | null>(null);
  const [launchMessage, setLaunchMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  useEffect(() => {
    let mounted = true;

    const load = async () => {
      setLoading(true);
      setError(null);
      try {
        const [data, historyData] = await Promise.all([
          getRadarOpportunityDetail(id),
          getRadarOpportunityHistory(id),
        ]);
        if (!mounted) return;
        setDetail(data);
        setHistory(historyData.entries);
      } catch (err) {
        console.error('Failed to load opportunity detail:', err);
        if (mounted) {
          setError(getApiErrorMessage(err, 'Failed to load opportunity.'));
        }
      } finally {
        if (mounted) setLoading(false);
      }
    };

    void load();
    return () => {
      mounted = false;
    };
  }, [id]);

  const handleStatusChange = async (status: OpportunityStatusUpdate) => {
    if (!detail || statusUpdating) return;
    setStatusUpdating(true);
    try {
      const updated = await updateRadarOpportunityStatus(id, status);
      setDetail((prev) =>
        prev
          ? {
              ...prev,
              opportunity: { ...prev.opportunity, status: updated.status },
            }
          : prev
      );
    } catch (err) {
      console.error('Failed to update status:', err);
    } finally {
      setStatusUpdating(false);
    }
  };

  const handleFeedback = async (feedbackType: FeedbackTypeInput) => {
    if (!detail || feedbackUpdating) return;
    setFeedbackError(null);
    setFeedbackUpdating(true);
    try {
      await recordRadarOpportunityFeedback(id, feedbackType);
    } catch (err) {
      console.error('Failed to record feedback:', err);
      setFeedbackError(getApiErrorMessage(err, 'Failed to record feedback.'));
    } finally {
      setFeedbackUpdating(false);
    }
  };

  const handleLaunchResearch = async () => {
    if (workflowLaunching) return;
    setWorkflowLaunching('research');
    setLaunchMessage(null);
    try {
      const result = await launchRadarOpportunityResearch(id);
      setLaunchMessage({
        type: 'success',
        text: `Research run launched: ${result.research_run_id}`,
      });
      // Refresh detail to get updated workflow links
      const updatedDetail = await getRadarOpportunityDetail(id);
      setDetail(updatedDetail);
      // Refresh history
      const historyData = await getRadarOpportunityHistory(id);
      setHistory(historyData.entries);
    } catch (err) {
      console.error('Failed to launch research:', err);
      setLaunchMessage({
        type: 'error',
        text: getApiErrorMessage(err, 'Failed to launch research.'),
      });
    } finally {
      setWorkflowLaunching(null);
    }
  };

  const handleLaunchBrief = async () => {
    if (workflowLaunching) return;
    setWorkflowLaunching('brief');
    setLaunchMessage(null);
    try {
      const result = await launchRadarOpportunityBrief(id);
      setLaunchMessage({
        type: 'success',
        text: `Brief created: ${result.brief_id}`,
      });
      // Refresh detail to get updated workflow links
      const updatedDetail = await getRadarOpportunityDetail(id);
      setDetail(updatedDetail);
    } catch (err) {
      console.error('Failed to create brief:', err);
      setLaunchMessage({
        type: 'error',
        text: getApiErrorMessage(err, 'Failed to create brief.'),
      });
    } finally {
      setWorkflowLaunching(null);
    }
  };

  const handleLaunchBacklog = async () => {
    if (workflowLaunching) return;
    setWorkflowLaunching('backlog');
    setLaunchMessage(null);
    try {
      const result = await launchRadarOpportunityBacklog(id);
      setLaunchMessage({
        type: 'success',
        text: `Added to backlog: ${result.backlog_item_id}`,
      });
      // Refresh detail to get updated workflow links
      const updatedDetail = await getRadarOpportunityDetail(id);
      setDetail(updatedDetail);
    } catch (err) {
      console.error('Failed to add to backlog:', err);
      setLaunchMessage({
        type: 'error',
        text: getApiErrorMessage(err, 'Failed to add to backlog.'),
      });
    } finally {
      setWorkflowLaunching(null);
    }
  };

  if (loading) {
    return (
      <div className="mx-auto max-w-content px-page-x py-page-y">
        <div className="space-y-6">
          <div className="skeleton h-8 w-64 animate-pulse rounded-md bg-muted" />
          <div className="grid gap-6 lg:grid-cols-[1fr_24rem]">
            <div className="space-y-6">
              <div className="skeleton h-48 animate-pulse rounded-xl bg-muted" />
              <div className="skeleton h-32 animate-pulse rounded-xl bg-muted" />
            </div>
            <div className="skeleton h-64 animate-pulse rounded-xl bg-muted" />
          </div>
        </div>
      </div>
    );
  }

  if (error && !detail) {
    return (
      <div className="mx-auto max-w-content px-page-x py-page-y">
        <EmptyState
          description={error}
          icon={AlertCircle}
          title="Failed to load opportunity"
          action={{ label: 'Back to inbox', href: '/radar' }}
        />
      </div>
    );
  }

  if (!detail) return null;

  const { opportunity, score, signals, feedback, workflowLinks } = detail;
  const priority = PRIORITY_CONFIG[opportunity.priorityLabel] ?? PRIORITY_CONFIG.monitor;
  const status = STATUS_CONFIG[opportunity.status] ?? STATUS_CONFIG.new;
  const transitions = STATUS_TRANSITIONS[opportunity.status] ?? [];

  return (
    <div className="mx-auto max-w-content px-page-x py-page-y">
      <div className="space-y-6">
        <Breadcrumb
          items={[
            { label: 'Radar', href: '/radar' },
            { label: opportunity.id },
          ]}
        />

        <div className="grid gap-6 lg:grid-cols-[1fr_24rem]">
          <div className="space-y-6">
            {/* Header Card */}
            <Card className="rounded-[1.45rem]">
              <CardContent className="pt-6">
                <div className="flex items-start justify-between gap-4">
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <Badge variant={priority.variant}>{priority.label}</Badge>
                      <Badge variant={status.variant}>{status.label}</Badge>
                      <Badge variant="outline" className="text-[0.62rem]">
                        {opportunity.opportunityType.replace(/_/g, ' ')}
                      </Badge>
                    </div>
                    <h1 className="mt-4 text-2xl font-semibold text-foreground">{opportunity.title}</h1>
                    <p className="mt-3 text-sm leading-relaxed text-muted-foreground">
                      {opportunity.summary}
                    </p>
                  </div>
                  <div className="shrink-0 text-right">
                    <div className="text-4xl font-bold text-foreground">{opportunity.totalScore.toFixed(0)}</div>
                    <div className="text-xs uppercase tracking-[0.16em] text-muted-foreground">total score</div>
                  </div>
                </div>

                {opportunity.whyItMatters && (
                  <div className="mt-5 rounded-lg bg-primary/5 border border-primary/20 p-4">
                    <p className="text-xs uppercase tracking-[0.16em] text-primary mb-1.5">Why it matters</p>
                    <p className="text-sm text-foreground">{opportunity.whyItMatters}</p>
                  </div>
                )}

                {opportunity.recommendedAction && (
                  <div className="mt-3 rounded-lg bg-success/5 border border-success/20 p-4">
                    <p className="text-xs uppercase tracking-[0.16em] text-success mb-1.5">Recommended action</p>
                    <p className="text-sm text-foreground">{opportunity.recommendedAction}</p>
                  </div>
                )}
              </CardContent>
            </Card>

            {/* Signals */}
            <Card className="rounded-[1.45rem]">
              <CardHeader className="border-b border-border/70">
                <CardTitle className="text-[1.4rem]">Signals</CardTitle>
              </CardHeader>
              <CardContent className="pt-4">
                {signals.length === 0 ? (
                  <p className="text-sm text-muted-foreground">No signals linked to this opportunity.</p>
                ) : (
                  <div className="space-y-3">
                    {signals.map((signal) => (
                      <div
                        key={signal.id}
                        className="flex items-start justify-between gap-3 rounded-lg border border-border/50 p-3"
                      >
                        <div className="min-w-0 flex-1">
                          <p className="text-sm font-medium text-foreground">{signal.title}</p>
                          {signal.summary && (
                            <p className="mt-1 text-xs text-muted-foreground">{signal.summary}</p>
                          )}
                          {signal.url && (
                            <a
                              href={signal.url}
                              target="_blank"
                              rel="noopener noreferrer"
                              className={buttonVariants({ variant: 'ghost', size: 'sm' }) + ' mt-2 h-auto p-0 text-xs text-primary hover:underline'}
                            >
                              <ExternalLink className="mr-1 h-3 w-3" />
                              View source
                            </a>
                          )}
                        </div>
                        {signal.publishedAt && (
                          <span className="shrink-0 text-[0.62rem] text-muted-foreground">
                            {new Date(signal.publishedAt).toLocaleDateString()}
                          </span>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>

            {/* Feedback History */}
            <Card className="rounded-[1.45rem]">
              <CardHeader className="border-b border-border/70">
                <CardTitle className="text-[1.4rem]">Feedback</CardTitle>
              </CardHeader>
              <CardContent className="pt-4">
                {feedbackError && (
                  <div className="mb-3 rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">
                    {feedbackError}
                  </div>
                )}
                {feedback.length === 0 && !feedbackError ? (
                  <p className="text-sm text-muted-foreground">No feedback recorded yet.</p>
                ) : (
                  <div className="space-y-3">
                    {feedback.map((f) => (
                      <div key={f.id} className="flex items-center gap-3 text-sm">
                        <MessageSquare className="h-4 w-4 shrink-0 text-muted-foreground" />
                        <span className="font-medium capitalize">{f.feedbackType.replace(/_/g, ' ')}</span>
                        <span className="text-muted-foreground">
                          {new Date(f.createdAt).toLocaleDateString()}
                        </span>
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>

            {/* Workflow Links */}
            {workflowLinks.length > 0 && (
              <Card className="rounded-[1.45rem]">
                <CardHeader className="border-b border-border/70">
                  <CardTitle className="text-[1.4rem]">Workflow Links</CardTitle>
                </CardHeader>
                <CardContent className="pt-4">
                  <div className="space-y-3">
                    {workflowLinks.map((link) => (
                      <div key={link.id} className="flex items-center justify-between rounded-lg border border-border/50 p-3">
                        <div className="flex items-center gap-2">
                          <span className="text-sm font-medium capitalize">{link.workflowType.replace(/_/g, ' ')}</span>
                          <code className="text-xs text-muted-foreground">{link.workflowId}</code>
                        </div>
                        <span className="text-xs text-muted-foreground">
                          {new Date(link.createdAt).toLocaleDateString()}
                        </span>
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>
            )}

            {/* Status History */}
            {history.length > 0 && (
              <Card className="rounded-[1.45rem]">
                <CardHeader className="border-b border-border/70">
                  <CardTitle className="text-[1.4rem]">Status History</CardTitle>
                </CardHeader>
                <CardContent className="pt-4">
                  <div className="space-y-3">
                    {history.map((entry) => (
                      <div key={entry.id} className="flex items-center gap-3 text-sm">
                        <div className="flex items-center gap-1">
                          <Badge variant="outline" className="text-[0.62rem] capitalize">
                            {entry.previous_status.replace(/_/g, ' ')}
                          </Badge>
                          <ChevronRight className="h-3 w-3 text-muted-foreground" />
                          <Badge variant="secondary" className="text-[0.62rem] capitalize">
                            {entry.new_status.replace(/_/g, ' ')}
                          </Badge>
                        </div>
                        <span className="text-muted-foreground">
                          {new Date(entry.changed_at).toLocaleDateString()}
                        </span>
                        {entry.reason && (
                          <span className="text-xs text-muted-foreground">({entry.reason})</span>
                        )}
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>
            )}
          </div>

          {/* Sidebar */}
          <div className="space-y-6">
            {/* Score Breakdown */}
            {score && (
              <Card className="rounded-[1.45rem]">
                <CardHeader className="border-b border-border/70">
                  <CardTitle className="text-[1.4rem]">Score Breakdown</CardTitle>
                </CardHeader>
                <CardContent className="space-y-4 pt-4">
                  {score.explanation && (
                    <p className="text-sm text-muted-foreground">{score.explanation}</p>
                  )}
                  <div className="space-y-3">
                    <ScoreGauge score={score.strategicRelevanceScore} label="Strategic Relevance" />
                    <ScoreGauge score={score.noveltyScore} label="Novelty" />
                    <ScoreGauge score={score.urgencyScore} label="Urgency" />
                    <ScoreGauge score={score.evidenceScore} label="Evidence" />
                    <ScoreGauge score={score.businessValueScore} label="Business Value" />
                    <ScoreGauge score={score.workflowFitScore} label="Workflow Fit" />
                  </div>
                </CardContent>
              </Card>
            )}

            {/* Actions */}
            <Card className="rounded-[1.45rem]">
              <CardHeader className="border-b border-border/70">
                <CardTitle className="text-[1.4rem]">Actions</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3 pt-4">
                {launchMessage && (
                  <div
                    className={`rounded-lg p-3 text-sm ${
                      launchMessage.type === 'success'
                        ? 'bg-success/10 border border-success/30 text-success'
                        : 'bg-destructive/10 border border-destructive/30 text-destructive'
                    }`}
                  >
                    {launchMessage.text}
                  </div>
                )}

                {/* Workflow Launch Buttons */}
                <div className="space-y-2">
                  <p className="text-xs uppercase tracking-[0.12em] text-muted-foreground">
                    Convert to Workflow
                  </p>
                  <Button
                    variant="outline"
                    className="w-full justify-start"
                    onClick={() => void handleLaunchResearch()}
                    disabled={workflowLaunching === 'research'}
                  >
                    {workflowLaunching === 'research' ? (
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    ) : (
                      <PlayCircle className="mr-2 h-4 w-4" />
                    )}
                    Launch Research
                  </Button>
                  <Button
                    variant="outline"
                    className="w-full justify-start"
                    onClick={() => void handleLaunchBrief()}
                    disabled={workflowLaunching === 'brief'}
                  >
                    {workflowLaunching === 'brief' ? (
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    ) : (
                      <FileText className="mr-2 h-4 w-4" />
                    )}
                    Create Brief
                  </Button>
                  <Button
                    variant="outline"
                    className="w-full justify-start"
                    onClick={() => void handleLaunchBacklog()}
                    disabled={workflowLaunching === 'backlog'}
                  >
                    {workflowLaunching === 'backlog' ? (
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    ) : (
                      <ListChecks className="mr-2 h-4 w-4" />
                    )}
                    Add to Backlog
                  </Button>
                </div>

                {/* Divider */}
                <div className="border-t border-border/50 pt-3">
                  <p className="text-xs uppercase tracking-[0.12em] text-muted-foreground mb-2">
                    Change Status
                  </p>
                  {transitions.map(({ label, icon: Icon, status: newStatus }) => (
                    <Button
                      key={newStatus}
                      variant="outline"
                      className="w-full justify-start"
                      onClick={() => void handleStatusChange(newStatus)}
                      disabled={statusUpdating}
                    >
                      <Icon className="mr-2 h-4 w-4" />
                      {label}
                    </Button>
                  ))}
                </div>
              </CardContent>
            </Card>

            {/* Metadata */}
            <Card className="rounded-[1.45rem]">
              <CardHeader className="border-b border-border/70">
                <CardTitle className="text-[1.4rem]">Details</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3 pt-4 text-sm">
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Created</span>
                  <span>{new Date(opportunity.createdAt).toLocaleDateString()}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Last updated</span>
                  <span>{new Date(opportunity.updatedAt).toLocaleDateString()}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Freshness</span>
                  <Badge variant="outline" className="text-[0.62rem] capitalize">
                    {opportunity.freshnessState}
                  </Badge>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Signals</span>
                  <span>{signals.length}</span>
                </div>
              </CardContent>
            </Card>
          </div>
        </div>
      </div>
    </div>
  );
}