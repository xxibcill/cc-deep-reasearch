import { contentGenClient, getContentGenErrorMessage } from './client';
import type {
  StartPipelineRequest,
  PipelineRunSummary,
  PipelineContext,
  ApproveQCRequest,
} from '@/types/content-gen';

interface PipelineRunDetailResponse extends PipelineRunSummary {
  context?: PipelineContext;
}

function emptyPipelineContext(summary: PipelineRunSummary): PipelineContext {
  return {
    pipeline_id: summary.pipeline_id,
    theme: summary.theme,
    created_at: summary.created_at,
    current_stage: summary.current_stage,
    strategy: null,
    opportunity_brief: null,
    run_constraints: null,
    backlog: null,
    scoring: null,
    shortlist: [],
    selected_idea_id: '',
    selection_reasoning: '',
    runner_up_idea_ids: [],
    angles: null,
    research_pack: null,
    argument_map: null,
    fact_risk_gate: null,
    scripting: null,
    visual_plan: null,
    production_brief: null,
    execution_brief: null,
    packaging: null,
    qc_gate: null,
    publish_items: [],
    publish_item: null,
    performance: null,
    iteration_state: null,
    stage_traces: [],
    lane_contexts: [],
  };
}

export async function startPipeline(
  req: StartPipelineRequest,
): Promise<{ pipeline_id: string; [key: string]: unknown }> {
  try {
    const response = await contentGenClient.post('/pipelines', req);
    return response.data;
  } catch (error) {
    throw new Error(getContentGenErrorMessage(error, 'Failed to start pipeline.'));
  }
}

export async function listPipelines(): Promise<PipelineRunSummary[]> {
  try {
    const response = await contentGenClient.get('/pipelines');
    return response.data.items ?? response.data;
  } catch (error) {
    throw new Error(getContentGenErrorMessage(error, 'Failed to list pipelines.'));
  }
}

export async function getPipeline(id: string): Promise<PipelineContext> {
  try {
    const response = await contentGenClient.get<PipelineRunDetailResponse>(`/pipelines/${id}`);
    return response.data.context ?? emptyPipelineContext(response.data);
  } catch (error) {
    throw new Error(getContentGenErrorMessage(error, 'Failed to get pipeline.'));
  }
}

export async function stopPipeline(id: string): Promise<void> {
  try {
    await contentGenClient.post(`/pipelines/${id}/stop`);
  } catch (error) {
    throw new Error(getContentGenErrorMessage(error, 'Failed to stop pipeline.'));
  }
}

export async function resumePipeline(
  id: string,
  req?: { from_stage?: number },
): Promise<{ pipeline_id: string; [key: string]: unknown }> {
  try {
    const response = await contentGenClient.post(`/pipelines/${id}/resume`, req);
    return response.data;
  } catch (error) {
    throw new Error(getContentGenErrorMessage(error, 'Failed to resume pipeline.'));
  }
}

export async function approveQC(pipelineId: string, req?: ApproveQCRequest): Promise<void> {
  try {
    await contentGenClient.post(`/qc/${pipelineId}/approve`, req ?? {});
  } catch (error) {
    throw new Error(getContentGenErrorMessage(error, 'Failed to approve QC.'));
  }
}