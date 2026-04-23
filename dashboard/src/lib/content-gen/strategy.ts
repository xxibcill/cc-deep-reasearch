import { contentGenClient, getContentGenErrorMessage } from './client';
import type { StrategyMemory, RuleVersion, StrategyReadinessResult, OperatingFitnessMetrics } from '@/types/content-gen';

export async function getStrategy(): Promise<StrategyMemory> {
  try {
    const response = await contentGenClient.get('/strategy');
    return response.data;
  } catch (error) {
    throw new Error(getContentGenErrorMessage(error, 'Failed to get strategy.'));
  }
}

export async function updateStrategy(
  patch: Record<string, unknown>,
): Promise<StrategyMemory> {
  try {
    const response = await contentGenClient.put('/strategy', { patch });
    return response.data;
  } catch (error) {
    throw new Error(getContentGenErrorMessage(error, 'Failed to update strategy.'));
  }
}

export async function getStrategyReadiness(): Promise<StrategyReadinessResult> {
  try {
    const response = await contentGenClient.get('/strategy/readiness');
    return response.data;
  } catch (error) {
    throw new Error(getContentGenErrorMessage(error, 'Failed to get strategy readiness.'));
  }
}

export async function getRulesForReview(): Promise<RuleVersion[]> {
  try {
    const response = await contentGenClient.get('/strategy/rules-for-review');
    return response.data.items ?? response.data;
  } catch (error) {
    throw new Error(getContentGenErrorMessage(error, 'Failed to get rules for review.'));
  }
}

export async function updateRuleLifecycle(
  versionId: string,
  opts?: {
    status?: string;
    confidence?: number;
    evidenceCount?: number;
    reviewAfter?: string;
    reviewNotes?: string;
  },
): Promise<RuleVersion> {
  try {
    const params = new URLSearchParams();
    if (opts?.status) params.set('status', opts.status);
    if (opts?.confidence !== undefined) params.set('confidence', String(opts.confidence));
    if (opts?.evidenceCount !== undefined) params.set('evidence_count', String(opts.evidenceCount));
    if (opts?.reviewAfter) params.set('review_after', opts.reviewAfter);
    if (opts?.reviewNotes) params.set('review_notes', opts.reviewNotes);
    const response = await contentGenClient.patch(`/strategy/rule-lifecycle/${versionId}?${params}`);
    return response.data;
  } catch (error) {
    throw new Error(getContentGenErrorMessage(error, 'Failed to update rule lifecycle.'));
  }
}

export async function getOperatingFitness(
  periodStart?: string,
  periodEnd?: string,
): Promise<{ metrics: OperatingFitnessMetrics; summary: string }> {
  try {
    const params = new URLSearchParams();
    if (periodStart) params.set('period_start', periodStart);
    if (periodEnd) params.set('period_end', periodEnd);
    const response = await contentGenClient.get(`/operating-fitness?${params}`);
    return response.data;
  } catch (error) {
    throw new Error(getContentGenErrorMessage(error, 'Failed to get operating fitness.'));
  }
}