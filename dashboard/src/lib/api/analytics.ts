import { apiClient } from '@/lib/api/client';

export interface AnalyticsSummary {
  total_runs: number;
  completed_runs: number;
  failed_runs: number;
  interrupted_runs: number;
  avg_duration_ms: number;
  avg_sources: number;
  report_availability_rate: number;
  archived_sessions: number;
  active_sessions: number;
}

export interface StatusCount {
  status: string;
  count: number;
}

export interface DurationByStatus {
  status: string;
  avg_duration_ms: number;
  min_duration_ms: number;
  max_duration_ms: number;
  count: number;
}

export interface SourcesTrend {
  day: string | null;
  run_count: number;
  avg_sources: number;
  total_sources: number;
}

export interface DailyVolume {
  day: string | null;
  total_runs: number;
  completed: number;
  failed: number;
  interrupted: number;
}

export interface DepthDistribution {
  depth: string;
  count: number;
  avg_duration_ms: number;
}

export interface AnalyticsResponse {
  summary: AnalyticsSummary;
  status_counts: StatusCount[];
  duration_by_status: DurationByStatus[];
  sources_trend: SourcesTrend[];
  daily_volume: DailyVolume[];
  depth_distribution: DepthDistribution[];
}

export async function getAnalytics(daysBack: number = 30): Promise<AnalyticsResponse> {
  const response = await apiClient.get<AnalyticsResponse>('/analytics', {
    params: { days_back: daysBack },
  });
  return response.data;
}
