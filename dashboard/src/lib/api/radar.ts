import { apiClient } from '@/lib/api/client';
import type {
  ApiRadarSource,
  ApiOpportunity,
  OpportunityDetailResponse,
  OpportunityListResponse,
  SourceListResponse,
  RadarSource,
  Opportunity,
  OpportunityDetail,
  OpportunityListResult,
  SourceListResult,
} from '@/types/radar';

// ---------------------------------------------------------------------------
// Radar API helpers
// ---------------------------------------------------------------------------

function normalizeRadarSource(raw: ApiRadarSource): RadarSource {
  return {
    id: raw.id,
    sourceType: raw.source_type as RadarSource['sourceType'],
    label: raw.label,
    urlOrIdentifier: raw.url_or_identifier,
    status: raw.status as RadarSource['status'],
    owner: raw.owner,
    priority: (raw.priority || 'medium') as RadarSource['priority'],
    scanCadence: raw.scan_cadence,
    lastScannedAt: raw.last_scanned_at,
    lastScanSuccess: raw.last_scan_success,
    lastFailureReason: raw.last_failure_reason,
    consecutiveFailures: raw.consecutive_failures || 0,
    health: (raw.health || 'healthy') as RadarSource['health'],
    notes: raw.notes,
    createdAt: raw.created_at,
    updatedAt: raw.updated_at,
    metadata: raw.metadata || {},
  };
}

function normalizeOpportunity(raw: ApiOpportunity): Opportunity {
  const rawAny = raw as unknown as Record<string, unknown>;
  return {
    id: raw.id,
    title: raw.title,
    summary: raw.summary,
    opportunityType: raw.opportunity_type as Opportunity['opportunityType'],
    status: raw.status as Opportunity['status'],
    owner: raw.owner || null,
    priority: (raw.priority || 'medium') as Opportunity['priority'],
    reason: raw.reason || null,
    nextAction: (rawAny['next_action'] as string | null) || null,
    reviewedAt: (rawAny['reviewed_at'] as string | null) || null,
    priorityLabel: raw.priority_label as Opportunity['priorityLabel'],
    whyItMatters: raw.why_it_matters,
    recommendedAction: raw.recommended_action,
    totalScore: raw.total_score,
    freshnessState: raw.freshness_state as Opportunity['freshnessState'],
    createdAt: raw.created_at,
    updatedAt: raw.updated_at,
    metadata: raw.metadata || {},
  };
}

export async function getRadarSources(status?: string): Promise<SourceListResult> {
  const params: Record<string, unknown> = {};
  if (status) params.status = status;
  const response = await apiClient.get<SourceListResponse>('/radar/sources', { params });
  return {
    sources: response.data.items.map(normalizeRadarSource),
    total: response.data.count,
  };
}

export interface CreateRadarSourceRequest {
  source_type: string;
  label: string;
  url_or_identifier: string;
  scan_cadence?: string;
  metadata?: Record<string, unknown>;
}

export async function createRadarSource(request: CreateRadarSourceRequest): Promise<RadarSource> {
  const response = await apiClient.post<ApiRadarSource>('/radar/sources', request);
  return normalizeRadarSource(response.data);
}

export async function getRadarOpportunities(params?: {
  status?: string;
  opportunity_type?: string;
  freshness?: string;
  limit?: number;
}): Promise<OpportunityListResult> {
  const queryParams: Record<string, unknown> = {};
  if (params?.status) queryParams.status = params.status;
  if (params?.opportunity_type) queryParams.opportunity_type = params.opportunity_type;
  if (params?.freshness) queryParams.freshness = params.freshness;
  if (params?.limit) queryParams.limit = params.limit;
  const response = await apiClient.get<OpportunityListResponse>('/radar/opportunities', {
    params: queryParams,
  });
  return {
    opportunities: response.data.items.map(normalizeOpportunity),
    total: response.data.count,
  };
}

export async function getRadarOpportunityDetail(
  opportunityId: string
): Promise<OpportunityDetail> {
  const response = await apiClient.get<OpportunityDetailResponse>(
    `/radar/opportunities/${opportunityId}`
  );
  return {
    opportunity: normalizeOpportunity(response.data.opportunity),
    score: response.data.score
      ? {
          opportunityId: response.data.score.opportunity_id,
          strategicRelevanceScore: response.data.score.strategic_relevance_score,
          noveltyScore: response.data.score.novelty_score,
          urgencyScore: response.data.score.urgency_score,
          evidenceScore: response.data.score.evidence_score,
          businessValueScore: response.data.score.business_value_score,
          workflowFitScore: response.data.score.workflow_fit_score,
          totalScore: response.data.score.total_score,
          priorityLabel: response.data.score.priority_label as Opportunity['priorityLabel'],
          explanation: response.data.score.explanation,
          scoredAt: response.data.score.scored_at,
        }
      : null,
    signals: response.data.signals.map((s) => ({
      id: s.id,
      sourceId: s.source_id,
      externalId: s.external_id,
      title: s.title,
      summary: s.summary,
      url: s.url,
      publishedAt: s.published_at,
      discoveredAt: s.discovered_at,
      contentHash: s.content_hash,
      metadata: s.metadata,
      normalizedType: s.normalized_type,
    })),
    feedback: response.data.feedback.map((f) => ({
      id: f.id,
      opportunityId: f.opportunity_id,
      feedbackType: f.feedback_type as OpportunityDetail['feedback'][number]['feedbackType'],
      createdAt: f.created_at,
      metadata: f.metadata,
    })),
    workflowLinks: response.data.workflow_links.map((w) => ({
      id: w.id,
      opportunityId: w.opportunity_id,
      workflowType: w.workflow_type as OpportunityDetail['workflowLinks'][number]['workflowType'],
      workflowId: w.workflow_id,
      createdAt: w.created_at,
    })),
  };
}

export type OpportunityStatusUpdate =
  | 'new'
  | 'reviewing'
  | 'accepted'
  | 'deferred'
  | 'rejected'
  | 'converted'
  | 'saved'
  | 'acted_on'
  | 'monitoring'
  | 'dismissed'
  | 'archived';

export async function updateRadarOpportunity(
  opportunityId: string,
  updates: {
    status?: string;
    owner?: string | null;
    priority?: string;
    reason?: string | null;
    next_action?: string | null;
    reviewed_at?: string | null;
  }
): Promise<OpportunityDetail> {
  const response = await apiClient.patch<OpportunityDetailResponse>(
    `/radar/opportunities/${opportunityId}`,
    updates
  );
  return {
    opportunity: normalizeOpportunity(response.data.opportunity),
    score: response.data.score
      ? {
          opportunityId: response.data.score.opportunity_id,
          strategicRelevanceScore: response.data.score.strategic_relevance_score,
          noveltyScore: response.data.score.novelty_score,
          urgencyScore: response.data.score.urgency_score,
          evidenceScore: response.data.score.evidence_score,
          businessValueScore: response.data.score.business_value_score,
          workflowFitScore: response.data.score.workflow_fit_score,
          totalScore: response.data.score.total_score,
          priorityLabel: response.data.score.priority_label as Opportunity['priorityLabel'],
          explanation: response.data.score.explanation,
          scoredAt: response.data.score.scored_at,
        }
      : null,
    signals: response.data.signals.map((s) => ({
      id: s.id,
      sourceId: s.source_id,
      externalId: s.external_id,
      title: s.title,
      summary: s.summary,
      url: s.url,
      publishedAt: s.published_at,
      discoveredAt: s.discovered_at,
      contentHash: s.content_hash,
      metadata: s.metadata,
      normalizedType: s.normalized_type,
    })),
    feedback: response.data.feedback.map((f) => ({
      id: f.id,
      opportunityId: f.opportunity_id,
      feedbackType: f.feedback_type as OpportunityDetail['feedback'][number]['feedbackType'],
      createdAt: f.created_at,
      metadata: f.metadata,
    })),
    workflowLinks: response.data.workflow_links.map((w) => ({
      id: w.id,
      opportunityId: w.opportunity_id,
      workflowType: w.workflow_type as OpportunityDetail['workflowLinks'][number]['workflowType'],
      workflowId: w.workflow_id,
      createdAt: w.created_at,
    })),
  };
}

export async function bulkUpdateRadarOpportunities(
  opportunityIds: string[],
  status: string,
  reason?: string
): Promise<{ updated: Opportunity[]; count: number }> {
  const response = await apiClient.post<{ updated: ApiOpportunity[]; count: number }>(
    '/radar/opportunities/bulk-status',
    { opportunity_ids: opportunityIds, status, reason }
  );
  return {
    updated: response.data.updated.map(normalizeOpportunity),
    count: response.data.count,
  };
}

export async function updateRadarOpportunityStatus(
  opportunityId: string,
  status: OpportunityStatusUpdate
): Promise<Opportunity> {
  const response = await apiClient.post<ApiOpportunity>(
    `/radar/opportunities/${opportunityId}/status`,
    { status }
  );
  return normalizeOpportunity(response.data);
}

export type FeedbackTypeInput =
  | 'acted_on'
  | 'saved'
  | 'dismissed'
  | 'ignored'
  | 'converted_to_research'
  | 'converted_to_content'
  | 'useful'
  | 'not_useful'
  | 'duplicate'
  | 'stale'
  | 'too_broad'
  | 'wrong_audience';

export async function recordRadarOpportunityFeedback(
  opportunityId: string,
  feedbackType: FeedbackTypeInput,
  metadata?: Record<string, unknown>
): Promise<void> {
  await apiClient.post(`/radar/opportunities/${opportunityId}/feedback`, {
    feedback_type: feedbackType,
    metadata: metadata ?? {},
  });
}

export async function recordRadarScoringFeedback(
  opportunityId: string,
  request: {
    feedback_type: string;
    signal_id?: string;
    scoring_features?: Record<string, number>;
    rank_position?: number;
    outcome?: string;
  }
): Promise<void> {
  await apiClient.post(`/radar/opportunities/${opportunityId}/scoring-feedback`, request);
}

export async function getRadarScoringFeedback(opportunityId: string): Promise<{
  feedback_entries: import('@/types/radar').ScoringFeedback[];
  count: number;
}> {
  const response = await apiClient.get<{ feedback_entries: import('@/types/radar').ScoringFeedback[]; count: number }>(
    `/radar/opportunities/${opportunityId}/scoring-feedback`
  );
  return response.data;
}

export async function getRadarScoringOutcomes(): Promise<{
  outcomes: Record<string, number>;
  total_feedback: number;
}> {
  const response = await apiClient.get<{ outcomes: Record<string, number>; total_feedback: number }>(
    '/radar/scoring/outcomes'
  );
  return response.data;
}

export interface LaunchResearchResponse {
  research_run_id: string;
  opportunity_id: string;
  status: string;
  session_id: string | null;
}

export interface LaunchBriefResponse {
  brief_id: string;
  opportunity_id: string;
}

export interface LaunchBacklogResponse {
  backlog_item_id: string;
  opportunity_id: string;
}

export interface LaunchContentPipelineResponse {
  pipeline_id: string;
  opportunity_id: string;
  status: string;
}

export interface StatusHistoryEntry {
  id: string;
  opportunity_id: string;
  previous_status: string;
  new_status: string;
  reason: string | null;
  changed_at: string;
}

export interface StatusHistoryResult {
  entries: StatusHistoryEntry[];
  count: number;
}

export async function launchRadarOpportunityResearch(
  opportunityId: string
): Promise<LaunchResearchResponse> {
  const response = await apiClient.post<LaunchResearchResponse>(
    `/radar/opportunities/${opportunityId}/launch-research`,
    {}
  );
  return response.data;
}

export async function launchRadarOpportunityBrief(
  opportunityId: string
): Promise<LaunchBriefResponse> {
  const response = await apiClient.post<LaunchBriefResponse>(
    `/radar/opportunities/${opportunityId}/launch-brief`,
    {}
  );
  return response.data;
}

export async function launchRadarOpportunityBacklog(
  opportunityId: string
): Promise<LaunchBacklogResponse> {
  const response = await apiClient.post<LaunchBacklogResponse>(
    `/radar/opportunities/${opportunityId}/launch-backlog`,
    {}
  );
  return response.data;
}

export async function launchRadarOpportunityContentPipeline(
  opportunityId: string
): Promise<LaunchContentPipelineResponse> {
  const response = await apiClient.post<LaunchContentPipelineResponse>(
    `/radar/opportunities/${opportunityId}/launch-content-pipeline`,
    {}
  );
  return response.data;
}

export async function getRadarOpportunityHistory(
  opportunityId: string
): Promise<StatusHistoryResult> {
  const response = await apiClient.get<StatusHistoryResult>(
    `/radar/opportunities/${opportunityId}/history`
  );
  return response.data;
}

export interface RadarAnalytics {
  total_opportunities: number;
  opportunities_by_status: Record<string, number>;
  opportunities_by_type: Record<string, number>;
  feedback_counts: Record<string, number>;
  conversion_rates: Record<string, number>;
  avg_time_to_action_hours: number | null;
  top_opportunity_types: [string, number][];
}

export interface ConversionFunnel {
  funnel: { stage: string; label: string; count: number }[];
  total: number;
}

export interface ScoreDistribution {
  distribution: Record<string, number>;
  total: number;
  avg_score: number;
}

export interface FeedbackTrends {
  daily_counts: Record<string, Record<string, number>>;
  days_back: number;
}

export async function getRadarAnalytics(): Promise<RadarAnalytics> {
  const response = await apiClient.get<RadarAnalytics>('/radar/analytics');
  return response.data;
}

export async function getRadarConversionFunnel(): Promise<ConversionFunnel> {
  const response = await apiClient.get<ConversionFunnel>('/radar/analytics/funnel');
  return response.data;
}

export async function getRadarScoreDistribution(): Promise<ScoreDistribution> {
  const response = await apiClient.get<ScoreDistribution>('/radar/analytics/score-distribution');
  return response.data;
}

export async function getRadarFeedbackTrends(daysBack: number = 30): Promise<FeedbackTrends> {
  const response = await apiClient.get<FeedbackTrends>('/radar/analytics/feedback-trends', {
    params: { days_back: daysBack },
  });
  return response.data;
}

// Source governance API helpers

export async function updateRadarSource(
  sourceId: string,
  patch: {
    owner?: string | null;
    priority?: string;
    scan_cadence?: string;
    status?: string;
    notes?: string | null;
    metadata?: Record<string, unknown>;
  }
): Promise<RadarSource> {
  const response = await apiClient.patch<ApiRadarSource>(`/radar/sources/${sourceId}`, patch);
  return normalizeRadarSource(response.data);
}

export async function getRadarSourceHealth(
  sourceId: string
): Promise<import('@/types/radar').SourceHealthDetails> {
  const response = await apiClient.get<import('@/types/radar').SourceHealthDetails>(
    `/radar/sources/health/${sourceId}`
  );
  return response.data;
}

export async function getRadarSourcesGovernance(filters?: {
  status?: string;
  health?: string;
  priority?: string;
  owner?: string;
}): Promise<SourceListResult> {
  const params: Record<string, unknown> = {};
  if (filters?.status) params.status = filters.status;
  if (filters?.health) params.health = filters.health;
  if (filters?.priority) params.priority = filters.priority;
  if (filters?.owner) params.owner = filters.owner;
  const response = await apiClient.get<SourceListResponse>('/radar/sources/governance', { params });
  return {
    sources: response.data.items.map(normalizeRadarSource),
    total: response.data.count,
  };
}

export async function pauseRadarSource(sourceId: string): Promise<RadarSource> {
  const response = await apiClient.post<ApiRadarSource>(`/radar/sources/${sourceId}/pause`);
  return normalizeRadarSource(response.data);
}

export async function resumeRadarSource(sourceId: string): Promise<RadarSource> {
  const response = await apiClient.post<ApiRadarSource>(`/radar/sources/${sourceId}/resume`);
  return normalizeRadarSource(response.data);
}

// Scan job API helpers

export interface ScanJobResult {
  jobs: import('@/types/radar').ScanJob[];
  count: number;
}

export async function getRadarScanHistory(
  sourceId?: string,
  limit: number = 50
): Promise<ScanJobResult> {
  const params: Record<string, unknown> = { limit };
  if (sourceId) params.source_id = sourceId;
  const response = await apiClient.get<{ jobs: import('@/types/radar').ScanJob[]; count: number }>(
    '/radar/scan/history',
    { params }
  );
  return response.data;
}

export async function triggerRadarScan(sourceId: string): Promise<import('@/types/radar').ScanJob> {
  const response = await apiClient.post<import('@/types/radar').ScanJob>('/radar/scan/trigger', {
    source_id: sourceId,
  });
  return response.data;
}

export async function dryRunRadarScan(sourceId?: string): Promise<{
  sources: { id: string; label: string; scan_cadence: string }[];
  job_count: number;
  dry_run: boolean;
}> {
  const params: Record<string, unknown> = {};
  if (sourceId) params.source_id = sourceId;
  const response = await apiClient.get<{
    sources: { id: string; label: string; scan_cadence: string }[];
    job_count: number;
    dry_run: boolean;
  }>('/radar/scan/dry-run', { params });
  return response.data;
}

// Alert API helpers

export interface AlertListResult {
  alerts: import('@/types/radar').RadarAlert[];
  count: number;
  unacknowledged_count: number;
}

export async function getRadarAlerts(
  acknowledged?: boolean
): Promise<AlertListResult> {
  const params: Record<string, unknown> = {};
  if (acknowledged !== undefined) params.acknowledged = acknowledged;
  const response = await apiClient.get<AlertListResult>('/radar/alerts', { params });
  return response.data;
}

export async function acknowledgeRadarAlert(
  alertId: string,
  acknowledgedBy: string
): Promise<import('@/types/radar').RadarAlert> {
  const response = await apiClient.post<import('@/types/radar').RadarAlert>(
    `/radar/alerts/${alertId}/acknowledge`,
    { acknowledged_by: acknowledgedBy }
  );
  return response.data;
}

export async function muteRadarAlert(request: {
  trigger: string;
  source_id?: string;
  expires_at?: string;
}): Promise<import('@/types/radar').AlertMute> {
  const response = await apiClient.post<import('@/types/radar').AlertMute>('/radar/alerts/mute', request);
  return response.data;
}

export async function unmuteRadarAlert(muteId: string): Promise<void> {
  await apiClient.delete(`/radar/alerts/mute/${muteId}`);
}

export async function getRadarAlertMutes(): Promise<{
  mutes: import('@/types/radar').AlertMute[];
  count: number;
}> {
  const response = await apiClient.get<{ mutes: import('@/types/radar').AlertMute[]; count: number }>(
    '/radar/alerts/mutes'
  );
  return response.data;
}

// Digest API helpers

export async function generateRadarDigest(periodStart: string, periodEnd: string): Promise<
  import('@/types/radar').RadarDigest
> {
  const response = await apiClient.post<import('@/types/radar').RadarDigest>('/radar/digests', {
    period_start: periodStart,
    period_end: periodEnd,
  });
  return response.data;
}

export async function getRadarDigests(
  limit: number = 12
): Promise<{ digests: import('@/types/radar').RadarDigest[]; count: number }> {
  const response = await apiClient.get<{ digests: import('@/types/radar').RadarDigest[]; count: number }>(
    '/radar/digests',
    { params: { limit } }
  );
  return response.data;
}

