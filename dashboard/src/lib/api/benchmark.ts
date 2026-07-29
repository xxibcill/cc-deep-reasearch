import { apiClient } from '@/lib/api/client';

export interface BenchmarkCorpus {
  version: string;
  description: string;
  cases: BenchmarkCase[];
}

export interface BenchmarkCase {
  case_id: string;
  query: string;
  category: string;
  rationale: string;
  date_sensitive: boolean;
  tags: string[];
  status: string;
  owner: string | null;
  domain: string | null;
  difficulty: string | null;
  review_notes: string | null;
  expected_capabilities: string[];
}

export interface BenchmarkRun {
  run_id: string;
  path: string;
  corpus_version?: string;
  generated_at?: string;
  configuration?: Record<string, unknown>;
  total_cases?: number;
  average_validation_score?: number | null;
  average_latency_ms?: number | null;
}

export interface BenchmarkRunReport {
  harness_version: string;
  corpus_version: string;
  generated_at: string;
  configuration: Record<string, unknown>;
  scorecard: BenchmarkScorecard;
  cases: BenchmarkCaseReport[];
}

export interface BenchmarkScorecard {
  total_cases: number;
  average_source_count: number;
  average_unique_domains: number;
  average_source_type_diversity: number;
  average_iteration_count: number;
  average_latency_ms: number;
  average_validation_score: number | null;
  date_sensitive_cases: number;
  stop_reasons: Record<string, number>;
  categories: Record<string, number>;
}

export interface BenchmarkCaseReport {
  case_id: string;
  query: string;
  category: string;
  rationale: string;
  date_sensitive: boolean;
  tags: string[];
  status: string;
  owner: string | null;
  domain: string | null;
  difficulty: string | null;
  review_notes: string | null;
  expected_capabilities: string[];
  metrics: {
    source_count: number;
    unique_domains: number;
    source_type_diversity: number;
    iteration_count: number;
    latency_ms: number;
    validation_score: number | null;
  };
  session_id?: string;
  configured_depth: string;
  stop_reason: string;
  validation_issues: string[];
  failure_modes: string[];
  source_domains: string[];
  source_types: string[];
}

export interface BenchmarkRunsResponse {
  runs: BenchmarkRun[];
  total: number;
}

export async function getBenchmarkCorpus(): Promise<BenchmarkCorpus> {
  const response = await apiClient.get<BenchmarkCorpus>('/benchmarks/corpus');
  return response.data;
}

export async function listBenchmarkRuns(): Promise<BenchmarkRunsResponse> {
  const response = await apiClient.get<BenchmarkRunsResponse>('/benchmarks/runs');
  return response.data;
}

export async function getBenchmarkRun(runId: string): Promise<BenchmarkRunReport> {
  const response = await apiClient.get<BenchmarkRunReport>(`/benchmarks/runs/${runId}`);
  return response.data;
}

export async function getBenchmarkCaseReport(
  runId: string,
  caseId: string
): Promise<BenchmarkCaseReport> {
  const response = await apiClient.get<BenchmarkCaseReport>(
    `/benchmarks/runs/${runId}/cases/${caseId}`
  );
  return response.data;
}

export interface BenchmarkRunResult {
  run_id: string;
  output_dir: string;
  total_cases: number;
  workflow_mode: string;
  average_validation_score: number | null;
}

export async function runBenchmark(
  workflowMode: string = 'staged',
  depth: string = 'standard',
  outputDir?: string
): Promise<BenchmarkRunResult> {
  const params: Record<string, unknown> = { workflow_mode: workflowMode, depth };
  if (outputDir) params.output_dir = outputDir;
  const response = await apiClient.post<BenchmarkRunResult>('/benchmarks/run', null, { params });
  return response.data;
}

export interface BenchmarkComparisonReport {
  run1_path: string;
  run2_path: string;
  generated_at: string;
  delta_source_count: number;
  delta_unique_domains: number;
  delta_source_type_diversity: number;
  delta_iteration_count: number;
  delta_latency_ms: number;
  delta_validation_score: number | null;
  delta_report_quality_score: number | null;
  delta_unsupported_claim_count: number;
  delta_citation_error_count: number;
  delta_hydration_success_rate: number | null;
  run1_workflow_mode: string;
  run2_workflow_mode: string;
  case_deltas: Array<{
    case_id: string;
    delta_source_count: number;
    delta_validation_score: number | null;
    delta_stop_reason: string;
  }>;
}

export async function compareBenchmark(
  run1Path: string,
  run2Path: string
): Promise<BenchmarkComparisonReport> {
  const response = await apiClient.post<BenchmarkComparisonReport>('/benchmarks/compare', null, {
    params: { run1_path: run1Path, run2_path: run2Path },
  });
  return response.data;
}

export interface BenchmarkValidateResponse {
  valid: boolean;
  errors: Record<string, string[]>;
  total_cases: number;
}

export async function validateBenchmarkCorpus(): Promise<BenchmarkValidateResponse> {
  const response = await apiClient.get<BenchmarkValidateResponse>('/benchmarks/validate');
  return response.data;
}

export interface BenchmarkGateResult {
  outcome: 'pass' | 'warning' | 'fail';
  baseline_run_id: string;
  candidate_run_id: string;
  generated_at: string;
  baseline_score: number | null;
  candidate_score: number | null;
  delta_score: number | null;
  baseline_pass_rate: number;
  candidate_pass_rate: number;
  delta_pass_rate: number;
  baseline_avg_latency_ms: number;
  candidate_avg_latency_ms: number;
  delta_latency_ms: number;
  failing_cases: Array<{
    case_id: string;
    baseline_stop_reason: string;
    candidate_stop_reason: string;
    candidate_validation_score: number | null;
  }>;
  regressions: Array<{
    case_id: string;
    baseline_score: number;
    candidate_score: number;
    delta: number;
  }>;
  overridden: boolean;
  override_notes: string | null;
}

export interface BenchmarkGateParams {
  baselinePath: string;
  candidatePath: string;
  minPassRate?: number;
  minValidationScore?: number;
  maxLatencyIncreaseRatio?: number;
  overrideNotes?: string | null;
}

export async function evaluateBenchmarkGate(params: BenchmarkGateParams): Promise<BenchmarkGateResult> {
  const queryParams: Record<string, unknown> = {
    baseline_path: params.baselinePath,
    candidate_path: params.candidatePath,
  };
  if (params.minPassRate !== undefined) queryParams.min_pass_rate = params.minPassRate;
  if (params.minValidationScore !== undefined) queryParams.min_validation_score = params.minValidationScore;
  if (params.maxLatencyIncreaseRatio !== undefined) queryParams.max_latency_increase_ratio = params.maxLatencyIncreaseRatio;
  if (params.overrideNotes !== undefined) queryParams.override_notes = params.overrideNotes;
  const response = await apiClient.post<BenchmarkGateResult>('/benchmarks/gate', null, { params: queryParams });
  return response.data;
}

export interface BaselineMetadata {
  run_id: string;
  run_path: string;
  owner: string | null;
  approved_at: string;
  approval_note: string | null;
  is_promoted: boolean;
}

export interface ListBaselinesResponse {
  baselines: BaselineMetadata[];
  total: number;
}

export async function listBenchmarkBaselines(): Promise<ListBaselinesResponse> {
  const response = await apiClient.get<ListBaselinesResponse>('/benchmarks/baselines');
  return response.data;
}

export async function getBenchmarkBaseline(runId: string): Promise<BaselineMetadata> {
  const response = await apiClient.get<BaselineMetadata>(`/benchmarks/baselines/${runId}`);
  return response.data;
}

export async function promoteBenchmarkBaseline(
  runId: string,
  owner?: string,
  approvalNote?: string
): Promise<BaselineMetadata> {
  const params: Record<string, unknown> = {};
  if (owner) params.owner = owner;
  if (approvalNote) params.approval_note = approvalNote;
  const response = await apiClient.post<BaselineMetadata>(`/benchmarks/baselines/${runId}/promote`, null, { params });
  return response.data;
}

export async function deleteBenchmarkBaseline(runId: string): Promise<{ deleted: boolean; run_id: string }> {
  const response = await apiClient.delete<{ deleted: boolean; run_id: string }>(`/benchmarks/baselines/${runId}`);
  return response.data;
}

export async function getPromotedBenchmarkBaseline(): Promise<{ baseline: BaselineMetadata | null }> {
  const response = await apiClient.get<{ baseline: BaselineMetadata | null }>('/benchmarks/baselines/promoted');
  return response.data;
}

export interface ResearchThemeInfo {
  theme: string;
  display_name: string;
  description: string;
  source: 'builtin' | 'custom';
}

export interface ThemesListResponse {
  themes: ResearchThemeInfo[];
  total: number;
}

export interface BenchmarkTrendRun {
  run_id: string;
  generated_at: string | null;
  corpus_version: string | null;
  workflow_mode: string | null;
  total_cases: number;
  pass_count: number;
  pass_rate: number | null;
  average_validation_score: number | null;
  average_latency_ms: number | null;
  average_report_quality_score: number | null;
  average_source_count: number | null;
  date_sensitive_cases: number;
  stop_reasons: Record<string, number>;
  categories: Record<string, number>;
}

export interface BenchmarkTrendsResponse {
  runs: BenchmarkTrendRun[];
  total: number;
}

export async function getBenchmarkTrends(limit = 10): Promise<BenchmarkTrendsResponse> {
  const response = await apiClient.get<BenchmarkTrendsResponse>('/benchmarks/trends', {
    params: { limit },
  });
  return response.data;
}

export async function listResearchThemes(): Promise<ThemesListResponse> {
  const response = await apiClient.get<ThemesListResponse>('/themes');
  return response.data;
}
