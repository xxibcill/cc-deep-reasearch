// Radar domain types for the Opportunity Radar feature

export type SourceType =
  | 'news'
  | 'blog'
  | 'changelog'
  | 'forum'
  | 'social'
  | 'competitor'
  | 'custom';

export type SourceStatus = 'active' | 'inactive' | 'error';

export type SourceHealth = 'healthy' | 'degraded' | 'unhealthy';

export type SourcePriority = 'critical' | 'high' | 'medium' | 'low';

export type OpportunityType =
  | 'competitor_move'
  | 'audience_question'
  | 'rising_topic'
  | 'narrative_shift'
  | 'launch_update_change'
  | 'proof_point'
  | 'recurring_pattern';

export type OpportunityStatus =
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

export type OpportunityOwnerPriority = 'critical' | 'high' | 'medium' | 'low';

export type FreshnessState = 'new' | 'fresh' | 'stale' | 'expired';

export type PriorityLabel = 'act_now' | 'high_potential' | 'monitor' | 'low_priority';

export type FeedbackType =
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

export type WorkflowType =
  | 'research_run'
  | 'brief'
  | 'backlog_item'
  | 'content_pipeline';

// Scan job types
export type ScanJobStatus = 'pending' | 'running' | 'completed' | 'failed' | 'skipped' | 'cancelled';

// Alert types
export type AlertSeverity = 'info' | 'warning' | 'critical';
export type AlertTrigger = 'high_priority_opportunity' | 'source_failure' | 'stale_scan' | 'volume_spike' | 'consecutive_failures';

// API response shapes (raw from backend)

export interface ApiRadarSource {
  id: string;
  source_type: string;
  label: string;
  url_or_identifier: string;
  status: string;
  owner: string | null;
  priority: string;
  scan_cadence: string;
  last_scanned_at: string | null;
  last_scan_success: boolean | null;
  last_failure_reason: string | null;
  consecutive_failures: number;
  health: string;
  notes: string | null;
  created_at: string;
  updated_at: string;
  metadata: Record<string, unknown>;
}

export interface ApiOpportunity {
  id: string;
  title: string;
  summary: string;
  opportunity_type: string;
  status: string;
  owner: string | null;
  priority: string;
  reason: string | null;
  next_action: string | null;
  reviewed_at: string | null;
  priority_label: string;
  why_it_matters: string | null;
  recommended_action: string | null;
  total_score: number;
  freshness_state: string;
  created_at: string;
  updated_at: string;
  metadata: Record<string, unknown>;
}

export interface ApiOpportunityScore {
  opportunity_id: string;
  strategic_relevance_score: number;
  novelty_score: number;
  urgency_score: number;
  evidence_score: number;
  business_value_score: number;
  workflow_fit_score: number;
  total_score: number;
  priority_label: string;
  explanation: string | null;
  scored_at: string;
}

export interface ApiOpportunitySignal {
  id: string;
  source_id: string;
  external_id: string | null;
  title: string;
  summary: string | null;
  url: string | null;
  published_at: string | null;
  discovered_at: string;
  content_hash: string | null;
  metadata: Record<string, unknown>;
  normalized_type: string | null;
}

export interface ApiOpportunityFeedback {
  id: string;
  opportunity_id: string;
  feedback_type: string;
  created_at: string;
  metadata: Record<string, unknown>;
}

export interface ApiWorkflowLink {
  id: string;
  opportunity_id: string;
  workflow_type: string;
  workflow_id: string;
  created_at: string;
}

// API response wrappers

export interface SourceListResponse {
  items: ApiRadarSource[];
  count: number;
}

export interface OpportunityListResponse {
  items: ApiOpportunity[];
  count: number;
}

export interface OpportunityDetailResponse {
  opportunity: ApiOpportunity;
  score: ApiOpportunityScore | null;
  signals: ApiOpportunitySignal[];
  feedback: ApiOpportunityFeedback[];
  workflow_links: ApiWorkflowLink[];
}

// Normalized client-side types (with full lifecycle/governance fields)
// See expanded interfaces above for opportunities/governance details

export interface OpportunityScore {
  opportunityId: string;
  strategicRelevanceScore: number;
  noveltyScore: number;
  urgencyScore: number;
  evidenceScore: number;
  businessValueScore: number;
  workflowFitScore: number;
  totalScore: number;
  priorityLabel: PriorityLabel;
  explanation: string | null;
  scoredAt: string;
}

export interface OpportunitySignal {
  id: string;
  sourceId: string;
  externalId: string | null;
  title: string;
  summary: string | null;
  url: string | null;
  publishedAt: string | null;
  discoveredAt: string;
  contentHash: string | null;
  metadata: Record<string, unknown>;
  normalizedType: string | null;
}

export interface OpportunityFeedback {
  id: string;
  opportunityId: string;
  feedbackType: FeedbackType;
  createdAt: string;
  metadata: Record<string, unknown>;
}

export interface WorkflowLink {
  id: string;
  opportunityId: string;
  workflowType: WorkflowType;
  workflowId: string;
  createdAt: string;
}

export interface OpportunityDetail {
  opportunity: Opportunity;
  score: OpportunityScore | null;
  signals: OpportunitySignal[];
  feedback: OpportunityFeedback[];
  workflowLinks: WorkflowLink[];
}

// Normalized RadarSource with governance fields
export interface RadarSource {
  id: string;
  sourceType: SourceType;
  label: string;
  urlOrIdentifier: string;
  status: SourceStatus;
  owner: string | null;
  priority: SourcePriority;
  scanCadence: string;
  lastScannedAt: string | null;
  lastScanSuccess: boolean | null;
  lastFailureReason: string | null;
  consecutiveFailures: number;
  health: SourceHealth;
  notes: string | null;
  createdAt: string;
  updatedAt: string;
  metadata: Record<string, unknown>;
}

// Normalized Opportunity with lifecycle fields
export interface Opportunity {
  id: string;
  title: string;
  summary: string;
  opportunityType: OpportunityType;
  status: OpportunityStatus;
  owner: string | null;
  priority: OpportunityOwnerPriority;
  reason: string | null;
  nextAction: string | null;
  reviewedAt: string | null;
  priorityLabel: PriorityLabel;
  whyItMatters: string | null;
  recommendedAction: string | null;
  totalScore: number;
  freshnessState: FreshnessState;
  createdAt: string;
  updatedAt: string;
  metadata: Record<string, unknown>;
}

// Scan job types
export interface ScanJob {
  id: string;
  sourceId: string | null;
  triggeredBy: string;
  status: ScanJobStatus;
  signalsFound: number;
  errors: string[];
  startedAt: string;
  completedAt: string | null;
  scanType: string;
}

// Alert types
export interface RadarAlert {
  id: string;
  trigger: AlertTrigger;
  severity: AlertSeverity;
  title: string;
  message: string;
  sourceId: string | null;
  opportunityId: string | null;
  acknowledged: boolean;
  acknowledgedBy: string | null;
  acknowledgedAt: string | null;
  createdAt: string;
  metadata: Record<string, unknown>;
}

export interface AlertMute {
  id: string;
  trigger: AlertTrigger;
  sourceId: string | null;
  mutedBy: string | null;
  mutedAt: string;
  expiresAt: string | null;
}

// Digest types
export interface RadarDigest {
  id: string;
  periodStart: string;
  periodEnd: string;
  newOpportunitiesCount: number;
  topOpportunities: Record<string, unknown>[];
  sourceHealthIssues: Record<string, unknown>[];
  alertCount: number;
  createdAt: string;
}

// Scoring feedback types
export interface ScoringFeedback {
  id: string;
  opportunityId: string;
  signalId: string | null;
  feedbackType: FeedbackType;
  scoringFeatures: Record<string, number>;
  rankPosition: number | null;
  outcome: string | null;
  createdAt: string;
}

// Source health response
export interface SourceHealthDetails {
  sourceId: string;
  health: SourceHealth;
  consecutiveFailures: number;
  lastFailureReason: string | null;
  lastScanSuccess: boolean | null;
  lastScannedAt: string | null;
  recentJobs: {
    id: string;
    status: string;
    signalsFound: number;
    startedAt: string;
    completedAt: string | null;
  }[];
}

// List result shapes

export interface SourceListResult {
  sources: RadarSource[];
  total: number;
}

export interface OpportunityListResult {
  opportunities: Opportunity[];
  total: number;
}