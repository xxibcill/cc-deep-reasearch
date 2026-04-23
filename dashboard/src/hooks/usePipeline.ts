import { create } from 'zustand';
import type {
  PipelineRunSummary,
  PipelineContext,
  StageProgress,
} from '@/types/content-gen';
import {
  listPipelines,
  startPipeline as startPipelineApi,
  getPipeline,
  stopPipeline as stopPipelineApi,
  resumePipeline as resumePipelineApi,
  approveQC as approveQCApi,
} from '@/lib/content-gen/pipeline';
import { getApiErrorMessage } from '@/lib/api';

interface PipelineState {
  pipelines: PipelineRunSummary[];
  pipelinesLoading: boolean;
  activePipelineId: string | null;
  pipelineContext: PipelineContext | null;
  pipelineStageProgress: Record<number, StageProgress>;
  error: string | null;
  loadPipelines: () => Promise<void>;
  startPipeline: (theme: string, fromStage?: number, toStage?: number) => Promise<string | null>;
  selectPipeline: (id: string) => Promise<void>;
  stopPipeline: (id: string) => Promise<void>;
  resumePipeline: (id: string, fromStage?: number) => Promise<string | null>;
  approveQC: (pipelineId: string) => Promise<void>;
  updateStageProgress: (stageIndex: number, event: Record<string, unknown>) => void;
  updatePipelineContext: (context: PipelineContext) => void;
  clearError: () => void;
}

const initialState = {
  pipelines: [],
  pipelinesLoading: false,
  activePipelineId: null as string | null,
  pipelineContext: null as PipelineContext | null,
  pipelineStageProgress: {} as Record<number, StageProgress>,
  error: null as string | null,
};

export const usePipelineStore = create<PipelineState>((set, get) => ({
  ...initialState,

  loadPipelines: async () => {
    set({ pipelinesLoading: true, error: null });
    try {
      const pipelines = await listPipelines();
      set({ pipelines, pipelinesLoading: false });
    } catch (err) {
      set({
        pipelinesLoading: false,
        error: getApiErrorMessage(err, 'Failed to load pipelines.'),
      });
    }
  },

  startPipeline: async (theme, fromStage, toStage) => {
    set({ error: null });
    try {
      const result = await startPipelineApi({
        theme,
        from_stage: fromStage,
        to_stage: toStage ?? null,
      });
      const pipelineId = result.pipeline_id ?? null;
      if (pipelineId) {
        set({ activePipelineId: pipelineId });
        const pipelines = await listPipelines();
        set({ pipelines });
      }
      return pipelineId;
    } catch (err) {
      set({ error: getApiErrorMessage(err, 'Failed to start pipeline.') });
      return null;
    }
  },

  selectPipeline: async (id) => {
    set({ activePipelineId: id, pipelineContext: null, pipelineStageProgress: {}, error: null });
    try {
      const context = await getPipeline(id);
      set({ pipelineContext: context });
    } catch (err) {
      set({ error: getApiErrorMessage(err, 'Failed to load pipeline context.') });
    }
  },

  stopPipeline: async (id) => {
    set({ error: null });
    try {
      await stopPipelineApi(id);
      const pipelines = await listPipelines();
      set({ pipelines });
      if (get().activePipelineId === id) {
        set({ pipelineContext: null });
      }
    } catch (err) {
      set({ error: getApiErrorMessage(err, 'Failed to stop pipeline.') });
    }
  },

  resumePipeline: async (id, fromStage) => {
    set({ error: null });
    try {
      const result = await resumePipelineApi(id, { from_stage: fromStage });
      const pipelineId = result.pipeline_id ?? null;
      if (pipelineId) {
        set({ activePipelineId: pipelineId });
      }
      return pipelineId;
    } catch (err) {
      set({ error: getApiErrorMessage(err, 'Failed to resume pipeline.') });
      return null;
    }
  },

  approveQC: async (pipelineId) => {
    set({ error: null });
    try {
      await approveQCApi(pipelineId);
      const context = await getPipeline(pipelineId);
      set({ pipelineContext: context });
    } catch (err) {
      set({ error: getApiErrorMessage(err, 'Failed to approve QC.') });
    }
  },

  updateStageProgress: (stageIndex, event) => {
    set((state) => ({
      pipelineStageProgress: {
        ...state.pipelineStageProgress,
        [stageIndex]: {
          ...state.pipelineStageProgress[stageIndex],
          ...event,
        } as StageProgress,
      },
    }));
  },

  updatePipelineContext: (context) => {
    set({ pipelineContext: context });
  },

  clearError: () => set({ error: null }),
}));

// Backwards compatibility alias
export const usePipeline = usePipelineStore;