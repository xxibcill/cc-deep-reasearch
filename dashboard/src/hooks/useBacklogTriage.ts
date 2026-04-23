import { useState, useCallback } from 'react';
import { backlogTriageRespond, backlogTriageApply } from '@/lib/content-gen/backlog-ai';
import type { BacklogItem, TriageOperation, TriageOperationInput } from '@/types/content-gen';

export interface UseBacklogTriageReturn {
  loading: boolean;
  error: string | null;
  proposals: TriageOperation[];
  replyMarkdown: string;
  dismissedSet: Set<number>;
  appliedSet: Set<number>;
  selectedSet: Set<number>;
  applyBusy: boolean;
  applyErrors: string[];
  bulkResult: { applied: number; errors: string[] } | null;
  runTriage: (backlog: BacklogItem[], strategy?: Record<string, unknown> | null) => Promise<void>;
  dismissProposal: (index: number) => void;
  toggleSelectProposal: (index: number) => void;
  selectAllInGroup: (indices: number[]) => void;
  applySelected: (operations: TriageOperationInput[]) => Promise<{ applied: number; errors: string[] }>;
  clearResults: () => void;
}

export function useBacklogTriage(): UseBacklogTriageReturn {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [allProposals, setAllProposals] = useState<TriageOperation[]>([]);
  const [replyMarkdown, setReplyMarkdown] = useState<string>('');
  const [dismissedSet, setDismissedSet] = useState<Set<number>>(new Set());
  const [appliedSet, setAppliedSet] = useState<Set<number>>(new Set());
  const [selectedSet, setSelectedSet] = useState<Set<number>>(new Set());
  const [applyBusy, setApplyBusy] = useState(false);
  const [applyErrors, setApplyErrors] = useState<string[]>([]);
  const [bulkResult, setBulkResult] = useState<{ applied: number; errors: string[] } | null>(null);

  const runTriage = useCallback(async (
    backlog: BacklogItem[],
    strategy?: Record<string, unknown> | null,
  ) => {
    setLoading(true);
    setError(null);
    setAllProposals([]);
    setDismissedSet(new Set());
    setAppliedSet(new Set());
    setSelectedSet(new Set());
    setReplyMarkdown('');
    setApplyErrors([]);
    setBulkResult(null);

    try {
      const response = await backlogTriageRespond({ backlog_items: backlog, strategy });
      setAllProposals(response.proposals);
      setReplyMarkdown(response.reply_markdown);
      if (response.warnings.length > 0) {
        setError(response.warnings.join('; '));
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Triage analysis failed.');
    } finally {
      setLoading(false);
    }
  }, []);

  const dismissProposal = useCallback((index: number) => {
    setDismissedSet((prev) => new Set([...prev, index]));
    setSelectedSet((prev) => {
      const next = new Set(prev);
      next.delete(index);
      return next;
    });
  }, []);

  const toggleSelectProposal = useCallback((index: number) => {
    setSelectedSet((prev) => {
      const next = new Set(prev);
      if (next.has(index)) {
        next.delete(index);
      } else {
        next.add(index);
      }
      return next;
    });
  }, []);

  const selectAllInGroup = useCallback((indices: number[]) => {
    setSelectedSet((prev) => {
      const next = new Set(prev);
      indices.forEach((i) => next.add(i));
      return next;
    });
  }, []);

  const applySelected = useCallback(async (
    operations: TriageOperationInput[],
  ): Promise<{ applied: number; errors: string[] }> => {
    setApplyBusy(true);
    setApplyErrors([]);
    try {
      const response = await backlogTriageApply({ operations });
      setBulkResult({ applied: response.applied, errors: response.errors });
      setApplyErrors(response.errors);
      return response;
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : 'Failed to apply proposals.';
      setApplyErrors([errorMsg]);
      return { applied: 0, errors: [errorMsg] };
    } finally {
      setApplyBusy(false);
    }
  }, []);

  const clearResults = useCallback(() => {
    setAllProposals([]);
    setReplyMarkdown('');
    setDismissedSet(new Set());
    setAppliedSet(new Set());
    setSelectedSet(new Set());
    setApplyErrors([]);
    setBulkResult(null);
    setError(null);
  }, []);

  return {
    loading,
    error,
    proposals: allProposals,
    replyMarkdown,
    dismissedSet,
    appliedSet,
    selectedSet,
    applyBusy,
    applyErrors,
    bulkResult,
    runTriage,
    dismissProposal,
    toggleSelectProposal,
    selectAllInGroup,
    applySelected,
    clearResults,
  };
}