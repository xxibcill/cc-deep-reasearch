'use client';

import { useState, useEffect, useCallback } from 'react';
import {
  fetchGaps,
  fetchAcceptedGaps,
  updateGapStatus,
  runGapDetection,
  type GapCandidate,
  type GapReason,
  type GapStatus,
} from '@/lib/knowledge-client';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { CollapsiblePanel } from '@/components/ui/collapsible-panel';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select-dropdown';
import { AlertTriangle, CheckCircle, Clock, RefreshCw, Search, XCircle, Target } from 'lucide-react';

const GAP_REASON_LABELS: Record<string, { label: string; color: string }> = {
  low_source_count: { label: "Low Source", color: "bg-red-100 text-red-800" },
  stale_coverage: { label: "Stale Coverage", color: "bg-amber-100 text-amber-800" },
  contradictory_claims: { label: "Contradiction", color: "bg-orange-100 text-orange-800" },
  missing_provenance: { label: "Missing Provenance", color: "bg-yellow-100 text-yellow-800" },
  failed_retrieval: { label: "Failed Retrieval", color: "bg-purple-100 text-purple-800" },
  sparse_entity: { label: "Sparse Entity", color: "bg-blue-100 text-blue-800" },
  orphan_node: { label: "Orphan Node", color: "bg-gray-100 text-gray-800" },
};

const STATUS_ICONS: Record<string, React.ReactNode> = {
  detected: <AlertTriangle className="h-4 w-4 text-yellow-500" />,
  accepted: <Target className="h-4 w-4 text-blue-500" />,
  dismissed: <XCircle className="h-4 w-4 text-gray-400" />,
  deferred: <Clock className="h-4 w-4 text-blue-400" />,
  resolved: <CheckCircle className="h-4 w-4 text-green-500" />,
};

const STATUS_COLORS: Record<string, string> = {
  detected: "bg-yellow-50 text-yellow-800 border-yellow-200",
  accepted: "bg-blue-50 text-blue-800 border-blue-200",
  dismissed: "bg-gray-50 text-gray-500 border-gray-200",
  deferred: "bg-slate-50 text-slate-600 border-slate-200",
  resolved: "bg-green-50 text-green-700 border-green-200",
};

interface GapPanelProps {
  /** Callback when a gap is resolved/accepted, to refresh related data */
  onGapChange?: () => void;
}

export function GapPanel({ onGapChange }: GapPanelProps) {
  const [gaps, setGaps] = useState<GapCandidate[]>([]);
  const [acceptedGaps, setAcceptedGaps] = useState<GapCandidate[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [reasonFilter, setReasonFilter] = useState<string>('all');
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [actionStatus, setActionStatus] = useState<string | null>(null);
  const [detectResult, setDetectResult] = useState<{ detected: number; added: number } | null>(null);

  const loadGaps = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [allData, acceptedData] = await Promise.all([
        fetchGaps(),
        fetchAcceptedGaps(),
      ]);
      setGaps(allData.gaps || []);
      setAcceptedGaps(acceptedData.gaps || []);
    } catch {
      setError('Failed to load gaps');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadGaps();
  }, [loadGaps]);

  const handleStatusUpdate = async (
    gapId: string,
    newStatus: 'accepted' | 'dismissed' | 'deferred' | 'resolved',
  ) => {
    try {
      setActionStatus(`Updating gap status...`);
      await updateGapStatus(gapId, newStatus);
      setActionStatus(null);
      if (onGapChange) onGapChange();
      loadGaps();
    } catch {
      setActionStatus('Failed to update gap status');
    }
  };

  const handleRunDetection = async () => {
    try {
      setActionStatus('Running gap detection...');
      const result = await runGapDetection();
      setDetectResult({ detected: result.detected, added: result.added });
      setActionStatus(null);
      if (onGapChange) onGapChange();
      loadGaps();
    } catch {
      setActionStatus('Failed to run gap detection');
    }
  };

  const filteredGaps = gaps.filter((g) => {
    if (reasonFilter !== 'all' && g.gap_type !== reasonFilter) return false;
    if (statusFilter !== 'all' && g.status !== statusFilter) return false;
    return true;
  });

  const reasonOptions = Object.keys(GAP_REASON_LABELS);
  const statusOptions = ['detected', 'accepted', 'dismissed', 'deferred', 'resolved'];

  return (
    <div className="flex flex-col gap-4 p-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-sm font-medium">Knowledge Gaps</h3>
          <p className="text-xs text-muted-foreground">
            {filteredGaps.length} gap{filteredGaps.length !== 1 ? 's' : ''} shown
            {acceptedGaps.length > 0 && ` · ${acceptedGaps.length} accepted`}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={handleRunDetection}
            className="h-7 px-2 text-xs"
            title="Scan graph for new gaps"
          >
            <Search className="h-3 w-3 mr-1" />
            Detect
          </Button>
          <Button variant="outline" size="sm" onClick={loadGaps} className="h-7 px-2">
            <RefreshCw className="h-3 w-3" />
          </Button>
        </div>
      </div>

      {/* Detection result */}
      {detectResult && (
        <div className="rounded bg-primary/5 border border-primary/20 p-2 text-xs">
          Detection complete: found {detectResult.detected} gaps, added {detectResult.added} new
          <button
            onClick={() => setDetectResult(null)}
            className="ml-2 text-muted-foreground hover:text-foreground"
          >
            ✕
          </button>
        </div>
      )}

      {/* Action status */}
      {actionStatus && (
        <div className="rounded bg-muted/50 p-2 text-xs text-muted-foreground">
          {actionStatus}
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="rounded bg-destructive/10 p-2 text-xs text-destructive">
          {error}
        </div>
      )}

      {/* Filters */}
      <div className="flex items-center gap-2">
        <Select value={reasonFilter} onValueChange={setReasonFilter}>
          <SelectTrigger className="h-7 w-36 text-xs">
            <SelectValue placeholder="Filter by reason" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Reasons</SelectItem>
            {reasonOptions.map((key) => (
              <SelectItem key={key} value={key}>
                {GAP_REASON_LABELS[key].label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Select value={statusFilter} onValueChange={setStatusFilter}>
          <SelectTrigger className="h-7 w-32 text-xs">
            <SelectValue placeholder="Filter by status" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Statuses</SelectItem>
            {statusOptions.map((s) => (
              <SelectItem key={s} value={s}>
                {s.charAt(0).toUpperCase() + s.slice(1)}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {/* Loading */}
      {loading && gaps.length === 0 && (
        <div className="py-8 text-center text-sm text-muted-foreground">
          Loading gaps...
        </div>
      )}

      {/* Empty state */}
      {!loading && filteredGaps.length === 0 && (
        <div className="py-8 text-center text-sm text-muted-foreground">
          {reasonFilter !== 'all' || statusFilter !== 'all'
            ? 'No gaps match the selected filters.'
            : 'No gaps detected. Run detection to scan the graph.'}
        </div>
      )}

      {/* Accepted gaps section */}
      {acceptedGaps.length > 0 && statusFilter === 'all' && (
        <div className="space-y-2">
          <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
            Accepted for Follow-up
          </p>
          <div className="space-y-2">
            {acceptedGaps.slice(0, 5).map((gap) => (
              <div
                key={gap.id}
                className="rounded-lg border border-blue-200 bg-blue-50/50 p-3"
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <Badge variant="info">
                        {GAP_REASON_LABELS[gap.gap_type]?.label || gap.gap_type}
                      </Badge>
                      <span className="text-xs text-muted-foreground capitalize">
                        {gap.status}
                      </span>
                    </div>
                    <p className="text-sm text-foreground break-words">
                      {gap.description}
                    </p>
                    {gap.suggested_queries.length > 0 && (
                      <ul className="mt-2 space-y-1">
                        {gap.suggested_queries.slice(0, 2).map((q, i) => (
                          <li key={i} className="text-xs text-muted-foreground">
                            → {q}
                          </li>
                        ))}
                      </ul>
                    )}
                  </div>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => handleStatusUpdate(gap.id, 'resolved')}
                    className="h-7 text-xs text-green-600 hover:text-green-700"
                  >
                    Resolve
                  </Button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* All gaps list */}
      {filteredGaps.length > 0 && (
        <div className="space-y-2">
          {filteredGaps.map((gap) => {
            const reasonInfo = GAP_REASON_LABELS[gap.gap_type] || {
              label: gap.gap_type,
              color: 'bg-gray-100 text-gray-800',
            };

            return (
              <CollapsiblePanel
                key={gap.id}
                summary={
                  <div className="flex items-center gap-2 min-w-0">
                    <span className={`inline-flex rounded-full px-2 py-0.5 text-[0.65rem] font-medium ${reasonInfo.color}`}>
                      {reasonInfo.label}
                    </span>
                    <span className="text-xs text-foreground truncate">
                      {gap.description.slice(0, 80)}
                      {gap.description.length > 80 ? '...' : ''}
                    </span>
                  </div>
                }
                meta={
                  <div className="flex items-center gap-1.5">
                    {STATUS_ICONS[gap.status]}
                    <span className="text-[10px] uppercase">{gap.status}</span>
                  </div>
                }
                actions={
                  gap.status === 'detected' ? (
                    <div className="flex items-center gap-1">
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          handleStatusUpdate(gap.id, 'accepted');
                        }}
                        className="rounded px-1.5 py-0.5 text-[10px] bg-blue-100 text-blue-700 hover:bg-blue-200"
                      >
                        Accept
                      </button>
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          handleStatusUpdate(gap.id, 'dismissed');
                        }}
                        className="rounded px-1.5 py-0.5 text-[10px] bg-gray-100 text-gray-600 hover:bg-gray-200"
                      >
                        Dismiss
                      </button>
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          handleStatusUpdate(gap.id, 'deferred');
                        }}
                        className="rounded px-1.5 py-0.5 text-[10px] bg-amber-100 text-amber-700 hover:bg-amber-200"
                      >
                        Defer
                      </button>
                    </div>
                  ) : gap.status === 'accepted' ? (
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        handleStatusUpdate(gap.id, 'resolved');
                      }}
                      className="rounded px-1.5 py-0.5 text-[10px] bg-green-100 text-green-700 hover:bg-green-200"
                    >
                      Resolve
                    </button>
                  ) : null
                }
              >
                <div className="space-y-3">
                  {/* Full description */}
                  <p className="text-sm text-foreground">{gap.description}</p>

                  {/* Evidence */}
                  {Object.keys(gap.evidence).length > 0 && (
                    <div className="rounded bg-muted/50 p-2">
                      <p className="text-[10px] uppercase tracking-wider text-muted-foreground mb-1">
                        Evidence
                      </p>
                      <div className="space-y-1">
                        {Object.entries(gap.evidence).map(([key, value]) => (
                          <div key={key} className="flex items-center gap-2 text-xs">
                            <span className="text-muted-foreground font-mono">{key}:</span>
                            <span className="text-foreground">
                              {typeof value === 'string' ? value.slice(0, 100) : String(value)}
                            </span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Suggested queries */}
                  {gap.suggested_queries.length > 0 && (
                    <div>
                      <p className="text-[10px] uppercase tracking-wider text-muted-foreground mb-1">
                        Suggested Follow-up
                      </p>
                      <ul className="space-y-1">
                        {gap.suggested_queries.map((q, i) => (
                          <li
                            key={i}
                            className="flex items-start gap-1.5 text-xs text-foreground"
                          >
                            <Search className="h-3 w-3 mt-0.5 shrink-0 text-muted-foreground" />
                            {q}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {/* Timestamps */}
                  <div className="flex items-center gap-4 text-[10px] text-muted-foreground">
                    <span>Created: {new Date(gap.created_at).toLocaleDateString()}</span>
                    {gap.resolved_at && (
                      <span>Resolved: {new Date(gap.resolved_at).toLocaleDateString()}</span>
                    )}
                    {gap.node_id && (
                      <span className="font-mono truncate">Node: {gap.node_id}</span>
                    )}
                  </div>

                  {/* Status actions for accepted/deferred gaps */}
                  {gap.status === 'accepted' && (
                    <div className="flex items-center gap-2 pt-1 border-t">
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => handleStatusUpdate(gap.id, 'resolved')}
                        className="h-7 text-xs"
                      >
                        <CheckCircle className="h-3 w-3 mr-1" />
                        Mark Resolved
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => handleStatusUpdate(gap.id, 'deferred')}
                        className="h-7 text-xs"
                      >
                        Defer
                      </Button>
                    </div>
                  )}
                  {gap.status === 'deferred' && (
                    <div className="flex items-center gap-2 pt-1 border-t">
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => handleStatusUpdate(gap.id, 'accepted')}
                        className="h-7 text-xs"
                      >
                        Accept
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => handleStatusUpdate(gap.id, 'resolved')}
                        className="h-7 text-xs"
                      >
                        Resolve
                      </Button>
                    </div>
                  )}
                </div>
              </CollapsiblePanel>
            );
          })}
        </div>
      )}
    </div>
  );
}
