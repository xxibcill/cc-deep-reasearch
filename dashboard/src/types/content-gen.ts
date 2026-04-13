// ---------------------------------------------------------------------------
// Content Generation Pipeline Types
// Mirrors the Pydantic models from src/cc_deep_research/content_gen/models.py
// and the request/response shapes from the API router.
// ---------------------------------------------------------------------------

// =============================================================================
// String literal type aliases
// =============================================================================

export type PipelineRunStatus =
  | 'queued'
  | 'running'
  | 'completed'
  | 'failed'
  | 'cancelled';

export type BacklogCategory =
  | 'trend-responsive'
  | 'evergreen'
  | 'authority-building';

export type RiskLevel = 'low' | 'medium' | 'high';

export type BacklogItemStatus =
  | 'backlog'
  | 'selected'
  | 'runner_up'
  | 'in_production'
  | 'published'
  | 'archived';

export type ScoreRecommendation = 'produce_now' | 'hold' | 'kill';

export type HookStrength = 'strong' | 'adequate' | 'weak';

export type PublishItemStatus = 'scheduled' | 'published';
export type PipelineTraceStatus = 'completed' | 'skipped' | 'failed';

// =============================================================================
// Pipeline stage & scripting step constants (mirrors Python lists)
// =============================================================================

export type PipelineStageName =
  | 'load_strategy'
  | 'plan_opportunity'
  | 'build_backlog'
  | 'score_ideas'
  | 'generate_angles'
  | 'build_research_pack'
  | 'build_argument_map'
  | 'run_scripting'
  | 'visual_translation'
  | 'production_brief'
  | 'packaging'
  | 'human_qc'
  | 'publish_queue'
  | 'performance_analysis';

export const PIPELINE_STAGE_ORDER: PipelineStageName[] = [
  'load_strategy',
  'plan_opportunity',
  'build_backlog',
  'score_ideas',
  'generate_angles',
  'build_research_pack',
  'build_argument_map',
  'run_scripting',
  'visual_translation',
  'production_brief',
  'packaging',
  'human_qc',
  'publish_queue',
  'performance_analysis',
];

export const PIPELINE_STAGE_SHORT_LABELS: Record<PipelineStageName, string> = {
  load_strategy: 'Load Strategy',
  plan_opportunity: 'Plan Opportunity',
  build_backlog: 'Build Backlog',
  score_ideas: 'Score Ideas',
  generate_angles: 'Generate Angles',
  build_research_pack: 'Build Research',
  build_argument_map: 'Argument Map',
  run_scripting: 'Run Scripting',
  visual_translation: 'Visual Translation',
  production_brief: 'Production Brief',
  packaging: 'Packaging',
  human_qc: 'Human QC',
  publish_queue: 'Publish Queue',
  performance_analysis: 'Performance',
};

export const TOTAL_PIPELINE_STAGES = PIPELINE_STAGE_ORDER.length;

export type ScriptingStepName =
  | 'define_core_inputs'
  | 'define_angle'
  | 'choose_structure'
  | 'define_beat_intents'
  | 'generate_hooks'
  | 'draft_script'
  | 'add_retention_mechanics'
  | 'tighten'
  | 'add_visual_notes'
  | 'run_qc';

// =============================================================================
// Pipeline run progress
// =============================================================================

export interface StageProgress {
  stageIndex: number;
  stageName: PipelineStageName;
  label: string;
  startedAt: string | null;
  completedAt: string | null;
}

export interface PipelineRunSummary {
  pipeline_id: string;
  theme: string;
  from_stage: number;
  to_stage: number | null;
  status: PipelineRunStatus;
  current_stage: number;
  error: string | null;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
}

// =============================================================================
// Strategy (stage 0)
// =============================================================================

export interface AudienceSegment {
  name: string;
  description: string;
  pain_points: string[];
}

export interface ContentExample {
  title: string;
  why_it_worked_or_failed: string;
  metrics_snapshot: Record<string, unknown>;
}

export interface StrategyMemory {
  niche: string;
  content_pillars: string[];
  audience_segments: AudienceSegment[];
  tone_rules: string[];
  offer_cta_rules: string[];
  platforms: string[];
  forbidden_claims: string[];
  proof_standards: string[];
  past_winners: ContentExample[];
  past_losers: ContentExample[];
}

// =============================================================================
// Opportunity brief (stage 1)
// =============================================================================

export interface OpportunityBrief {
  theme: string;
  goal: string;
  primary_audience_segment: string;
  secondary_audience_segments: string[];
  problem_statements: string[];
  content_objective: string;
  proof_requirements: string[];
  platform_constraints: string[];
  risk_constraints: string[];
  freshness_rationale: string;
  sub_angles: string[];
  research_hypotheses: string[];
  success_criteria: string[];
}

// =============================================================================
// Backlog (stage 1)
// =============================================================================

export interface BacklogItem {
  idea_id: string;
  category: BacklogCategory | string;
  idea: string;
  audience: string;
  problem: string;
  source: string;
  why_now: string;
  potential_hook: string;
  content_type: string;
  evidence: string;
  risk_level: RiskLevel | string;
  priority_score: number;
  status: BacklogItemStatus | string;
  created_at?: string;
  updated_at?: string;
  selection_reasoning?: string;
  latest_score?: number;
  latest_recommendation?: string;
  source_theme?: string;
  expertise_reason?: string;
  genericity_risk?: string;
  proof_gap_note?: string;
  source_pipeline_id?: string;
  last_scored_at?: string;
}

export interface BacklogOutput {
  items: BacklogItem[];
  rejected_count: number;
  rejection_reasons: string[];
  is_degraded: boolean;
  degradation_reason: string;
}

export interface BacklogListResponse {
  path: string;
  items: BacklogItem[];
}

// =============================================================================
// Scoring (stage 2)
// =============================================================================

export interface IdeaScores {
  idea_id: string;
  relevance: number;
  novelty: number;
  authority_fit: number;
  production_ease: number;
  evidence_strength: number;
  hook_strength: number;
  repurposing: number;
  total_score: number;
  recommendation: ScoreRecommendation | string;
  reason: string;
}

export interface ScoringOutput {
  scores: IdeaScores[];
  produce_now: string[];
  shortlist: string[];
  selected_idea_id: string;
  selection_reasoning: string;
  runner_up_idea_ids: string[];
  hold: string[];
  killed: string[];
  is_degraded: boolean;
  degradation_reason: string;
}

// =============================================================================
// Angles (stage 3)
// =============================================================================

export interface AngleOption {
  angle_id: string;
  target_audience: string;
  viewer_problem: string;
  core_promise: string;
  primary_takeaway: string;
  lens: string;
  format: string;
  tone: string;
  cta: string;
  why_this_version_should_exist: string;
}

export interface AngleOutput {
  idea_id: string;
  angle_options: AngleOption[];
  selected_angle_id: string;
  selection_reasoning: string;
}

// =============================================================================
// Research (stage 4)
// =============================================================================

export interface ResearchPack {
  idea_id: string;
  angle_id: string;
  audience_insights: string[];
  competitor_observations: string[];
  key_facts: string[];
  proof_points: string[];
  examples: string[];
  case_studies: string[];
  gaps_to_exploit: string[];
  assets_needed: string[];
  claims_requiring_verification: string[];
  unsafe_or_uncertain_claims: string[];
  research_stop_reason: string;
}

// =============================================================================
// Argument map (stage 5)
// =============================================================================

export interface ArgumentProofAnchor {
  proof_id: string;
  summary: string;
  source_ids: string[];
  usage_note: string;
}

export interface ArgumentCounterargument {
  counterargument_id: string;
  counterargument: string;
  response: string;
  response_proof_ids: string[];
}

export interface ArgumentClaim {
  claim_id: string;
  claim: string;
  supporting_proof_ids: string[];
  note: string;
}

export interface ArgumentBeatClaim {
  beat_id: string;
  beat_name: string;
  goal: string;
  claim_ids: string[];
  proof_anchor_ids: string[];
  counterargument_ids: string[];
  transition_note: string;
}

export interface ArgumentMap {
  idea_id: string;
  angle_id: string;
  thesis: string;
  audience_belief_to_challenge: string;
  core_mechanism: string;
  proof_anchors: ArgumentProofAnchor[];
  counterarguments: ArgumentCounterargument[];
  safe_claims: ArgumentClaim[];
  unsafe_claims: ArgumentClaim[];
  beat_claim_plan: ArgumentBeatClaim[];
  what_this_contributes?: string;
  genericity_flags?: string[];
  differentiation_stategy?: string;
}

// =============================================================================
// Scripting (stage 6)
// =============================================================================

export interface CoreInputs {
  topic: string;
  outcome: string;
  audience: string;
}

export interface AngleDefinition {
  angle: string;
  content_type: string;
  core_tension: string;
  why_it_works: string;
}

export interface ScriptStructure {
  chosen_structure: string;
  why_it_fits: string;
  beat_list: string[];
}

export interface BeatIntent {
  beat_name: string;
  intent: string;
}

export interface BeatIntentMap {
  beats: BeatIntent[];
}

export interface HookSet {
  hooks: string[];
  best_hook: string;
  best_hook_reason: string;
}

export interface ScriptVersion {
  content: string;
  word_count: number;
}

export interface VisualNote {
  beat_name: string;
  line: string;
  note: string | null;
}

export interface QCCheck {
  item: string;
  passed: boolean;
}

export interface QCResult {
  checks: QCCheck[];
  weakest_parts: string[];
  final_script: string;
}

export interface ScriptingLLMCallTrace {
  call_index: number;
  temperature: number;
  system_prompt: string;
  user_prompt: string;
  raw_response: string;
  provider: string;
  model: string;
  transport: string;
  latency_ms: number;
  prompt_tokens: number;
  completion_tokens: number;
  finish_reason: string | null;
}

export interface ScriptingStepTrace {
  step_index: number;
  step_name: string;
  step_label: string;
  iteration: number;
  llm_calls: ScriptingLLMCallTrace[];
  parsed_output: unknown;
}

export interface ScriptingContext {
  raw_idea: string;
  research_context: string;
  tone: string;
  cta: string;
  core_inputs: CoreInputs | null;
  angle: AngleDefinition | null;
  structure: ScriptStructure | null;
  beat_intents: BeatIntentMap | null;
  hooks: HookSet | null;
  draft: ScriptVersion | null;
  retention_revised: ScriptVersion | null;
  tightened: ScriptVersion | null;
  annotated_script: ScriptVersion | null;
  visual_notes: VisualNote[] | null;
  qc: QCResult | null;
  step_traces: ScriptingStepTrace[];
}

export interface SavedScriptRun {
  run_id: string;
  saved_at: string;
  raw_idea: string;
  word_count: number;
  script_path: string;
  context_path: string;
  result_path?: string | null;
  execution_mode: 'single_pass' | 'iterative';
  iterations?: ScriptingIterations | null;
}

// =============================================================================
// Visual translation (stage 7)
// =============================================================================

export interface BeatVisual {
  beat: string;
  spoken_line: string;
  visual: string;
  shot_type: string;
  a_roll: string;
  b_roll: string;
  on_screen_text: string;
  overlay_or_graphic: string;
  prop_or_asset: string;
  transition: string;
  retention_function: string;
}

export interface VisualPlanOutput {
  idea_id: string;
  angle_id: string;
  visual_plan: BeatVisual[];
  visual_refresh_check: string;
}

// =============================================================================
// Production brief (stage 8)
// =============================================================================

export interface ProductionBrief {
  idea_id: string;
  location: string;
  setup: string;
  wardrobe: string;
  props: string[];
  assets_to_prepare: string[];
  audio_checks: string[];
  battery_checks: string[];
  storage_checks: string[];
  pickup_lines_to_capture: string[];
  backup_plan: string;
}

// =============================================================================
// Packaging (stage 9)
// =============================================================================

export interface PlatformPackage {
  platform: string;
  primary_hook: string;
  alternate_hooks: string[];
  cover_text: string;
  caption: string;
  keywords: string[];
  hashtags: string[];
  pinned_comment: string;
  cta: string;
  version_notes: string;
}

export interface PackagingOutput {
  idea_id: string;
  platform_packages: PlatformPackage[];
}

// =============================================================================
// Human QC gate (stage 10)
// =============================================================================

export interface HumanQCGate {
  review_round: number;
  hook_strength: HookStrength | string;
  clarity_issues: string[];
  factual_issues: string[];
  visual_issues: string[];
  audio_issues: string[];
  caption_issues: string[];
  must_fix_items: string[];
  approved_for_publish: boolean;
}

// =============================================================================
// Publish queue (stage 11)
// =============================================================================

export interface PublishItem {
  idea_id: string;
  platform: string;
  publish_datetime: string;
  asset_version: string;
  caption_version: string;
  pinned_comment: string;
  cross_post_targets: string[];
  first_30_minute_engagement_plan: string;
  status: PublishItemStatus | string;
}

// =============================================================================
// Performance analysis (stage 12)
// =============================================================================

export interface PerformanceAnalysis {
  video_id: string;
  metrics: Record<string, unknown>;
  what_worked: string[];
  what_failed: string[];
  audience_signals: string[];
  dropoff_hypotheses: string[];
  hook_diagnosis: string;
  lesson: string;
  next_test: string;
  follow_up_ideas: string[];
  backlog_updates: string[];
}

export interface QualityEvaluation {
  overall_quality_score: number;
  passes_threshold: boolean;
  hook_quality: number;
  content_clarity: number;
  factual_accuracy: number;
  audience_alignment: number;
  production_readiness: number;
  critical_issues: string[];
  improvement_suggestions: string[];
  research_gaps_identified: string[];
  rationale: string;
  iteration_number: number;
}

export interface IterationState {
  current_iteration: number;
  max_iterations: number;
  quality_history: QualityEvaluation[];
  latest_feedback: string;
  is_converged: boolean;
  convergence_reason: string;
  should_rerun_research: boolean;
}

export interface StageTraceMetadata {
  selected_idea_id?: string;
  selected_angle_id?: string;
  shortlist_count?: number;
  option_count?: number;
  is_degraded?: boolean;
  degradation_reason?: string;
  fact_count?: number;
  proof_count?: number;
  claim_count?: number;
  unsafe_claim_count?: number;
  cache_reused?: boolean;
  step_count?: number;
  llm_call_count?: number;
  final_word_count?: number;
  current_iteration?: number;
  latest_quality_score?: number;
  should_rerun_research?: boolean;
  beats_count?: number;
  platforms_count?: number;
  approved?: boolean;
  active_candidate_count?: number;
}

export interface PipelineStageTrace {
  stage_index: number;
  stage_name: PipelineStageName | string;
  stage_label: string;
  status: PipelineTraceStatus | string;
  started_at: string;
  completed_at: string;
  duration_ms: number;
  input_summary: string;
  output_summary: string;
  warnings: string[];
  decision_summary: string;
  metadata: StageTraceMetadata;
}

// =============================================================================
// Full pipeline context
// =============================================================================

export interface PipelineContext {
  pipeline_id: string;
  theme: string;
  created_at: string;
  current_stage: number;
  strategy: StrategyMemory | null;
  opportunity_brief: OpportunityBrief | null;
  backlog: BacklogOutput | null;
  scoring: ScoringOutput | null;
  shortlist: string[];
  selected_idea_id: string;
  selection_reasoning: string;
  runner_up_idea_ids: string[];
  angles: AngleOutput | null;
  research_pack: ResearchPack | null;
  argument_map: ArgumentMap | null;
  scripting: ScriptingContext | null;
  visual_plan: VisualPlanOutput | null;
  production_brief: ProductionBrief | null;
  packaging: PackagingOutput | null;
  qc_gate: HumanQCGate | null;
  publish_items?: PublishItem[];
  publish_item: PublishItem | null;
  performance: PerformanceAnalysis | null;
  iteration_state: IterationState | null;
  stage_traces: PipelineStageTrace[];
}

// =============================================================================
// API request types
// =============================================================================

export interface StartPipelineRequest {
  theme: string;
  from_stage?: number;
  to_stage?: number | null;
}

export interface ResumePipelineRequest {
  from_stage?: number;
}

export interface RunScriptingRequest {
  idea: string;
  iterative_mode?: boolean | null;
  max_iterations?: number | null;
  llm_route?: 'openrouter' | 'cerebras' | 'anthropic' | 'heuristic' | null;
}

export interface ScriptingIterationSummary {
  iteration: number;
  score: number;
  passes: boolean;
}

export interface ScriptingIterations {
  count: number;
  max_iterations: number;
  converged: boolean;
  quality_history: ScriptingIterationSummary[];
}

export interface RunScriptingResponse {
  run_id?: string;
  raw_idea: string;
  script: string;
  word_count: number;
  context: ScriptingContext;
  execution_mode: 'single_pass' | 'iterative';
  iterations?: ScriptingIterations;
}

export interface UpdateStrategyRequest {
  patch: Record<string, unknown>;
}

// =============================================================================
// WebSocket events
// =============================================================================

export interface PipelineStageStartedEvent {
  type: 'pipeline_stage_started';
  stage_index: number;
  stage_label: string;
  timestamp: string;
}

export interface PipelineStageCompletedEvent {
  type: 'pipeline_stage_completed';
  stage_index: number;
  stage_status: PipelineTraceStatus;
  stage_detail: string;
  timestamp: string;
}

export interface PipelineStageFailedEvent {
  type: 'pipeline_stage_failed';
  stage_index: number;
  stage_label: string;
  error: string;
  timestamp: string;
}

export interface PipelineStageSkippedEvent {
  type: 'pipeline_stage_skipped';
  stage_index: number;
  stage_label: string;
  reason: string;
  timestamp: string;
}

export interface PipelineCompletedEvent {
  type: 'pipeline_completed';
  current_stage: number;
  timestamp: string;
}

export interface PipelineErrorEvent {
  type: 'pipeline_error';
  error: string;
  timestamp: string;
}

export interface ScriptingStepEvent {
  type: 'scripting_step';
  step_index: number;
  step_name: ScriptingStepName;
  step_label: string;
  timestamp: string;
}

export interface PipelineStatusEvent {
  type: 'pipeline_status';
  pipeline_id: string;
  status: PipelineRunStatus;
  current_stage?: number;
  context?: PipelineContext;
}

export interface PipelineCancelledEvent {
  type: 'pipeline_cancelled';
  timestamp: string;
}

export type ContentGenWebSocketEvent =
  | PipelineStageStartedEvent
  | PipelineStageCompletedEvent
  | PipelineStageFailedEvent
  | PipelineStageSkippedEvent
  | PipelineCompletedEvent
  | PipelineErrorEvent
  | ScriptingStepEvent
  | PipelineStatusEvent
  | PipelineCancelledEvent;

export interface ContentGenWebSocketMessage {
  type: 'ping' | 'get_pipeline_status';
}

// =============================================================================
// Backlog Chat Types
// =============================================================================

export interface BacklogChatMessage {
  role: 'user' | 'assistant';
  content: string;
}

export interface BacklogChatOperation {
  kind: 'update_item' | 'create_item';
  idea_id?: string | null;
  reason: string;
  fields: Record<string, unknown>;
}

export interface BacklogChatRespondRequest {
  messages: BacklogChatMessage[];
  backlog_items: BacklogItem[];
  strategy?: Record<string, unknown> | null;
  selected_idea_id?: string | null;
}

export interface BacklogChatRespondResponse {
  reply_markdown: string;
  apply_ready: boolean;
  warnings: string[];
  operations: BacklogChatOperation[];
  mentioned_idea_ids: string[];
}

export interface BacklogChatApplyRequest {
  operations: BacklogChatOperation[];
}

export interface BacklogChatApplyResponse {
  applied: number;
  items: BacklogItem[];
  errors: string[];
}
