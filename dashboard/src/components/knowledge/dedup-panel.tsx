"use client";

import { useState, useEffect, useCallback } from 'react';
import {
  fetchDuplicateCandidates,
  resolveDuplicateCandidate,
  mergeNodes,
  type DuplicateCandidate,
} from '@/lib/knowledge-client';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select-dropdown';
import { AlertCircle, CheckCircle, Clock, Merge, XCircle, MoreHorizontal, RefreshCw } from 'lucide-react';

interface DedupPanelProps {
  /** Callback when a merge occurs, to refresh graph data */
  onMerge?: () => void;
}

const REASON_LABELS: Record<string, { label: string; color: string }> = {
  same_url: { label: "Same URL", color: "bg-red-100 text-red-800" },
  similar_title: { label: "Similar Title", color: "bg-yellow-100 text-yellow-800" },
  same_entity_label: { label: "Same Entity", color: "bg-blue-100 text-blue-800" },
  similar_text: { label: "Similar Text", color: "bg-purple-100 text-purple-800" },
  shared_session: { label: "Shared Session", color: "bg-gray-100 text-gray-800" },
};

const STATUS_ICONS = {
  pending: <Clock className="h-4 w-4 text-yellow-500" />,
  merged: <CheckCircle className="h-4 w-4 text-green-500" />,
  dismissed: <XCircle className="h-4 w-4 text-gray-400" />,
  deferred: <AlertCircle className="h-4 w-4 text-blue-500" />,
};

export function DedupPanel({ onMerge }: DedupPanelProps) {
  const [candidates, setCandidates] = useState<DuplicateCandidate[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [reasonFilter, setReasonFilter] = useState<string>('all');
  const [actionStatus, setActionStatus] = useState<string | null>(null);

  const loadCandidates = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchDuplicateCandidates();
      setCandidates(data.candidates || []);
    } catch (err) {
      setError('Failed to load candidates');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadCandidates();
  }, [loadCandidates]);

  const handleResolve = async (candidateId: string, action: 'merge' | 'dismiss' | 'defer') => {
    try {
      setActionStatus(`${action}ing candidate...`);
      const result = await resolveDuplicateCandidate(candidateId, action);
      setActionStatus(null);

      if (action === 'merge' && onMerge) {
        onMerge();
      }

      // Refresh candidates
      loadCandidates();
    } catch (err) {
      setActionStatus('Action failed');
    }
  };

  const handleMerge = async (nodeAId: string, nodeBId: string) => {
    try {
      setActionStatus('Merging nodes...');
      await mergeNodes(nodeAId, nodeBId);
      setActionStatus('Merge complete');
      if (onMerge) onMerge();
      loadCandidates();
    } catch (err) {
      setActionStatus('Merge failed');
    }
  };

  const filteredCandidates = candidates.filter((c) => {
    if (reasonFilter === 'all') return true;
    return c.match_reason === reasonFilter;
  });

  return (
    <div className="flex flex-col gap-4 p-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-sm font-medium">Duplicate Candidates</h3>
          <p className="text-xs text-muted-foreground">
            {filteredCandidates.length} candidates
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Select value={reasonFilter} onValueChange={setReasonFilter}>
            <SelectTrigger className="h-7 w-36 text-xs">
              <SelectValue placeholder="Filter by reason" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Reasons</SelectItem>
              {Object.entries(REASON_LABELS).map(([key, { label }]) => (
                <SelectItem key={key} value={key}>
                  {label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Button variant="outline" size="sm" onClick={loadCandidates} className="h-7 px-2">
            <RefreshCw className="h-3 w-3" />
          </Button>
        </div>
      </div>

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

      {/* Loading */}
      {loading && candidates.length === 0 && (
        <div className="py-8 text-center text-sm text-muted-foreground">
          Loading candidates...
        </div>
      )}

      {/* Empty state */}
      {!loading && filteredCandidates.length === 0 && (
        <div className="py-8 text-center text-sm text-muted-foreground">
          No duplicate candidates found.
        </div>
      )}

      {/* Candidates table */}
      {filteredCandidates.length > 0 && (
        <div className="rounded-lg border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-32">Reason</TableHead>
                <TableHead>Node A</TableHead>
                <TableHead>Node B</TableHead>
                <TableHead className="w-20">Confidence</TableHead>
                <TableHead className="w-24">Status</TableHead>
                <TableHead className="w-24">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filteredCandidates.map((candidate) => {
                const reasonInfo = REASON_LABELS[candidate.match_reason] || {
                  label: candidate.match_reason,
                  color: 'bg-gray-100 text-gray-800',
                };

                return (
                  <TableRow key={candidate.id}>
                    <TableCell>
                      <span
                        className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ${reasonInfo.color}`}
                      >
                        {reasonInfo.label}
                      </span>
                    </TableCell>
                    <TableCell className="font-mono text-xs">
                      <div className="max-w-32 truncate" title={candidate.node_a_id}>
                        {candidate.node_a_id}
                      </div>
                    </TableCell>
                    <TableCell className="font-mono text-xs">
                      <div className="max-w-32 truncate" title={candidate.node_b_id}>
                        {candidate.node_b_id}
                      </div>
                    </TableCell>
                    <TableCell>
                      <div className="flex items-center gap-1">
                        <div className="h-1.5 w-16 rounded-full bg-muted">
                          <div
                            className="h-1.5 rounded-full bg-primary"
                            style={{ width: `${candidate.confidence * 100}%` }}
                          />
                        </div>
                        <span className="text-xs text-muted-foreground">
                          {Math.round(candidate.confidence * 100)}%
                        </span>
                      </div>
                    </TableCell>
                    <TableCell>
                      <div className="flex items-center gap-1">
                        {STATUS_ICONS[candidate.status as keyof typeof STATUS_ICONS] || STATUS_ICONS.pending}
                        <span className="text-xs capitalize">{candidate.status}</span>
                      </div>
                    </TableCell>
                    <TableCell>
                      <DropdownMenu>
                        <DropdownMenuTrigger asChild>
                          <Button variant="ghost" size="sm" className="h-7 w-7 p-0">
                            <MoreHorizontal className="h-4 w-4" />
                          </Button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end">
                          <DropdownMenuItem
                            onClick={() =>
                              handleMerge(candidate.node_a_id, candidate.node_b_id)
                            }
                          >
                            <Merge className="mr-2 h-3 w-3" />
                            Merge
                          </DropdownMenuItem>
                          <DropdownMenuItem
                            onClick={() =>
                              handleResolve(candidate.id, 'dismiss')
                            }
                          >
                            <XCircle className="mr-2 h-3 w-3" />
                            Dismiss
                          </DropdownMenuItem>
                          <DropdownMenuItem
                            onClick={() =>
                              handleResolve(candidate.id, 'defer')
                            }
                          >
                            <Clock className="mr-2 h-3 w-3" />
                            Defer
                          </DropdownMenuItem>
                        </DropdownMenuContent>
                      </DropdownMenu>
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </div>
      )}
    </div>
  );
}
