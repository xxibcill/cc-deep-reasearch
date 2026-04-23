import { contentGenClient, getContentGenErrorMessage } from './client';
import type {
  ManagedOpportunityBrief,
  BriefRevision,
  BriefAuditResponse,
  BriefAssistantRespondRequest,
  BriefAssistantRespondResponse,
  BriefAssistantApplyRequest,
  BriefAssistantApplyResponse,
  GeneratedBacklogItem,
  BriefToBacklogResponse,
  ApplyBacklogFromBriefResponse,
  BranchBriefRequest,
  SiblingBriefsResponse,
  CompareBriefsResponse,
} from '@/types/content-gen';

export interface CreateBriefRequest {
  brief: Record<string, unknown>;
  provenance?: string;
  source_pipeline_id?: string;
  revision_notes?: string;
}

export interface SaveRevisionRequest {
  brief: Record<string, unknown>;
  revision_notes?: string;
  source_pipeline_id?: string;
  expected_updated_at?: string | null;
}

export interface ApplyRevisionRequest {
  revision_id: string;
  expected_updated_at?: string | null;
}

export interface UpdateBriefRequest {
  patch: Record<string, unknown>;
  expected_updated_at?: string | null;
}

export async function listBriefs(
  lifecycleState?: string,
  limit = 50,
): Promise<{ items: ManagedOpportunityBrief[]; count: number }> {
  try {
    const params = new URLSearchParams();
    if (lifecycleState) params.set('lifecycle_state', lifecycleState);
    params.set('limit', String(limit));
    const response = await contentGenClient.get<{ items: ManagedOpportunityBrief[]; count: number }>(
      `/briefs?${params.toString()}`,
    );
    return response.data;
  } catch (error) {
    throw new Error(getContentGenErrorMessage(error, 'Failed to list briefs.'));
  }
}

export async function getBrief(
  briefId: string,
): Promise<ManagedOpportunityBrief & { current_revision?: BriefRevision }> {
  try {
    const response = await contentGenClient.get<
      ManagedOpportunityBrief & { current_revision?: BriefRevision }
    >(`/briefs/${briefId}`);
    return response.data;
  } catch (error) {
    throw new Error(getContentGenErrorMessage(error, 'Failed to get brief.'));
  }
}

export async function createBrief(req: CreateBriefRequest): Promise<ManagedOpportunityBrief> {
  try {
    const response = await contentGenClient.post<ManagedOpportunityBrief>('/briefs', req);
    return response.data;
  } catch (error) {
    throw new Error(getContentGenErrorMessage(error, 'Failed to create brief.'));
  }
}

export async function updateBrief(
  briefId: string,
  req: UpdateBriefRequest,
): Promise<ManagedOpportunityBrief> {
  try {
    const response = await contentGenClient.patch<ManagedOpportunityBrief>(
      `/briefs/${briefId}`,
      req,
    );
    return response.data;
  } catch (error) {
    throw new Error(getContentGenErrorMessage(error, 'Failed to update brief.'));
  }
}

export async function listBriefRevisions(
  briefId: string,
  limit = 50,
): Promise<{ items: BriefRevision[]; count: number }> {
  try {
    const response = await contentGenClient.get<{ items: BriefRevision[]; count: number }>(
      `/briefs/${briefId}/revisions?limit=${limit}`,
    );
    return response.data;
  } catch (error) {
    throw new Error(getContentGenErrorMessage(error, 'Failed to list brief revisions.'));
  }
}

export async function getBriefRevision(
  briefId: string,
  revisionId: string,
): Promise<BriefRevision> {
  try {
    const response = await contentGenClient.get<BriefRevision>(
      `/briefs/${briefId}/revisions/${revisionId}`,
    );
    return response.data;
  } catch (error) {
    throw new Error(getContentGenErrorMessage(error, 'Failed to get brief revision.'));
  }
}

export async function saveBriefRevision(
  briefId: string,
  req: SaveRevisionRequest,
): Promise<BriefRevision> {
  try {
    const response = await contentGenClient.post<BriefRevision>(
      `/briefs/${briefId}/revisions`,
      req,
    );
    return response.data;
  } catch (error) {
    throw new Error(getContentGenErrorMessage(error, 'Failed to save brief revision.'));
  }
}

export async function applyRevision(
  briefId: string,
  req: ApplyRevisionRequest,
): Promise<ManagedOpportunityBrief> {
  try {
    const response = await contentGenClient.post<ManagedOpportunityBrief>(
      `/briefs/${briefId}/apply-revision`,
      req,
    );
    return response.data;
  } catch (error) {
    throw new Error(getContentGenErrorMessage(error, 'Failed to apply revision.'));
  }
}

export async function approveBrief(
  briefId: string,
  expectedUpdatedAt?: string | null,
): Promise<ManagedOpportunityBrief> {
  try {
    const response = await contentGenClient.post<ManagedOpportunityBrief>(
      `/briefs/${briefId}/approve`,
      {},
      { params: expectedUpdatedAt ? { expected_updated_at: expectedUpdatedAt } : undefined },
    );
    return response.data;
  } catch (error) {
    throw new Error(getContentGenErrorMessage(error, 'Failed to approve brief.'));
  }
}

export async function archiveBrief(
  briefId: string,
  expectedUpdatedAt?: string | null,
): Promise<ManagedOpportunityBrief> {
  try {
    const response = await contentGenClient.post<ManagedOpportunityBrief>(
      `/briefs/${briefId}/archive`,
      {},
      { params: expectedUpdatedAt ? { expected_updated_at: expectedUpdatedAt } : undefined },
    );
    return response.data;
  } catch (error) {
    throw new Error(getContentGenErrorMessage(error, 'Failed to archive brief.'));
  }
}

export async function supersedeBrief(
  briefId: string,
  expectedUpdatedAt?: string | null,
): Promise<ManagedOpportunityBrief> {
  try {
    const response = await contentGenClient.post<ManagedOpportunityBrief>(
      `/briefs/${briefId}/supersede`,
      {},
      { params: expectedUpdatedAt ? { expected_updated_at: expectedUpdatedAt } : undefined },
    );
    return response.data;
  } catch (error) {
    throw new Error(getContentGenErrorMessage(error, 'Failed to supersede brief.'));
  }
}

export async function revertBriefToDraft(
  briefId: string,
  expectedUpdatedAt?: string | null,
): Promise<ManagedOpportunityBrief> {
  try {
    const response = await contentGenClient.post<ManagedOpportunityBrief>(
      `/briefs/${briefId}/revert-to-draft`,
      {},
      { params: expectedUpdatedAt ? { expected_updated_at: expectedUpdatedAt } : undefined },
    );
    return response.data;
  } catch (error) {
    throw new Error(getContentGenErrorMessage(error, 'Failed to revert brief to draft.'));
  }
}

export async function cloneBrief(
  briefId: string,
  newTitle?: string,
): Promise<ManagedOpportunityBrief> {
  try {
    const response = await contentGenClient.post<ManagedOpportunityBrief>(
      `/briefs/${briefId}/clone`,
      { new_title: newTitle },
    );
    return response.data;
  } catch (error) {
    throw new Error(getContentGenErrorMessage(error, 'Failed to clone brief.'));
  }
}

export async function getBriefAuditHistory(
  briefId: string,
  eventType?: string,
  actor?: string,
  limit = 100,
): Promise<BriefAuditResponse> {
  try {
    const params = new URLSearchParams();
    if (eventType) params.set('event_type', eventType);
    if (actor) params.set('actor', actor);
    params.set('limit', String(limit));
    const response = await contentGenClient.get<BriefAuditResponse>(
      `/briefs/${briefId}/audit?${params.toString()}`,
    );
    return response.data;
  } catch (error) {
    throw new Error(getContentGenErrorMessage(error, 'Failed to get brief audit history.'));
  }
}

const BRIEF_ASSISTANT_TIMEOUT_MS = 45000;

export async function briefAssistantRespond(
  briefId: string,
  req: BriefAssistantRespondRequest,
): Promise<BriefAssistantRespondResponse> {
  try {
    const response = await contentGenClient.post<BriefAssistantRespondResponse>(
      `/briefs/${briefId}/assistant/respond`,
      req,
      { timeout: BRIEF_ASSISTANT_TIMEOUT_MS },
    );
    return response.data;
  } catch (error) {
    throw new Error(getContentGenErrorMessage(error, 'Failed to get brief assistant response.'));
  }
}

export async function briefAssistantApply(
  briefId: string,
  req: BriefAssistantApplyRequest,
): Promise<BriefAssistantApplyResponse> {
  try {
    const response = await contentGenClient.post<BriefAssistantApplyResponse>(
      `/briefs/${briefId}/assistant/apply`,
      req,
    );
    return response.data;
  } catch (error) {
    throw new Error(getContentGenErrorMessage(error, 'Failed to apply brief assistant proposals.'));
  }
}

const BRIEF_TO_BACKLOG_TIMEOUT_MS = 60000;

export async function generateBacklogFromBrief(
  briefId: string,
): Promise<BriefToBacklogResponse> {
  try {
    const response = await contentGenClient.post<BriefToBacklogResponse>(
      `/briefs/${briefId}/generate-backlog`,
      {},
      { timeout: BRIEF_TO_BACKLOG_TIMEOUT_MS },
    );
    return response.data;
  } catch (error) {
    throw new Error(getContentGenErrorMessage(error, 'Failed to generate backlog from brief.'));
  }
}

export async function applyBacklogFromBrief(
  briefId: string,
  items: GeneratedBacklogItem[],
): Promise<ApplyBacklogFromBriefResponse> {
  try {
    const response = await contentGenClient.post<ApplyBacklogFromBriefResponse>(
      `/briefs/${briefId}/apply-backlog`,
      items,
    );
    return response.data;
  } catch (error) {
    throw new Error(getContentGenErrorMessage(error, 'Failed to apply backlog items.'));
  }
}

export async function branchBrief(
  briefId: string,
  req: BranchBriefRequest,
): Promise<ManagedOpportunityBrief> {
  try {
    const response = await contentGenClient.post<ManagedOpportunityBrief>(
      `/briefs/${briefId}/branch`,
      req,
    );
    return response.data;
  } catch (error) {
    throw new Error(getContentGenErrorMessage(error, 'Failed to branch brief.'));
  }
}

export async function listSiblingBriefs(
  briefId: string,
): Promise<SiblingBriefsResponse> {
  try {
    const response = await contentGenClient.get<SiblingBriefsResponse>(
      `/briefs/${briefId}/siblings`,
    );
    return response.data;
  } catch (error) {
    throw new Error(getContentGenErrorMessage(error, 'Failed to list sibling briefs.'));
  }
}

export async function compareBriefs(
  briefId: string,
  otherBriefId: string,
): Promise<CompareBriefsResponse> {
  try {
    const response = await contentGenClient.get<CompareBriefsResponse>(
      `/briefs/${briefId}/compare/${otherBriefId}`,
    );
    return response.data;
  } catch (error) {
    throw new Error(getContentGenErrorMessage(error, 'Failed to compare briefs.'));
  }
}