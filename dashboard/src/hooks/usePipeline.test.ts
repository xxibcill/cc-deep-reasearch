import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, act, waitFor } from '@testing-library/react';
import { usePipelineStore } from './usePipeline';
import type { PipelineRunSummary, PipelineContext } from '@/types/content-gen';

// Mock the API module
vi.mock('@/lib/content-gen/pipeline', () => ({
  listPipelines: vi.fn(),
  startPipeline: vi.fn(),
  getPipeline: vi.fn(),
  stopPipeline: vi.fn(),
  resumePipeline: vi.fn(),
  approveQC: vi.fn(),
}));

vi.mock('@/lib/api', () => ({
  getApiErrorMessage: vi.fn((_, fallback) => fallback),
}));

import {
  listPipelines,
  startPipeline,
  getPipeline,
  stopPipeline,
  resumePipeline,
  approveQC,
} from '@/lib/content-gen/pipeline';

const mockPipelineRun = (overrides: Partial<PipelineRunSummary> = {}): PipelineRunSummary => ({
  pipeline_id: 'pipeline-001',
  theme: 'Test Pipeline Theme',
  status: 'running',
  current_stage: 2,
  total_stages: 14,
  created_at: '2026-04-01T10:00:00Z',
  updated_at: '2026-04-01T12:00:00Z',
  ...overrides,
} as PipelineRunSummary);

const mockPipelineContext = (overrides: Partial<PipelineContext> = {}): PipelineContext => ({
  pipeline_id: 'pipeline-001',
  theme: 'Test Pipeline Theme',
  status: 'running',
  current_stage: 2,
  stage_traces: [],
  iteration_state: null,
  ...overrides,
} as PipelineContext);

describe('usePipelineStore', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    const { result } = renderHook(() => usePipelineStore());
    act(() => {
      result.current.clearError();
    });
  });

  describe('loadPipelines', () => {
    it('loads pipelines successfully', async () => {
      const mockPipelines = [
        mockPipelineRun({ pipeline_id: 'pipeline-001' }),
        mockPipelineRun({ pipeline_id: 'pipeline-002', status: 'completed' }),
      ];
      vi.mocked(listPipelines).mockResolvedValueOnce(mockPipelines);

      const { result } = renderHook(() => usePipelineStore());

      await act(async () => {
        await result.current.loadPipelines();
      });

      expect(result.current.pipelines).toHaveLength(2);
      expect(result.current.pipelinesLoading).toBe(false);
    });

    it('sets error on API failure', async () => {
      vi.mocked(listPipelines).mockRejectedValueOnce(new Error('Network error'));

      const { result } = renderHook(() => usePipelineStore());

      await act(async () => {
        await result.current.loadPipelines();
      });

      await waitFor(() => {
        expect(result.current.error).toBeTruthy();
      });
    });
  });

  describe('selectPipeline', () => {
    it('loads pipeline context for selected pipeline', async () => {
      const mockContext = mockPipelineContext({ pipeline_id: 'pipeline-001', theme: 'Selected Pipeline' });
      vi.mocked(getPipeline).mockResolvedValueOnce(mockContext);

      const { result } = renderHook(() => usePipelineStore());

      await act(async () => {
        await result.current.selectPipeline('pipeline-001');
      });

      expect(result.current.activePipelineId).toBe('pipeline-001');
      expect(result.current.pipelineContext).toEqual(mockContext);
    });

    it('resets context when selecting new pipeline', async () => {
      const ctx1 = mockPipelineContext({ pipeline_id: 'pipeline-001', theme: 'Pipeline 1' });
      const ctx2 = mockPipelineContext({ pipeline_id: 'pipeline-002', theme: 'Pipeline 2' });
      vi.mocked(getPipeline)
        .mockResolvedValueOnce(ctx1)
        .mockResolvedValueOnce(ctx2);

      const { result } = renderHook(() => usePipelineStore());

      await act(async () => {
        await result.current.selectPipeline('pipeline-001');
      });
      expect(result.current.pipelineContext?.pipeline_id).toBe('pipeline-001');

      await act(async () => {
        await result.current.selectPipeline('pipeline-002');
      });
      expect(result.current.activePipelineId).toBe('pipeline-002');
      expect(result.current.pipelineContext?.pipeline_id).toBe('pipeline-002');
    });
  });

  describe('stopPipeline', () => {
    it('reloads pipelines list after stopping', async () => {
      vi.mocked(stopPipeline).mockResolvedValueOnce(undefined);
      vi.mocked(listPipelines).mockResolvedValueOnce([
        mockPipelineRun({ pipeline_id: 'pipeline-001', status: 'cancelled' }),
      ]);

      const { result } = renderHook(() => usePipelineStore());

      await act(async () => {
        await result.current.stopPipeline('pipeline-001');
      });

      expect(stopPipeline).toHaveBeenCalledWith('pipeline-001');
      expect(listPipelines).toHaveBeenCalled();
    });
  });

  describe('approveQC', () => {
    it('reloads pipeline context after approving QC', async () => {
      const updatedCtx = mockPipelineContext({ pipeline_id: 'pipeline-001', status: 'completed' });
      vi.mocked(approveQC).mockResolvedValueOnce(undefined);
      vi.mocked(getPipeline).mockResolvedValueOnce(updatedCtx);

      const { result } = renderHook(() => usePipelineStore());

      await act(async () => {
        await result.current.approveQC('pipeline-001');
      });

      expect(approveQC).toHaveBeenCalledWith('pipeline-001');
      expect(result.current.pipelineContext).toEqual(updatedCtx);
    });
  });

  describe('updateStageProgress', () => {
    it('updates stage progress for a given stage index', () => {
      const { result } = renderHook(() => usePipelineStore());

      act(() => {
        result.current.updateStageProgress(2, { status: 'running', started_at: '2026-04-01T12:00:00Z' });
      });

      expect(result.current.pipelineStageProgress[2]).toMatchObject({
        status: 'running',
        started_at: '2026-04-01T12:00:00Z',
      });
    });

    it('merges with existing stage progress', () => {
      const { result } = renderHook(() => usePipelineStore());

      act(() => {
        result.current.updateStageProgress(2, { status: 'running' });
      });

      act(() => {
        result.current.updateStageProgress(2, { status: 'completed', completed_at: '2026-04-01T12:05:00Z' });
      });

      expect(result.current.pipelineStageProgress[2]).toMatchObject({
        status: 'completed',
        started_at: undefined,
        completed_at: '2026-04-01T12:05:00Z',
      });
    });
  });

  describe('updatePipelineContext', () => {
    it('updates the pipeline context directly', () => {
      const newCtx = mockPipelineContext({ pipeline_id: 'pipeline-001', theme: 'Updated Theme' });
      const { result } = renderHook(() => usePipelineStore());

      act(() => {
        result.current.updatePipelineContext(newCtx);
      });

      expect(result.current.pipelineContext).toEqual(newCtx);
    });
  });
});
