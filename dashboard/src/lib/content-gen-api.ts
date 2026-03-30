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
} from '@/types/content-gen';

// ---------------------------------------------------------------------------
// Client
// ---------------------------------------------------------------------------

const CONTENT_GEN_TIMEOUT_MS = 30000;
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
    const response = await contentGenClient.get(`/pipelines/${id}`);
    return response.data;
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
