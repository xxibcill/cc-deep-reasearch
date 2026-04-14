import axios from 'axios';
import { dashboardRuntimeConfig } from '@/lib/runtime-config';
import { getApiErrorMessage } from '@/lib/api';
import type {
  PipelineRunSummary,
  PipelineContext,
  StrategyMemory,
  SavedScriptRun,
  PublishItem,
  StartPipelineRequest,
  ResumePipelineRequest,
  RunScriptingRequest,
  RunScriptingResponse,
  BacklogItem,
  BacklogChatMessage,
  BacklogChatOperation,
  BacklogChatRespondRequest,
  BacklogChatRespondResponse,
  BacklogChatApplyRequest,
  BacklogChatApplyResponse,
  TriageRespondRequest,
  TriageRespondResponse,
  TriageApplyRequest,
  TriageApplyResponse,
  NextActionRequest,
  NextActionResponse,
  NextActionBatchResponse,
  ExecutionBriefRequest,
  ExecutionBriefResponse,
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
    backlog: null,
    scoring: null,
    shortlist: [],
    selected_idea_id: '',
    selection_reasoning: '',
    runner_up_idea_ids: [],
    angles: null,
    research_pack: null,
    argument_map: null,
    scripting: null,
    visual_plan: null,
    production_brief: null,
    packaging: null,
    qc_gate: null,
    publish_items: [],
    publish_item: null,
    performance: null,
    iteration_state: null,
    stage_traces: [],
  };
}

// ---------------------------------------------------------------------------
// Client
// ---------------------------------------------------------------------------

const CONTENT_GEN_TIMEOUT_MS = 30000;
/** Timeout for scripting operations (4 minutes). Script generation can be slow due to LLM inference. */
const SCRIPTING_TIMEOUT_MS = 240000;

const contentGenClient = axios.create({
  baseURL: `${dashboardRuntimeConfig.apiBaseUrl}/content-gen`,
  timeout: CONTENT_GEN_TIMEOUT_MS,
});

// ---------------------------------------------------------------------------
// Pipeline endpoints
// ---------------------------------------------------------------------------

export async function startPipeline(
  req: StartPipelineRequest,
): Promise<{ pipeline_id: string; [key: string]: unknown }> {
  try {
    const response = await contentGenClient.post('/pipelines', req);
    return response.data;
  } catch (error) {
    throw new Error(getApiErrorMessage(error, 'Failed to start pipeline.'));
  }
}

export async function listPipelines(): Promise<PipelineRunSummary[]> {
  try {
    const response = await contentGenClient.get('/pipelines');
    return response.data.items ?? response.data;
  } catch (error) {
    throw new Error(getApiErrorMessage(error, 'Failed to list pipelines.'));
  }
}

export async function getPipeline(id: string): Promise<PipelineContext> {
  try {
    const response = await contentGenClient.get<PipelineRunDetailResponse>(`/pipelines/${id}`);
    return response.data.context ?? emptyPipelineContext(response.data);
  } catch (error) {
    throw new Error(getApiErrorMessage(error, 'Failed to get pipeline.'));
  }
}

export async function stopPipeline(id: string): Promise<void> {
  try {
    await contentGenClient.post(`/pipelines/${id}/stop`);
  } catch (error) {
    throw new Error(getApiErrorMessage(error, 'Failed to stop pipeline.'));
  }
}

export async function resumePipeline(
  id: string,
  req?: ResumePipelineRequest,
): Promise<{ pipeline_id: string; [key: string]: unknown }> {
  try {
    const response = await contentGenClient.post(`/pipelines/${id}/resume`, req);
    return response.data;
  } catch (error) {
    throw new Error(getApiErrorMessage(error, 'Failed to resume pipeline.'));
  }
}

// ---------------------------------------------------------------------------
// QC endpoints
// ---------------------------------------------------------------------------

export async function approveQC(pipelineId: string): Promise<void> {
  try {
    await contentGenClient.post(`/qc/${pipelineId}/approve`);
  } catch (error) {
    throw new Error(getApiErrorMessage(error, 'Failed to approve QC.'));
  }
}

// ---------------------------------------------------------------------------
// Scripting endpoints
// ---------------------------------------------------------------------------

export async function runScripting(
  req: RunScriptingRequest,
): Promise<RunScriptingResponse> {
  try {
    const response = await contentGenClient.post('/scripting', req, {
      timeout: SCRIPTING_TIMEOUT_MS,
    });
    return response.data;
  } catch (error) {
    throw new Error(getApiErrorMessage(error, 'Failed to run scripting.'));
  }
}

export async function listScripts(): Promise<SavedScriptRun[]> {
  try {
    const response = await contentGenClient.get('/scripts');
    return response.data.items ?? response.data;
  } catch (error) {
    throw new Error(getApiErrorMessage(error, 'Failed to list scripts.'));
  }
}

export async function getScript(
  runId: string,
): Promise<RunScriptingResponse> {
  try {
    const response = await contentGenClient.get(`/scripts/${runId}`);
    return response.data;
  } catch (error) {
    throw new Error(getApiErrorMessage(error, 'Failed to get script.'));
  }
}

// ---------------------------------------------------------------------------
// Strategy endpoints
// ---------------------------------------------------------------------------

export async function getStrategy(): Promise<StrategyMemory> {
  try {
    const response = await contentGenClient.get('/strategy');
    return response.data;
  } catch (error) {
    throw new Error(getApiErrorMessage(error, 'Failed to get strategy.'));
  }
}

export async function updateStrategy(
  patch: Record<string, unknown>,
): Promise<StrategyMemory> {
  try {
    const response = await contentGenClient.put('/strategy', { patch });
    return response.data;
  } catch (error) {
    throw new Error(getApiErrorMessage(error, 'Failed to update strategy.'));
  }
}

// ---------------------------------------------------------------------------
// Publish queue endpoints
// ---------------------------------------------------------------------------

export async function listPublishQueue(): Promise<PublishItem[]> {
  try {
    const response = await contentGenClient.get('/publish');
    return response.data.items ?? response.data;
  } catch (error) {
    throw new Error(getApiErrorMessage(error, 'Failed to list publish queue.'));
  }
}

export async function removeFromQueue(
  ideaId: string,
  platform: string,
): Promise<void> {
  try {
    await contentGenClient.delete(`/publish/${ideaId}/${platform}`);
  } catch (error) {
    throw new Error(
      getApiErrorMessage(error, 'Failed to remove item from publish queue.'),
    );
  }
}

// ---------------------------------------------------------------------------
// Backlog endpoints
// ---------------------------------------------------------------------------

interface BacklogListResponse {
  path: string;
  items: BacklogItem[];
}

export async function listBacklog(): Promise<BacklogListResponse> {
  try {
    const response = await contentGenClient.get<BacklogListResponse>('/backlog');
    return response.data;
  } catch (error) {
    throw new Error(getApiErrorMessage(error, 'Failed to load backlog.'));
  }
}

export async function updateBacklogItem(
  ideaId: string,
  patch: Record<string, unknown>,
): Promise<BacklogItem> {
  try {
    const response = await contentGenClient.patch(`/backlog/${ideaId}`, { patch });
    return response.data;
  } catch (error) {
    throw new Error(getApiErrorMessage(error, 'Failed to update backlog item.'));
  }
}

export async function selectBacklogItem(ideaId: string): Promise<BacklogItem> {
  try {
    const response = await contentGenClient.post<BacklogItem>(`/backlog/${ideaId}/select`);
    return response.data;
  } catch (error) {
    throw new Error(getApiErrorMessage(error, 'Failed to select backlog item.'));
  }
}

export async function archiveBacklogItem(ideaId: string): Promise<BacklogItem> {
  try {
    const response = await contentGenClient.post<BacklogItem>(`/backlog/${ideaId}/archive`);
    return response.data;
  } catch (error) {
    throw new Error(getApiErrorMessage(error, 'Failed to archive backlog item.'));
  }
}

export async function deleteBacklogItem(ideaId: string): Promise<void> {
  try {
    await contentGenClient.delete(`/backlog/${ideaId}`);
  } catch (error) {
    throw new Error(getApiErrorMessage(error, 'Failed to delete backlog item.'));
  }
}

export async function startBacklogItem(
  ideaId: string,
): Promise<{ pipeline_id: string; status: string; idea_id: string; from_stage: number; to_stage: number }> {
  try {
    const response = await contentGenClient.post<{
      pipeline_id: string;
      status: string;
      idea_id: string;
      from_stage: number;
      to_stage: number;
    }>(`/backlog/${ideaId}/start`);
    return response.data;
  } catch (error) {
    throw new Error(getApiErrorMessage(error, 'Failed to start backlog item.'));
  }
}

export interface CreateBacklogItemRequest {
  title?: string;
  one_line_summary?: string;
  raw_idea?: string;
  constraints?: string;
  idea?: string;
  category?: string;
  audience?: string;
  persona_detail?: string;
  problem?: string;
  emotional_driver?: string;
  urgency_level?: string;
  source?: string;
  why_now?: string;
  hook?: string;
  content_type?: string;
  format_duration?: string;
  key_message?: string;
  call_to_action?: string;
  evidence?: string;
  proof_gap_note?: string;
  expertise_reason?: string;
  genericity_risk?: string;
  risk_level?: string;
  source_theme?: string;
  selection_reasoning?: string;
}

export async function createBacklogItem(
  data: Record<string, unknown>,
): Promise<BacklogItem> {
  try {
    const response = await contentGenClient.post<BacklogItem>('/backlog', data);
    return response.data;
  } catch (error) {
    throw new Error(getApiErrorMessage(error, 'Failed to create backlog item.'));
  }
}

// ---------------------------------------------------------------------------
// Backlog chat endpoints
// ---------------------------------------------------------------------------

const BACKLOG_CHAT_TIMEOUT_MS = 45000;

export async function backlogChatRespond(
  req: BacklogChatRespondRequest,
): Promise<BacklogChatRespondResponse> {
  try {
    const response = await contentGenClient.post<BacklogChatRespondResponse>(
      '/backlog-chat/respond',
      req,
      { timeout: BACKLOG_CHAT_TIMEOUT_MS },
    );
    return response.data;
  } catch (error) {
    throw new Error(getApiErrorMessage(error, 'Failed to get chat response.'));
  }
}

export async function backlogChatApply(
  req: BacklogChatApplyRequest,
): Promise<BacklogChatApplyResponse> {
  try {
    const response = await contentGenClient.post<BacklogChatApplyResponse>(
      '/backlog-chat/apply',
      req,
    );
    return response.data;
  } catch (error) {
    throw new Error(getApiErrorMessage(error, 'Failed to apply chat proposal.'));
  }
}

// ---------------------------------------------------------------------------
// Backlog AI Triage endpoints
// ---------------------------------------------------------------------------

const BACKLOG_TRIAGE_TIMEOUT_MS = 60000;

export async function backlogTriageRespond(
  req: TriageRespondRequest,
): Promise<TriageRespondResponse> {
  try {
    const response = await contentGenClient.post<TriageRespondResponse>(
      '/backlog-ai/triage/respond',
      req,
      { timeout: BACKLOG_TRIAGE_TIMEOUT_MS },
    );
    return response.data;
  } catch (error) {
    throw new Error(getApiErrorMessage(error, 'Failed to run triage analysis.'));
  }
}

export async function backlogTriageApply(
  req: TriageApplyRequest,
): Promise<TriageApplyResponse> {
  try {
    const response = await contentGenClient.post<TriageApplyResponse>(
      '/backlog-ai/triage/apply',
      req,
    );
    return response.data;
  } catch (error) {
    throw new Error(getApiErrorMessage(error, 'Failed to apply triage proposals.'));
  }
}

// ---------------------------------------------------------------------------
// Next-Action Recommendations (P2-T1)
// ---------------------------------------------------------------------------

const NEXT_ACTION_TIMEOUT_MS = 45000;

export async function getNextAction(
  req: NextActionRequest,
): Promise<NextActionResponse> {
  try {
    const response = await contentGenClient.post<NextActionResponse>(
      '/backlog-ai/next-action',
      req,
      { timeout: NEXT_ACTION_TIMEOUT_MS },
    );
    return response.data;
  } catch (error) {
    throw new Error(getApiErrorMessage(error, 'Failed to get next-action recommendation.'));
  }
}

export async function getNextActionBatch(
  req: TriageRespondRequest,
): Promise<NextActionBatchResponse> {
  try {
    const response = await contentGenClient.post<NextActionBatchResponse>(
      '/backlog-ai/next-action/batch',
      req,
      { timeout: BACKLOG_TRIAGE_TIMEOUT_MS * 2 },
    );
    return response.data;
  } catch (error) {
    throw new Error(getApiErrorMessage(error, 'Failed to get batch next-action recommendations.'));
  }
}

// ---------------------------------------------------------------------------
// Execution Brief (P2-T2)
// ---------------------------------------------------------------------------

const EXECUTION_BRIEF_TIMEOUT_MS = 45000;

export async function generateExecutionBrief(
  req: ExecutionBriefRequest,
): Promise<ExecutionBriefResponse> {
  try {
    const response = await contentGenClient.post<ExecutionBriefResponse>(
      '/backlog-ai/execution-brief',
      req,
      { timeout: EXECUTION_BRIEF_TIMEOUT_MS },
    );
    return response.data;
  } catch (error) {
    throw new Error(getApiErrorMessage(error, 'Failed to generate execution brief.'));
  }
}
