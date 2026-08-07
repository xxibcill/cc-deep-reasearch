import { afterEach, describe, expect, it, vi } from 'vitest';

import { apiClient } from '@/lib/api/client';
import { resumeResearchSession } from '@/lib/api';

describe('resumeResearchSession', () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('posts the selected checkpoint with an idempotency key', async () => {
    const payload = {
      run_id: 'run-resumed',
      status: 'queued' as const,
      original_run_id: 'run-original',
      original_session_id: 'session-original',
      resumed_from_checkpoint_id: 'cp-source-collection',
      resume_attempt: 1,
      resume_mode: 'resume_latest',
    };
    const post = vi.spyOn(apiClient, 'post').mockResolvedValue({ data: payload });

    const result = await resumeResearchSession('session-original', {
      checkpointId: 'cp-source-collection',
      idempotencyKey: 'resume-once',
    });

    expect(result).toEqual(payload);
    expect(post).toHaveBeenCalledWith(
      '/sessions/session-original/resume',
      undefined,
      {
        params: { checkpoint_id: 'cp-source-collection' },
        headers: { 'Idempotency-Key': 'resume-once' },
      }
    );
  });
});
