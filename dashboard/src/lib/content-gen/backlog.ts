import { contentGenClient, getContentGenErrorMessage } from './client';
import type { BacklogItem, BacklogListResponse } from '@/types/content-gen';

export async function listBacklog(): Promise<BacklogListResponse> {
  try {
    const response = await contentGenClient.get<BacklogListResponse>('/backlog');
    return response.data;
  } catch (error) {
    throw new Error(getContentGenErrorMessage(error, 'Failed to load backlog.'));
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
    throw new Error(getContentGenErrorMessage(error, 'Failed to update backlog item.'));
  }
}

export async function selectBacklogItem(ideaId: string): Promise<BacklogItem> {
  try {
    const response = await contentGenClient.post<BacklogItem>(`/backlog/${ideaId}/select`);
    return response.data;
  } catch (error) {
    throw new Error(getContentGenErrorMessage(error, 'Failed to select backlog item.'));
  }
}

export async function archiveBacklogItem(ideaId: string): Promise<BacklogItem> {
  try {
    const response = await contentGenClient.post<BacklogItem>(`/backlog/${ideaId}/archive`);
    return response.data;
  } catch (error) {
    throw new Error(getContentGenErrorMessage(error, 'Failed to archive backlog item.'));
  }
}

export async function deleteBacklogItem(ideaId: string): Promise<void> {
  try {
    await contentGenClient.delete(`/backlog/${ideaId}`);
  } catch (error) {
    throw new Error(getContentGenErrorMessage(error, 'Failed to delete backlog item.'));
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
    throw new Error(getContentGenErrorMessage(error, 'Failed to start backlog item.'));
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
    throw new Error(getContentGenErrorMessage(error, 'Failed to create backlog item.'));
  }
}