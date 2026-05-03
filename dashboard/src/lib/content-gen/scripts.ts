import { contentGenClient, getContentGenErrorMessage, SCRIPTING_TIMEOUT_MS } from './client';
import type {
  RunScriptingRequest,
  RunScriptingResponse,
  SavedScriptRun,
  HookSet,
  CtaVariants,
} from '@/types/content-gen';

export interface GenerateVariantsResponse {
  hooks: HookSet;
  cta_variants: CtaVariants;
}

export async function runScripting(
  req: RunScriptingRequest,
): Promise<RunScriptingResponse> {
  try {
    const response = await contentGenClient.post('/scripting', req, {
      timeout: SCRIPTING_TIMEOUT_MS,
    });
    return response.data;
  } catch (error) {
    throw new Error(getContentGenErrorMessage(error, 'Failed to run scripting.'));
  }
}

export async function listScripts(): Promise<SavedScriptRun[]> {
  try {
    const response = await contentGenClient.get('/scripts');
    return response.data.items ?? response.data;
  } catch (error) {
    throw new Error(getContentGenErrorMessage(error, 'Failed to list scripts.'));
  }
}

export async function getScript(
  runId: string,
): Promise<RunScriptingResponse> {
  try {
    const response = await contentGenClient.get(`/scripts/${runId}`);
    return response.data;
  } catch (error) {
    throw new Error(getContentGenErrorMessage(error, 'Failed to get script.'));
  }
}

export async function generateScriptVariants(
  runId: string,
  options?: { tone?: string; cta_goal?: string },
): Promise<GenerateVariantsResponse> {
  try {
    const response = await contentGenClient.post(
      `/scripts/${runId}/generate-variants`,
      options ?? {},
    );
    return response.data;
  } catch (error) {
    throw new Error(getContentGenErrorMessage(error, 'Failed to generate variants.'));
  }
}

export async function updateScript(
  runId: string,
  patch: { hook?: string; cta?: string; script?: string }
): Promise<{ success: boolean; run_id: string }> {
  try {
    const response = await contentGenClient.patch(`/scripts/${runId}`, patch);
    return response.data;
  } catch (error) {
    throw new Error(getContentGenErrorMessage(error, 'Failed to update script.'));
  }
}