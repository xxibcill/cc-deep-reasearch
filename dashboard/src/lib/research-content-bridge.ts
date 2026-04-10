import type { Session } from '@/types/telemetry';

/**
 * Bridge payload type for research content actions.
 * This is a stub implementation - the full content gen integration
 * will be implemented in a future PR.
 */
export interface ResearchContentBridgePayload {
  sessionId: string;
  sessionSummary: Session | null;
  contentType: string;
  metadata?: Record<string, unknown>;
}

/**
 * Build a bridge payload from a session.
 */
export function buildResearchContentBridgePayloadFromSession(
  sessionId: string,
  sessionSummary: Session | null,
  contentType: string
): ResearchContentBridgePayload {
  return {
    sessionId,
    sessionSummary,
    contentType,
  };
}

/**
 * Transform a bridge payload for research report content.
 * Returns the payload as-is in this stub implementation.
 */
export function withResearchReportContent(
  payload: ResearchContentBridgePayload,
  _report: { format: string; content: string } | null = null
): ResearchContentBridgePayload {
  return payload;
}
