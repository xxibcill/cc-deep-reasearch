import { contentGenClient, getContentGenErrorMessage } from './client';
import type {
  BacklogChatMessage,
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
    throw new Error(getContentGenErrorMessage(error, 'Failed to get chat response.'));
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
    throw new Error(getContentGenErrorMessage(error, 'Failed to apply chat proposal.'));
  }
}

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
    throw new Error(getContentGenErrorMessage(error, 'Failed to run triage analysis.'));
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
    throw new Error(getContentGenErrorMessage(error, 'Failed to apply triage proposals.'));
  }
}

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
    throw new Error(getContentGenErrorMessage(error, 'Failed to get next-action recommendation.'));
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
    throw new Error(getContentGenErrorMessage(error, 'Failed to get batch next-action recommendations.'));
  }
}

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
    throw new Error(getContentGenErrorMessage(error, 'Failed to generate execution brief.'));
  }
}